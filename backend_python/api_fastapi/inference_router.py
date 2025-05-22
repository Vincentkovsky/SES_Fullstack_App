#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Inference API (FastAPI version)

Provides HTTP API for machine learning model inference, supporting water depth prediction
and flood inundation analysis.
"""

from fastapi import APIRouter, Body, HTTPException, status, BackgroundTasks, Path, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import os
import json
import logging
from pathlib import Path as FilePath
import time
import asyncio
from starlette.concurrency import run_in_threadpool
import torch

# Import custom tools
from core.fastapi_helpers import async_handle_exceptions
from core.config import Config
from services.inference_service import InferenceService
from ai_inference.model import get_model_path, get_data_file, list_available_files, MODEL_DIR

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/inference")

# Base paths
BASE_DIR = FilePath(__file__).parent.parent
INFERENCE_RESULTS_DIR = BASE_DIR / "data/inference_results"

# Ensure inference results directory exists
INFERENCE_RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Track running inference tasks
running_tasks = {}


class InferenceAPI:
    """API methods for inference operations"""
    
    @staticmethod
    @router.get("/status", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def get_inference_status():
        """Get inference service status"""
        # Check if necessary model files exist
        model_path = FilePath(get_model_path())
        model_exists = model_path.exists()
        
        # Check necessary data files
        data_files = {
            "dem_embeddings": FilePath(get_data_file("dem_embeddings")).exists(),
            "side_lengths": FilePath(get_data_file("side_lengths")).exists(),
            "square_centers": FilePath(get_data_file("square_centers")).exists(),
            "dem_min_tensor": FilePath(get_data_file("dem_min_tensor")).exists(),
            "water_level_min": FilePath(get_data_file("water_level_min")).exists(),
            "dem_file": FilePath(get_data_file("dem_file")).exists(),
            "gridadmin_file": FilePath(get_data_file("gridadmin_file")).exists(),
        }
        
        # Check data directory
        rainfall_data_dir = FilePath(get_data_file("rainfall_data"))
        rainfall_data_exists = rainfall_data_dir.exists() if rainfall_data_dir else False
        
        status_info = {
            "model_path": str(model_path),
            "model_exists": model_exists,
            "data_files": data_files,
            "rainfall_data_exists": rainfall_data_exists,
            "running_tasks": len(running_tasks),
            "task_ids": list(running_tasks.keys()),
            "results_directory": str(INFERENCE_RESULTS_DIR)
        }
        
        return {
            "success": True,
            "data": status_info
        }
    
    @staticmethod
    @router.get("/available_data", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def get_available_data():
        """Get available data files and models"""
        data_files = list_available_files()
        data_files = {k: FilePath(v).exists() for k, v in data_files.items()}
        
        return {
            "success": True,
            "data": {
                "available_files": data_files
            }
        }
    
    @staticmethod
    @router.post("/run", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def run_inference_task(
        background_tasks: BackgroundTasks,
        parameters: Dict[str, Any] = Body(..., description="Inference parameters")
    ):
        """
        Run inference task
        
        Parameters can include:
        - model_path: Model file path (default: best.pt)
        - data_dir: Input data directory (default: rainfall_20221024)
        - device: Computing device (default: cuda:0 or cpu)
        - pred_length: Number of prediction timesteps (default: 48)
        
        Args:
            background_tasks: Background task manager
            parameters: Inference parameter dictionary
        
        Returns:
            Task ID and status information
        """
        logger.info(f"Preparing to start inference task, parameters: {parameters}")
        
        # Validate necessary model and data files
        model_path = parameters.get('model_path', 'best.pt')
        model_full_path = FilePath(MODEL_DIR) / model_path
        if not model_full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model file does not exist: {model_full_path}"
            )
        
        # Validate data directory
        data_dir = parameters.get('data_dir', 'rainfall_20221024')
        data_dir_path = FilePath(MODEL_DIR) / data_dir
        if not data_dir_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Data directory does not exist: {data_dir_path}"
            )
        
        # Generate task ID
        task_id = f"inference_{int(time.time())}_{parameters.get('data_dir', 'default')}"
        
        # Prepare output directory
        task_dir = INFERENCE_RESULTS_DIR / task_id
        task_dir.mkdir(exist_ok=True)
        
        # Save parameters to JSON file
        params_file = task_dir / "parameters.json"
        with open(params_file, 'w') as f:
            json.dump(parameters, f, indent=2)
        
        # Add to background tasks
        background_tasks.add_task(
            execute_inference_task,
            task_id=task_id,
            params=parameters,
            task_dir=task_dir
        )
        
        # Mark task as running
        running_tasks[task_id] = {
            "status": "running",
            "start_time": time.time(),
            "parameters": parameters,
            "results_dir": str(task_dir)
        }
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": "running",
                "message": "Inference task started"
            }
        }
    
    @staticmethod
    @router.get("/tasks", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def list_inference_tasks():
        """Get list of all inference tasks"""
        tasks = []
        
        # Collect running tasks
        for task_id, task_info in running_tasks.items():
            tasks.append({
                "task_id": task_id,
                "status": task_info["status"],
                "start_time": task_info["start_time"],
                "elapsed_time": time.time() - task_info["start_time"],
                "results_dir": task_info.get("results_dir")
            })
        
        # Find completed tasks
        completed_dirs = [d for d in INFERENCE_RESULTS_DIR.iterdir() if d.is_dir()]
        for task_dir in completed_dirs:
            task_id = task_dir.name
            
            # Skip running tasks (already added)
            if task_id in running_tasks:
                continue
            
            # Check task status file
            status_file = task_dir / "status.json"
            if status_file.exists():
                try:
                    with open(status_file, 'r') as f:
                        status_info = json.load(f)
                    
                    tasks.append({
                        "task_id": task_id,
                        "status": status_info.get("status", "completed"),
                        "start_time": status_info.get("start_time", 0),
                        "end_time": status_info.get("end_time", 0),
                        "elapsed_time": status_info.get("elapsed_time", 0),
                        "results_dir": str(task_dir)
                    })
                except Exception as e:
                    logger.error(f"Failed to read task status file: {e}")
                    
                    # No valid status file but directory exists, possibly a previous task
                    tasks.append({
                        "task_id": task_id,
                        "status": "unknown",
                        "results_dir": str(task_dir)
                    })
        
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks)
            }
        }
    
    @staticmethod
    @router.get("/tasks/{task_id}", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def get_task_status(task_id: str = Path(..., description="Task ID")):
        """Get status of a specific task"""
        # Check if it's a running task
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            return {
                "success": True,
                "data": {
                    "task_id": task_id,
                    "status": task_info["status"],
                    "start_time": task_info["start_time"],
                    "elapsed_time": time.time() - task_info["start_time"],
                    "parameters": task_info.get("parameters"),
                    "results_dir": task_info.get("results_dir")
                }
            }
        
        # Check completed task directory
        task_dir = INFERENCE_RESULTS_DIR / task_id
        if not task_dir.exists() or not task_dir.is_dir():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )
        
        # Read task status
        status_file = task_dir / "status.json"
        if status_file.exists():
            try:
                with open(status_file, 'r') as f:
                    status_info = json.load(f)
                
                return {
                    "success": True,
                    "data": {
                        "task_id": task_id,
                        "status": status_info.get("status", "completed"),
                        "start_time": status_info.get("start_time", 0),
                        "end_time": status_info.get("end_time", 0),
                        "elapsed_time": status_info.get("elapsed_time", 0),
                        "parameters": status_info.get("parameters"),
                        "results": status_info.get("results"),
                        "results_dir": str(task_dir)
                    }
                }
            except Exception as e:
                logger.error(f"Failed to read task status file: {e}")
        
        # Read parameters file (if status file doesn't exist)
        params_file = task_dir / "parameters.json"
        parameters = {}
        if params_file.exists():
            try:
                with open(params_file, 'r') as f:
                    parameters = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read task parameters file: {e}")
        
        # Return basic information
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": "unknown",
                "parameters": parameters,
                "results_dir": str(task_dir)
            }
        }


async def execute_inference_task(task_id: str, params: Dict[str, Any], task_dir: FilePath):
    """
    Execute inference task
    
    Args:
        task_id: Task ID
        params: Inference parameters
        task_dir: Task output directory
    """
    start_time = time.time()
    
    # Update task status
    running_tasks[task_id]["status"] = "running"
    
    try:
        # Execute inference function in thread pool
        def run_process():
            try:
                # 使用新的参数格式调用推理函数
                return InferenceService.run_inference(
                    model_path=params.get('model_path', 'best.pt'),
                    data_dir=params.get('data_dir', 'rainfall_20221024'),
                    device=params.get('device', 'cuda:0' if torch.cuda.is_available() else 'cpu'),
                    start_tmp=params.get('start_tmp', None),
                    output_dir=task_dir,
                    pred_length=params.get('pred_length', 48)
                )
            except Exception as e:
                logger.error(f"Inference execution failed: {str(e)}")
                return {
                    "success": False,
                    "message": f"Inference execution failed: {str(e)}"
                }
        
        # Execute in thread pool
        result = await run_in_threadpool(run_process)
        
        # Calculate execution time
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Determine task status
        status = "completed" if result.get("success", False) else "failed"
        
        # Update task status
        if task_id in running_tasks:
            running_tasks[task_id]["status"] = status
        
        # Save status information
        status_info = {
            "task_id": task_id,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_time": elapsed_time,
            "parameters": params,
            "results": result.get("results", {})
        }
        
        with open(task_dir / "status.json", 'w') as f:
            json.dump(status_info, f, indent=2)
            
        logger.info(f"Inference task {task_id} completed, status: {status}, time: {elapsed_time:.2f} seconds")
        
    except Exception as e:
        # Record error
        logger.error(f"Failed to execute inference task {task_id}: {str(e)}")
        
        # Update status
        if task_id in running_tasks:
            running_tasks[task_id]["status"] = "failed"
        
        # Save error information
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        error_info = {
            "task_id": task_id,
            "status": "failed",
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_time": elapsed_time,
            "error": str(e),
            "parameters": params
        }
        
        with open(task_dir / "status.json", 'w') as f:
            json.dump(error_info, f, indent=2)
    
    finally:
        # Remove running task
        if task_id in running_tasks:
            del running_tasks[task_id] 
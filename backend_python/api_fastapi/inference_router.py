#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Inference API (FastAPI version)

Provides HTTP API for machine learning model inference, supporting water depth prediction
and flood inundation analysis.
"""

from fastapi import APIRouter, Body, HTTPException, status, BackgroundTasks, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional, Set
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
RAINFALL_DATA_DIR = BASE_DIR / "data/rainfall"

# Ensure inference results directory exists
INFERENCE_RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Track running inference tasks
running_tasks = {}

# Task execution lock to ensure only one task runs at a time
task_lock = asyncio.Lock()

# Store active WebSocket connections by task_id
active_connections: Dict[str, Set[WebSocket]] = {}

# WebSocket manager
class WebSocketManager:
    @staticmethod
    async def connect(websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in active_connections:
            active_connections[task_id] = set()
        active_connections[task_id].add(websocket)
    
    @staticmethod
    def disconnect(websocket: WebSocket, task_id: str):
        if task_id in active_connections:
            active_connections[task_id].discard(websocket)
            if not active_connections[task_id]:
                del active_connections[task_id]
    
    @staticmethod
    async def broadcast_progress(task_id: str, data: Dict[str, Any]):
        if task_id in active_connections:
            disconnected_ws = set()
            for websocket in active_connections[task_id]:
                try:
                    await websocket.send_json(data)
                except WebSocketDisconnect:
                    disconnected_ws.add(websocket)
                except Exception as e:
                    logger.error(f"Error sending to WebSocket: {str(e)}")
                    disconnected_ws.add(websocket)
            
            # Remove disconnected WebSockets
            for ws in disconnected_ws:
                WebSocketManager.disconnect(ws, task_id)


class InferenceAPI:
    """API methods for inference operations"""
    
    # Helper method to check if any inference task is running
    @staticmethod
    def is_any_task_running() -> bool:
        """Check if any inference task is currently running"""
        for task_id, task_info in running_tasks.items():
            if task_info.get("status") == "running":
                return True
        return False
    
    # WebSocket endpoint for progress updates
    @staticmethod
    @router.websocket("/ws/progress/{task_id}")
    async def websocket_progress(websocket: WebSocket, task_id: str):
        """WebSocket endpoint for inference progress updates"""
        await WebSocketManager.connect(websocket, task_id)
        try:
            # Send initial status if task exists
            if task_id in running_tasks:
                task_info = running_tasks[task_id]
                await websocket.send_json({
                    "type": "status",
                    "task_id": task_id,
                    "status": task_info.get("status", "unknown"),
                    "progress": task_info.get("progress", 0),
                    "stage": task_info.get("stage", ""),
                    "message": task_info.get("message", ""),
                    "elapsed_time": time.time() - task_info.get("start_time", time.time())
                })
            
            # Keep connection open
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            WebSocketManager.disconnect(websocket, task_id)
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            WebSocketManager.disconnect(websocket, task_id)
    
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
        
        # Check if any task is currently running
        any_task_running = InferenceAPI.is_any_task_running()
        
        status_info = {
            "model_path": str(model_path),
            "model_exists": model_exists,
            "data_files": data_files,
            "rainfall_data_exists": rainfall_data_exists,
            "running_tasks": len(running_tasks),
            "task_ids": list(running_tasks.keys()),
            "any_task_running": any_task_running,
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
    @router.get("/cuda_info", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def get_cuda_info():
        """Get information about available CUDA devices and their utilization"""
        cuda_available = torch.cuda.is_available()
        device_count = torch.cuda.device_count() if cuda_available else 0
        
        devices_info = []
        
        if cuda_available:
            for i in range(device_count):
                # Get basic device information
                device_name = torch.cuda.get_device_name(i)
                device_props = torch.cuda.get_device_properties(i)
                total_memory = device_props.total_memory / (1024 ** 3)  # Convert to GB
                
                # Get memory usage
                torch.cuda.set_device(i)
                reserved_memory = torch.cuda.memory_reserved() / (1024 ** 3)  # Convert to GB
                allocated_memory = torch.cuda.memory_allocated() / (1024 ** 3)  # Convert to GB
                free_memory = total_memory - reserved_memory
                
                # Calculate utilization percentages
                reserved_percent = (reserved_memory / total_memory) * 100 if total_memory > 0 else 0
                allocated_percent = (allocated_memory / total_memory) * 100 if total_memory > 0 else 0
                
                devices_info.append({
                    "device_id": i,
                    "device_name": device_name,
                    "compute_capability": f"{device_props.major}.{device_props.minor}",
                    "total_memory_gb": round(total_memory, 2),
                    "reserved_memory_gb": round(reserved_memory, 2),
                    "allocated_memory_gb": round(allocated_memory, 2),
                    "free_memory_gb": round(free_memory, 2),
                    "reserved_percent": round(reserved_percent, 2),
                    "allocated_percent": round(allocated_percent, 2),
                    "multiprocessor_count": device_props.multi_processor_count,
                    "current_device": i == torch.cuda.current_device()
                })
        
        return {
            "success": True,
            "data": {
                "cuda_available": cuda_available,
                "device_count": device_count,
                "devices": devices_info,
                "current_device": torch.cuda.current_device() if cuda_available else None
            }
        }
    
    @staticmethod
    @router.get("/rainfall_files", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def get_rainfall_files():
        """Get a list of available rainfall data files (NC files)"""
        rainfall_files = []
        
        # Check if rainfall data directory exists
        if RAINFALL_DATA_DIR.exists() and RAINFALL_DATA_DIR.is_dir():
            try:
                # List all NC files in the rainfall data directory
                for item in RAINFALL_DATA_DIR.glob('**/*.nc'):
                    if item.is_file() and not item.name.startswith('.'):
                        # Get file stats
                        file_info = {
                            "name": item.name,
                            "path": str(item.relative_to(BASE_DIR)),
                            "size_mb": round(item.stat().st_size / (1024 * 1024), 2),
                            "last_modified": time.ctime(item.stat().st_mtime)
                        }
                        rainfall_files.append(file_info)
                
                # Sort files by name
                rainfall_files.sort(key=lambda x: x["name"])
                
            except Exception as e:
                logger.error(f"Error reading rainfall files: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error reading rainfall files: {str(e)}"
                )
        else:
            logger.warning(f"Rainfall data directory not found: {RAINFALL_DATA_DIR}")
        
        return {
            "success": True,
            "data": {
                "rainfall_files": rainfall_files,
                "total_count": len(rainfall_files),
                "base_path": str(RAINFALL_DATA_DIR)
            }
        }
    
    @staticmethod
    @router.post("/run", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def run_inference_task(
        background_tasks: BackgroundTasks,
        model_path: str = Body('best.pt', description="Model file path"),
        data_dir: str = Body(None, description="Input data filename or full NC file path"),
        device: str = Body(None, description="Computing device (default: cuda:0 or cpu)"),
        pred_length: int = Body(48, description="Prediction timesteps")
    ):
        """Run inference task"""
        # Check if any task is already running
        if InferenceAPI.is_any_task_running():
            return {
                "success": False,
                "error": "Another inference task is currently running. Please wait for it to complete before starting a new one.",
                "data": {
                    "running_tasks": [
                        {"task_id": task_id, "status": task_info.get("status"), "start_time": task_info.get("start_time")} 
                        for task_id, task_info in running_tasks.items() 
                        if task_info.get("status") == "running"
                    ]
                }
            }
        
        # Check parameters
        if not model_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model path is required"
            )
        
        if not data_dir:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data file/directory is required"
            )
        
        # Use CPU if device not specified
        if not device:
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        
        # Convert parameters
        try:
            pred_length = int(pred_length)
            if pred_length <= 0:
                pred_length = 48
        except (ValueError, TypeError):
            pred_length = 48
        
        # Log parameters
        parameters = {
            "model_path": model_path,
            "data_dir": data_dir,
            "device": device,
            "pred_length": pred_length
        }
        
        # Validate model file
        model_full_path = FilePath(MODEL_DIR) / model_path
        if not model_full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model file does not exist: {model_full_path}"
            )
        
        # Validate data file/directory
        # Check if data_dir is a full path or just a filename
        data_path = FilePath(data_dir)
        if data_path.is_absolute():
            # Full path provided
            if not data_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Data file does not exist: {data_path}"
                )
        else:
            # Just a filename, check in the rainfall directory
            data_file_path = RAINFALL_DATA_DIR / data_dir
            if not data_file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Data file does not exist: {data_file_path}"
                )
            # Update data_dir to use the full path
            data_dir = str(data_file_path)
        
        # Generate task ID
        task_id = f"inference_{int(time.time())}_{os.path.basename(data_dir).replace('.nc', '')}"
        
        # Prepare output directory
        task_dir = INFERENCE_RESULTS_DIR / task_id
        task_dir.mkdir(exist_ok=True)
        
        # Save parameters to JSON file
        params_file = task_dir / "parameters.json"
        with open(params_file, 'w') as f:
            json.dump(parameters, f, indent=2)
        
        # Add to background tasks with lock to ensure only one runs at a time
        background_tasks.add_task(
            execute_inference_task_with_lock,
            task_id=task_id,
            model_path=model_path,
            data_dir=data_dir,
            device=device,
            pred_length=pred_length,
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

    @staticmethod
    @router.post("/tasks/{task_id}/cancel", response_model=Dict[str, Any])
    @async_handle_exceptions
    async def cancel_inference_task(task_id: str = Path(..., description="Task ID")):
        """Cancel a running inference task"""
        if task_id not in running_tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found"
            )
        
        task_info = running_tasks[task_id]
        if task_info.get("status") != "running":
            return {
                "success": False,
                "message": f"Task {task_id} is not running (status: {task_info.get('status')})"
            }
        
        logger.info(f"Canceling task {task_id}")
        
        # 获取任务进程句柄（如果存在）
        process_handle = task_info.get("process_handle")
        if process_handle:
            try:
                # 尝试终止进程
                logger.info(f"Attempting to terminate process for task {task_id}")
                process_handle.terminate()
                
                # 给进程一些时间来清理
                await asyncio.sleep(1)
                
                # 如果进程还在运行，强制终止
                if process_handle.is_alive():
                    logger.warning(f"Process for task {task_id} did not terminate gracefully, killing it")
                    process_handle.kill()
            except Exception as e:
                logger.error(f"Error terminating process for task {task_id}: {str(e)}")
        
        # 取消进度队列任务（如果存在）
        progress_task = task_info.get("progress_task")
        if progress_task and not progress_task.done():
            try:
                logger.info(f"Cancelling progress task for {task_id}")
                progress_task.cancel()
            except Exception as e:
                logger.error(f"Error cancelling progress task: {str(e)}")
        
        # Mark task as cancelled
        task_info["status"] = "cancelled"
        task_info["stage"] = "cancelled"
        task_info["message"] = "Task cancelled by user"
        task_info["end_time"] = time.time()
        task_info["elapsed_time"] = task_info["end_time"] - task_info["start_time"]
        
        # Notify any connected websockets
        await WebSocketManager.broadcast_progress(task_id, {
            "type": "status",
            "task_id": task_id,
            "status": "cancelled",
            "progress": task_info.get("progress", 0),
            "stage": "cancelled",
            "message": "Task cancelled by user",
            "elapsed_time": task_info["elapsed_time"]
        })
        
        # Save status to file
        task_dir = INFERENCE_RESULTS_DIR / task_id
        if task_dir.exists():
            status_info = {
                "task_id": task_id,
                "status": "cancelled",
                "start_time": task_info["start_time"],
                "end_time": task_info["end_time"],
                "elapsed_time": task_info["elapsed_time"],
                "parameters": task_info.get("parameters", {}),
                "message": "Task cancelled by user"
            }
            
            with open(task_dir / "status.json", 'w') as f:
                json.dump(status_info, f, indent=2)
        
        return {
            "success": True,
            "message": f"Task {task_id} has been cancelled",
            "data": {
                "task_id": task_id,
                "status": "cancelled",
                "elapsed_time": task_info["elapsed_time"]
            }
        }


# Wrapper function to execute inference task with lock
async def execute_inference_task_with_lock(
    task_id: str, 
    model_path: str, 
    data_dir: str, 
    device: str, 
    pred_length: int, 
    task_dir: FilePath
):
    """
    Execute inference task with a lock to ensure only one task runs at a time
    
    Args:
        task_id: Task ID
        model_path: Model file path
        data_dir: Input data filename or full NC file path
        device: Computing device
        pred_length: Prediction timesteps
        task_dir: Task output directory
    """
    async with task_lock:
        await execute_inference_task(
            task_id=task_id,
            model_path=model_path,
            data_dir=data_dir,
            device=device,
            pred_length=pred_length,
            task_dir=task_dir
        )

# Original execute_inference_task function
async def execute_inference_task(
    task_id: str, 
    model_path: str, 
    data_dir: str, 
    device: str, 
    pred_length: int, 
    task_dir: FilePath
):
    """
    Execute inference task
    
    Args:
        task_id: Task ID
        model_path: Model file path
        data_dir: Input data filename or full NC file path
        device: Computing device
        pred_length: Prediction timesteps
        task_dir: Task output directory
    """
    start_time = time.time()
    
    # Update task status
    running_tasks[task_id] = {
        "status": "running",
        "start_time": start_time,
        "progress": 0,
        "stage": "initialization",
        "message": "Task started"
    }
    
    # Build parameter dictionary for recording
    params = {
        'model_path': model_path,
        'data_dir': data_dir,
        'device': device,
        'pred_length': pred_length
    }
    
    # Create a thread-safe queue for progress updates
    from queue import Queue
    progress_queue = Queue()
    
    # Create a thread to broadcast progress updates
    def sync_progress_callback(stage, progress, message):
        """Thread-safe progress callback that adds updates to the queue"""
        progress_queue.put((stage, progress, message))
    
    # Background task to process progress updates
    async def process_progress_queue():
        """Process progress updates from the queue and broadcast to WebSocket clients"""
        while task_id in running_tasks and running_tasks[task_id]["status"] == "running":
            # Check if there are updates in the queue
            if not progress_queue.empty():
                try:
                    # Get an update from the queue
                    stage, progress, message = progress_queue.get_nowait()
                    
                    # Update task info
                    if task_id in running_tasks:
                        running_tasks[task_id].update({
                            "progress": progress,
                            "stage": stage,
                            "message": message,
                            "elapsed_time": time.time() - start_time
                        })
                    
                    # Broadcast progress update
                    await WebSocketManager.broadcast_progress(task_id, {
                        "type": "progress",
                        "task_id": task_id,
                        "status": running_tasks[task_id]["status"],
                        "progress": progress,
                        "stage": stage,
                        "message": message,
                        "elapsed_time": time.time() - start_time
                    })
                except Exception as e:
                    logger.error(f"Error processing progress update: {str(e)}")
            
            # Sleep a short time before checking the queue again
            await asyncio.sleep(0.1)
    
    # Start the progress queue processing task
    progress_task = asyncio.create_task(process_progress_queue())

    # 将进度任务保存到running_tasks字典中
    if task_id in running_tasks:
        running_tasks[task_id]["progress_task"] = progress_task

    try:
        # Execute inference function in a thread pool
        def run_process():
            try:
                # Call inference function with progress callback
                inference_service = InferenceService()
                # 保存进程引用到running_tasks
                if task_id in running_tasks:
                    running_tasks[task_id]["process_handle"] = inference_service
                
                return inference_service.run_inference(
                    model_path=model_path,
                    data_dir=data_dir,
                    device=device,
                    start_tmp=None,  # Use auto-generated timestamp
                    output_dir=task_dir,
                    pred_length=pred_length,
                    progress_callback=sync_progress_callback
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
            if status == "completed":
                running_tasks[task_id]["progress"] = 100
                running_tasks[task_id]["stage"] = "completion"
                running_tasks[task_id]["message"] = "Task completed successfully"
            else:
                running_tasks[task_id]["stage"] = "error"
                running_tasks[task_id]["message"] = result.get("message", "Unknown error")
        
        # Send final status update
        await WebSocketManager.broadcast_progress(task_id, {
            "type": "status",
            "task_id": task_id,
            "status": status,
            "progress": 100 if status == "completed" else 0,
            "stage": "completion" if status == "completed" else "error",
            "message": "Task completed successfully" if status == "completed" else result.get("message", "Unknown error"),
            "elapsed_time": elapsed_time,
            "results": result.get("results", {})
        })
        
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
            
        logger.info(f"Inference task {task_id} completed, status: {status}, duration: {elapsed_time:.2f} seconds")
        
    except Exception as e:
        # Log error
        logger.error(f"Error executing inference task {task_id}: {str(e)}")
        
        # Update status
        if task_id in running_tasks:
            running_tasks[task_id]["status"] = "failed"
            running_tasks[task_id]["stage"] = "error"
            running_tasks[task_id]["message"] = str(e)
        
        # Send error status update
        await WebSocketManager.broadcast_progress(task_id, {
            "type": "error",
            "task_id": task_id,
            "status": "failed",
            "message": str(e),
            "elapsed_time": time.time() - start_time
        })
        
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
        # Cancel the progress queue processing task
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
        # Wait a while before removing the task to allow clients to get the final status
        await asyncio.sleep(60)
        # Remove running task
        if task_id in running_tasks:
            del running_tasks[task_id] 
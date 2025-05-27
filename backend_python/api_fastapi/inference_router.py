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
RAINFALL_DATA_DIR = BASE_DIR / "data/rainfall"

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
        model_path: str = Body('best.pt', description="模型文件路径"),
        data_dir: str = Body(None, description="输入数据文件名"),
        device: str = Body(None, description="计算设备 (默认: cuda:0 或 cpu)"),
        pred_length: int = Body(48, description="预测时间步数")
    ):
        """
        运行推理任务
        
        Args:
            background_tasks: 后台任务管理器
            model_path: 模型文件路径 (默认: best.pt)
            data_dir: 输入数据文件名 (默认: 自动选择可用的NC文件)
            device: 计算设备 (默认: cuda:0 或 cpu)
            pred_length: 预测时间步数 (默认: 48)
        
        Returns:
            任务ID和状态信息
        """
        # 使用默认设备如果未指定
        if device is None:
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            
        # 如果没有指定数据文件，查找可用的NC文件
        if data_dir is None:
            try:
                # 查找第一个可用的NC文件
                nc_files = list(RAINFALL_DATA_DIR.glob('**/*.nc'))
                if nc_files:
                    # 选择第一个NC文件
                    data_dir = nc_files[0].name
                else:
                    # 如果没有找到NC文件，使用默认值
                    data_dir = 'rainfall_20221024.nc'
            except Exception as e:
                logger.error(f"自动查找NC文件失败: {str(e)}")
                data_dir = 'rainfall_20221024.nc'
        
        # 构建参数字典用于日志记录和保存
        parameters = {
            'model_path': model_path,
            'data_dir': data_dir,
            'device': device,
            'pred_length': pred_length
        }
        
        logger.info(f"准备开始推理任务，参数: {parameters}")
        
        # 验证模型文件
        model_full_path = FilePath(MODEL_DIR) / model_path
        if not model_full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"模型文件不存在: {model_full_path}"
            )
        
        # 验证数据文件
        data_file_path = RAINFALL_DATA_DIR / data_dir
        if not data_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据文件不存在: {data_file_path}"
            )
        
        # 生成任务ID
        task_id = f"inference_{int(time.time())}_{data_dir.replace('.nc', '')}"
        
        # 准备输出目录
        task_dir = INFERENCE_RESULTS_DIR / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 保存参数到JSON文件
        params_file = task_dir / "parameters.json"
        with open(params_file, 'w') as f:
            json.dump(parameters, f, indent=2)
        
        # 添加到后台任务
        background_tasks.add_task(
            execute_inference_task,
            task_id=task_id,
            model_path=model_path,
            data_dir=data_dir,
            device=device,
            pred_length=pred_length,
            task_dir=task_dir
        )
        
        # 标记任务为运行中
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
                "message": "推理任务已开始"
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


async def execute_inference_task(
    task_id: str, 
    model_path: str, 
    data_dir: str, 
    device: str, 
    pred_length: int, 
    task_dir: FilePath
):
    """
    执行推理任务
    
    Args:
        task_id: 任务ID
        model_path: 模型文件路径
        data_dir: 输入数据文件名
        device: 计算设备
        pred_length: 预测时间步数
        task_dir: 任务输出目录
    """
    start_time = time.time()
    
    # 更新任务状态
    running_tasks[task_id]["status"] = "running"
    
    # 构建参数字典用于记录
    params = {
        'model_path': model_path,
        'data_dir': data_dir,
        'device': device,
        'pred_length': pred_length
    }
    
    # 完整的数据文件路径
    data_file_path = str(RAINFALL_DATA_DIR / data_dir)
    
    try:
        # 在线程池中执行推理函数
        def run_process():
            try:
                # 使用新的参数格式调用推理函数
                return InferenceService.run_inference(
                    model_path=model_path,
                    data_file=data_file_path,  # 使用完整的文件路径
                    device=device,
                    start_tmp=None,  # 使用默认生成的时间戳
                    output_dir=task_dir,
                    pred_length=pred_length
                )
            except Exception as e:
                logger.error(f"推理执行失败: {str(e)}")
                return {
                    "success": False,
                    "message": f"推理执行失败: {str(e)}"
                }
        
        # 在线程池中执行
        result = await run_in_threadpool(run_process)
        
        # 计算执行时间
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 确定任务状态
        status = "completed" if result.get("success", False) else "failed"
        
        # 更新任务状态
        if task_id in running_tasks:
            running_tasks[task_id]["status"] = status
        
        # 保存状态信息
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
            
        logger.info(f"推理任务 {task_id} 已完成，状态: {status}，用时: {elapsed_time:.2f} 秒")
        
    except Exception as e:
        # 记录错误
        logger.error(f"执行推理任务 {task_id} 失败: {str(e)}")
        
        # 更新状态
        if task_id in running_tasks:
            running_tasks[task_id]["status"] = "failed"
        
        # 保存错误信息
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
        # 移除运行中的任务
        if task_id in running_tasks:
            del running_tasks[task_id] 
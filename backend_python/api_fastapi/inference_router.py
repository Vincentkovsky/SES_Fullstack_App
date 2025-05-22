#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
推理API (FastAPI版本)

提供机器学习模型推理的HTTP API，支持水深度预测和洪水淹没范围分析。
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

# 导入自定义工具
from core.fastapi_helpers import async_handle_exceptions
from core.config import Config
from services.inference_service import run_inference, get_latest_inference_dir, execute_inference_script
from ai_inference.model import get_model_path, get_data_file, list_available_files, MODEL_DIR

# 设置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/inference")

# 基础路径
BASE_DIR = FilePath(__file__).parent.parent
INFERENCE_RESULTS_DIR = BASE_DIR / "data/inference_results"

# 确保推理结果目录存在
INFERENCE_RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# 跟踪正在运行的推理任务
running_tasks = {}

@router.get("/status", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_inference_status():
    """获取推理服务状态"""
    # 检查必要的模型文件是否存在
    model_path = FilePath(get_model_path())
    model_exists = model_path.exists()
    
    # 检查必要的数据文件
    data_files = {
        "dem_embeddings": FilePath(get_data_file("dem_embeddings")).exists(),
        "side_lengths": FilePath(get_data_file("side_lengths")).exists(),
        "square_centers": FilePath(get_data_file("square_centers")).exists(),
        "dem_min_tensor": FilePath(get_data_file("dem_min_tensor")).exists(),
        "water_level_min": FilePath(get_data_file("water_level_min")).exists(),
        "dem_file": FilePath(get_data_file("dem_file")).exists(),
        "gridadmin_file": FilePath(get_data_file("gridadmin_file")).exists(),
    }
    
    # 检查数据目录
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

@router.get("/available_data", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_available_data():
    """获取可用的数据文件和模型"""
    data_files = list_available_files()
    data_files = {k: FilePath(v).exists() for k, v in data_files.items()}
    
    return {
        "success": True,
        "data": {
            "available_files": data_files
        }
    }

@router.post("/run", response_model=Dict[str, Any])
@async_handle_exceptions
async def run_inference_task(
    background_tasks: BackgroundTasks,
    parameters: Dict[str, Any] = Body(..., description="推理参数")
):
    """
    运行推理任务
    
    Args:
        background_tasks: 后台任务管理器
        parameters: 推理参数字典
    
    Returns:
        任务ID和状态信息
    """
    logger.info(f"准备启动推理任务，参数: {parameters}")
    
    # 验证必要的模型和数据文件是否存在
    model_path = parameters.get('model_path', 'best.pt')
    model_full_path = FilePath(MODEL_DIR) / model_path
    if not model_full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"模型文件不存在: {model_full_path}"
        )
    
    # 验证数据目录是否存在
    data_dir = parameters.get('data_dir', 'rainfall_20221024')
    data_dir_path = FilePath(MODEL_DIR) / data_dir
    if not data_dir_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据目录不存在: {data_dir_path}"
        )
    
    # 生成任务ID
    task_id = f"inference_{int(time.time())}_{parameters.get('data_dir', 'default')}"
    
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
        params=parameters,
        task_dir=task_dir
    )
    
    # 将任务标记为运行中
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
            "message": "推理任务已启动"
        }
    }

@router.get("/tasks", response_model=Dict[str, Any])
@async_handle_exceptions
async def list_inference_tasks():
    """获取所有推理任务列表"""
    tasks = []
    
    # 收集运行中的任务
    for task_id, task_info in running_tasks.items():
        tasks.append({
            "task_id": task_id,
            "status": task_info["status"],
            "start_time": task_info["start_time"],
            "elapsed_time": time.time() - task_info["start_time"],
            "results_dir": task_info.get("results_dir")
        })
    
    # 查找已完成的任务
    completed_dirs = [d for d in INFERENCE_RESULTS_DIR.iterdir() if d.is_dir()]
    for task_dir in completed_dirs:
        task_id = task_dir.name
        
        # 跳过运行中的任务（已经添加过）
        if task_id in running_tasks:
            continue
        
        # 检查任务状态文件
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
                logger.error(f"读取任务状态文件失败: {e}")
                
                # 没有有效的状态文件但目录存在，可能是之前的任务
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

@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_task_status(task_id: str = Path(..., description="任务ID")):
    """获取特定任务的状态"""
    # 检查是否为运行中的任务
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
    
    # 检查已完成任务目录
    task_dir = INFERENCE_RESULTS_DIR / task_id
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到任务: {task_id}"
        )
    
    # 读取任务状态
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
            logger.error(f"读取任务状态文件失败: {e}")
    
    # 读取参数文件（如果状态文件不存在）
    params_file = task_dir / "parameters.json"
    parameters = {}
    if params_file.exists():
        try:
            with open(params_file, 'r') as f:
                parameters = json.load(f)
        except Exception as e:
            logger.error(f"读取任务参数文件失败: {e}")
    
    # 返回基本信息
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
    执行推理任务
    
    Args:
        task_id: 任务ID
        params: 推理参数
        task_dir: 任务输出目录
    """
    start_time = time.time()
    
    # 更新任务状态
    running_tasks[task_id]["status"] = "running"
    
    try:
        # 在线程池中执行推理函数
        def run_process():
            try:
                # 直接调用推理函数
                return run_inference(params, task_dir)
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
            
        logger.info(f"推理任务 {task_id} 已完成，状态: {status}，耗时: {elapsed_time:.2f}秒")
        
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
        # 移除运行中任务
        if task_id in running_tasks:
            del running_tasks[task_id] 
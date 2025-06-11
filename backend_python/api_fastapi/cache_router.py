#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
缓存管理API (FastAPI版本)

提供缓存查询、删除和清理功能的API接口。
"""

from fastapi import APIRouter, Path, HTTPException, status, BackgroundTasks
from typing import Dict, Any, List, Optional
import logging
import os
import json
import shutil
from pathlib import Path as FilePath
import time
from datetime import datetime

# 导入自定义工具
from core.fastapi_helpers import async_handle_exceptions
from core.config import Config

# 导入各API模块的缓存
from .gauging_router import gauge_data_cache
from .raster_router import file_modification_times

# 设置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/cache")

# 基础路径
BASE_DIR = FilePath(__file__).parent.parent
CACHE_DIR = BASE_DIR / "data/cache"

# 确保缓存目录存在
CACHE_DIR.mkdir(exist_ok=True, parents=True)

@router.get("/info", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_cache_info():
    """获取所有缓存信息"""
    try:
        # 收集内存缓存信息
        memory_cache = {
            "gauging": {
                "gauge_data": len(gauge_data_cache)
            },
            "raster": {
                "files": len(file_modification_times)
            }
        }
        
        # 收集磁盘缓存信息
        disk_cache = {}
        
        # 检查各种缓存目录
        cache_dirs = [
            ("tiles", BASE_DIR / "data/tiles"),
            ("gauge_data", BASE_DIR / "data/gauge_data")
        ]
        
        for name, path in cache_dirs:
            if path.exists():
                dir_size = sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())
                file_count = sum(1 for _ in path.glob('**/*') if _.is_file())
                
                disk_cache[name] = {
                    "path": str(path),
                    "size_bytes": dir_size,
                    "size_mb": dir_size / (1024 * 1024),
                    "file_count": file_count
                }
        
        return {
            "success": True,
            "data": {
                "memory_cache": memory_cache,
                "disk_cache": disk_cache,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"获取缓存信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取缓存信息失败: {str(e)}"
        )

@router.delete("/clear", response_model=Dict[str, Any])
@async_handle_exceptions
async def clear_all_cache(background_tasks: BackgroundTasks):
    """清除所有缓存"""
    try:
        # 清除内存缓存
        gauge_data_cache.clear()
        file_modification_times.clear()
        
        # 在后台清除磁盘缓存
        background_tasks.add_task(clear_disk_cache)
        
        return {
            "success": True,
            "message": "缓存清除已开始，磁盘缓存将在后台清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清除缓存失败: {str(e)}"
        )

@router.delete("/tiles", response_model=Dict[str, Any])
@async_handle_exceptions
async def clear_tile_cache():
    """清除瓦片缓存"""
    try:
        tile_cache_dir = BASE_DIR / "data/tiles"
        
        if tile_cache_dir.exists():
            # 删除瓦片缓存目录下的所有内容
            for item in tile_cache_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            
            logger.info("瓦片缓存已清除")
        
        return {
            "success": True,
            "message": "瓦片缓存已清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清除瓦片缓存失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清除瓦片缓存失败: {str(e)}"
        )

@router.delete("/gauging", response_model=Dict[str, Any])
@async_handle_exceptions
async def clear_gauging_cache():
    """清除测量站缓存"""
    try:
        # 清除内存缓存
        gauge_data_cache.clear()
        
        # 清除缓存文件（如果有的话）
        gauging_cache_dir = BASE_DIR / "data/gauge_data"
        
        if gauging_cache_dir.exists():
            # 保留CSV数据文件，删除其他缓存文件
            for item in gauging_cache_dir.iterdir():
                if item.is_file() and not item.name.endswith(".csv"):
                    item.unlink()
            
            logger.info("水位测量缓存已清除")
        
        return {
            "success": True,
            "message": "水位测量缓存已清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清除水位测量缓存失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清除水位测量缓存失败: {str(e)}"
        )

async def clear_disk_cache():
    """清除所有磁盘缓存"""
    try:
        # 清除瓦片缓存
        tile_cache_dir = BASE_DIR / "data/tiles"
        if tile_cache_dir.exists():
            shutil.rmtree(tile_cache_dir)
            tile_cache_dir.mkdir(exist_ok=True)
        
        # 清除水位测量缓存（保留CSV数据文件）
        gauging_cache_dir = BASE_DIR / "data/gauge_data"
        if gauging_cache_dir.exists():
            for item in gauging_cache_dir.iterdir():
                if item.is_file() and not item.name.endswith(".csv"):
                    item.unlink()
        
        logger.info("所有磁盘缓存已清除")
    except Exception as e:
        logger.error(f"清除磁盘缓存失败: {str(e)}")
        
@router.post("/prefetch", response_model=Dict[str, Any])
@async_handle_exceptions
async def prefetch_cache(background_tasks: BackgroundTasks):
    """预取常用缓存数据"""
    try:
        # 添加后台任务
        background_tasks.add_task(prefetch_data)
        
        return {
            "success": True,
            "message": "缓存预取已开始",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"启动缓存预取失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动缓存预取失败: {str(e)}"
        )
        
async def prefetch_data():
    """在后台预取常用数据"""
    try:
        logger.info("开始预取缓存数据")
        
        # 这里可以添加各种预取任务
        # 例如预取测量站列表、常用瓦片等
        
        logger.info("缓存预取完成")
    except Exception as e:
        logger.error(f"缓存预取失败: {str(e)}") 
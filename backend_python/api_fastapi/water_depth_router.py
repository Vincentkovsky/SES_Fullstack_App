#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度API模块 (FastAPI版本)
用于计算和获取基于DEM和水位面的水深度数据
"""

from fastapi import APIRouter, HTTPException, status
from fastapi import Path as FastAPIPath
from fastapi import Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import os
import logging
import json
from pathlib import Path
import numpy as np
from time import time
import asyncio
from starlette.concurrency import run_in_threadpool
from functools import lru_cache

# 导入工具库
from utils.water_depth_calculator import (
    get_dem_value, 
    get_closest_node_level, 
    calculate_water_depth
)

# 创建路由器
router = APIRouter(prefix="/api")

# 设置日志
logger = logging.getLogger(__name__)

# 基础路径
BASE_DIR = Path(__file__).parent.parent
DEM_FILE = str(BASE_DIR / "data/dem/dem.tif")

# 文件修改时间缓存
file_modification_times = {}

def get_file_hash(filepath: str) -> str:
    """获取文件的哈希值，用于缓存键"""
    try:
        mtime = os.path.getmtime(filepath)
        current_mtime = file_modification_times.get(filepath)
        
        if current_mtime != mtime:
            file_modification_times[filepath] = mtime
            get_cached_water_depth.cache_clear()  # 清除水深度缓存
            
        return f"{filepath}_{mtime}"
    except:
        return filepath

@lru_cache(maxsize=1000)
def get_cached_water_depth(dem_file: str, nc_file: str, lat: float, lng: float, timestamp: str) -> dict:
    """获取缓存的水深度数据"""
    # 检查文件修改时间并更新缓存键
    _ = get_file_hash(dem_file)
    if nc_file:
        _ = get_file_hash(nc_file)
    
    try:
        # 获取DEM值
        dem_value = get_dem_value(dem_file, lat, lng)
        
        if dem_value is None:
            return {
                "success": False,
                "error": "无法获取DEM值，请检查坐标是否在有效范围内"
            }
        
        # 获取水位面高度
        water_level = get_closest_node_level(nc_file, lat, lng, timestamp)
        
        if water_level is None:
            return {
                "success": False,
                "error": "无法获取水位面高度，请检查NetCDF文件和时间戳"
            }
        
        # 计算水深度
        water_depth = calculate_water_depth(dem_value, water_level)
        
        return {
            "success": True,
            "data": {
                "dem_value": float(dem_value),
                "water_level": float(water_level),
                "water_depth": float(water_depth),
                "lat": lat,
                "lng": lng,
                "timestamp": timestamp
            }
        }
    
    except Exception as e:
        logger.error(f"水深度计算失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"水深度计算失败: {str(e)}"
        }

@router.get("/water-depth", response_model=Dict[str, Any])
async def get_water_depth(
    lat: float = Query(..., description="纬度", gt=-90, lt=90),
    lng: float = Query(..., description="经度", gt=-180, lt=180),
    nc_file: Optional[str] = Query(None, description="NetCDF结果文件路径"),
    timestamp: Optional[str] = Query(None, description="时间戳")
):
    """获取指定坐标的水深度信息"""
    try:
        start_time = time()
        
        result = await run_in_threadpool(
            get_cached_water_depth,
            DEM_FILE,
            nc_file,
            lat,
            lng,
            timestamp
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        result["processing_time_ms"] = int((time() - start_time) * 1000)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/water-depth/batch", response_model=Dict[str, Any])
async def batch_water_depth(
    points: str = Query(..., description="JSON格式的点列表"),
    nc_file: Optional[str] = Query(None, description="NetCDF结果文件路径"),
    timestamp: Optional[str] = Query(None, description="时间戳")
):
    """批量获取多个点的水深度信息"""
    try:
        start_time = time()
        
        # 解析点列表
        try:
            point_list = json.loads(points)
            if not isinstance(point_list, list):
                raise ValueError("points参数必须是有效的JSON数组")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的JSON格式点列表"
            )
        
        if not point_list:
            return {
                "success": True,
                "data": [],
                "processing_time_ms": 0
            }
        
        # 验证点列表格式
        for point in point_list:
            if not isinstance(point, dict) or 'lat' not in point or 'lng' not in point:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="点列表格式无效，每个点必须包含lat和lng字段"
                )
        
        # 异步处理每个点
        async def process_point(point):
            result = await run_in_threadpool(
                get_cached_water_depth,
                DEM_FILE,
                nc_file,
                point['lat'],
                point['lng'],
                timestamp
            )
            
            if result["success"]:
                return result["data"]
            else:
                return {
                    "lat": point['lat'],
                    "lng": point['lng'],
                    "dem_value": None,
                    "water_level": None,
                    "water_depth": None,
                    "error": result["error"]
                }
        
        # 并行处理所有点
        tasks = [process_point(point) for point in point_list]
        results = await asyncio.gather(*tasks)
        
        # 准备响应
        response_data = {
            "success": True,
            "data": results,
            "processing_time_ms": int((time() - start_time) * 1000)
        }
        
        logger.info(f"批量水深度计算完成，处理了{len(results)}个点，耗时{response_data['processing_time_ms']}ms")
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量水深度计算失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量水深度计算失败: {str(e)}"
        ) 
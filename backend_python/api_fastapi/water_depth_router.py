#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度API模块 (FastAPI版本)
用于计算和获取基于DEM和水位面的水深度数据
"""

from fastapi import APIRouter, HTTPException, status, Path, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import os
import logging
import json
from pathlib import Path as FilePath
import numpy as np
from time import time
import asyncio
from starlette.concurrency import run_in_threadpool

# 导入工具库
from utils.water_depth_calculator import (
    get_dem_value, 
    get_closest_node_level, 
    calculate_water_depth
)
from core.fastapi_helpers import async_handle_exceptions

# 创建路由器
router = APIRouter(prefix="/api")

# 设置日志
logger = logging.getLogger(__name__)

# DEM文件路径
BASE_DIR = FilePath(__file__).parent.parent
DEM_FILE = str(BASE_DIR / "data/dem/dem.tif")

@router.get("/water-depth", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_water_depth(
    lat: float = Query(..., description="纬度", gt=-90, lt=90),
    lng: float = Query(..., description="经度", gt=-180, lt=180),
    nc_file: Optional[str] = Query(None, description="NetCDF结果文件路径"),
    timestamp: Optional[str] = Query(None, description="时间戳")
):
    """
    根据给定的坐标获取水深度信息
    
    Args:
        lat: 纬度
        lng: 经度
        nc_file: NetCDF文件路径（可选）
        timestamp: 时间戳（可选）
    
    Returns:
        包含水深度信息的JSON响应
    """
    logger.info(f"计算水深度: lat={lat}, lng={lng}, nc_file={nc_file}, timestamp={timestamp}")
    start_time = time()
    
    try:
        # 使用线程池执行IO密集型操作
        dem_value = await run_in_threadpool(get_dem_value, DEM_FILE, lat, lng)
        
        if dem_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取DEM值，请检查坐标是否在有效范围内"
            )
        
        # 获取水位面高度
        water_level = await run_in_threadpool(
            get_closest_node_level, 
            nc_file, 
            lat, 
            lng, 
            timestamp
        )
        
        if water_level is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取水位面高度，请检查NetCDF文件和时间戳"
            )
        
        # 计算水深度
        water_depth = await run_in_threadpool(
            calculate_water_depth,
            dem_value, 
            water_level
        )
        
        # 准备响应
        response_data = {
            "success": True,
            "data": {
                "dem_value": float(dem_value),
                "water_level": float(water_level),
                "water_depth": float(water_depth),
                "lat": lat,
                "lng": lng,
                "timestamp": timestamp
            },
            "processing_time_ms": int((time() - start_time) * 1000)
        }
        
        logger.info(f"水深度计算完成: {response_data}")
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"水深度计算失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"水深度计算失败: {str(e)}"
        )

@router.get("/water-depth/batch", response_model=Dict[str, Any])
@async_handle_exceptions
async def batch_water_depth(
    points: str = Query(..., description="JSON格式的点列表"),
    nc_file: Optional[str] = Query(None, description="NetCDF结果文件路径"),
    timestamp: Optional[str] = Query(None, description="时间戳")
):
    """
    批量计算多个点的水深度
    
    Args:
        points: JSON格式的点列表，格式为[{"lat": lat1, "lng": lng1}, ...]
        nc_file: NetCDF文件路径（可选）
        timestamp: 时间戳（可选）
    
    Returns:
        包含多个点水深度信息的JSON响应
    """
    logger.info(f"批量计算水深度: points={points}, nc_file={nc_file}, timestamp={timestamp}")
    start_time = time()
    
    try:
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
            lat = point['lat']
            lng = point['lng']
            
            # 获取DEM值
            dem_value = await run_in_threadpool(get_dem_value, DEM_FILE, lat, lng)
            
            if dem_value is None:
                return {
                    "lat": lat,
                    "lng": lng,
                    "dem_value": None,
                    "water_level": None,
                    "water_depth": None,
                    "error": "无法获取DEM值"
                }
            
            # 获取水位面高度
            water_level = await run_in_threadpool(
                get_closest_node_level, 
                nc_file, 
                lat, 
                lng, 
                timestamp
            )
            
            if water_level is None:
                return {
                    "lat": lat,
                    "lng": lng,
                    "dem_value": float(dem_value),
                    "water_level": None,
                    "water_depth": None,
                    "error": "无法获取水位面高度"
                }
            
            # 计算水深度
            water_depth = await run_in_threadpool(
                calculate_water_depth,
                dem_value, 
                water_level
            )
            
            return {
                "lat": lat,
                "lng": lng,
                "dem_value": float(dem_value),
                "water_level": float(water_level),
                "water_depth": float(water_depth)
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
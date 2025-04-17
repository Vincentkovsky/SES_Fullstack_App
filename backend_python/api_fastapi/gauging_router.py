#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测量站API (FastAPI版本)

提供访问和管理水文测量站数据的API接口。
支持获取测量站列表、测量站详情、水位数据等功能。
"""

from fastapi import APIRouter, Path, Query, HTTPException, status
from typing import Dict, Any, List, Optional
import logging
import json
import os
from pathlib import Path as FilePath
import requests
from datetime import datetime, timedelta
import asyncio
from starlette.concurrency import run_in_threadpool

# 导入自定义工具
from core.fastapi_helpers import async_handle_exceptions
from core.config import Config

# 设置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/gauging")

# 基础路径
BASE_DIR = FilePath(__file__).parent.parent
GAUGING_DATA_DIR = BASE_DIR / "data/gauging_stations"

# 确保测量站数据目录存在
GAUGING_DATA_DIR.mkdir(exist_ok=True, parents=True)

# 缓存
station_cache = {}
data_cache = {}

@router.get("/stations", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_stations():
    """获取所有测量站列表"""
    logger.info("获取测量站列表")
    
    try:
        # 首先检查缓存
        if "stations" in station_cache and station_cache.get("timestamp", 0) > datetime.now().timestamp() - 3600:
            logger.info("返回缓存的测量站列表")
            return {
                "success": True,
                "data": station_cache["stations"],
                "from_cache": True
            }
        
        # 检查是否有本地保存的测量站列表
        stations_file = GAUGING_DATA_DIR / "stations.json"
        if stations_file.exists():
            try:
                stations_data = await run_in_threadpool(lambda: json.load(open(stations_file)))
                
                # 更新缓存
                station_cache["stations"] = stations_data
                station_cache["timestamp"] = datetime.now().timestamp()
                
                return {
                    "success": True,
                    "data": stations_data,
                    "from_file": True
                }
            except Exception as e:
                logger.error(f"读取测量站文件失败: {e}")
                # 继续尝试从API获取
        
        # 从WaterNSW API获取测量站列表
        if not Config.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="缺少API密钥，无法获取测量站数据"
            )
        
        # 构建请求URL
        api_url = f"{Config.WATERNSW_BASE_URL}{Config.WATERNSW_SURFACE_WATER_ENDPOINT}"
        
        # 执行请求
        async def fetch_stations():
            response = requests.get(
                api_url,
                headers={
                    "Authorization": f"ApiKey {Config.API_KEY}",
                    "Accept": "application/json"
                },
                params={
                    "query": json.dumps({
                        "type": "GAUGING",
                        "parameters": ["WATERLEVEL"],
                        "active": True
                    })
                },
                timeout=15
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"WaterNSW API返回错误: {response.text}"
                )
            
            return response.json()
        
        # 在线程池中执行请求
        response_data = await run_in_threadpool(fetch_stations)
        
        # 处理响应数据
        stations = []
        if "data" in response_data and "stations" in response_data["data"]:
            for station in response_data["data"]["stations"]:
                stations.append({
                    "id": station.get("id"),
                    "name": station.get("name"),
                    "number": station.get("number"),
                    "latitude": station.get("latitude"),
                    "longitude": station.get("longitude"),
                    "parameters": station.get("parameters"),
                    "catchment": station.get("catchment"),
                    "river": station.get("river"),
                    "active": station.get("active", True)
                })
        
        # 保存到文件
        with open(stations_file, 'w') as f:
            json.dump(stations, f, indent=2)
        
        # 更新缓存
        station_cache["stations"] = stations
        station_cache["timestamp"] = datetime.now().timestamp()
        
        return {
            "success": True,
            "data": stations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测量站列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测量站列表失败: {str(e)}"
        )

@router.get("/stations/{station_id}", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_station(station_id: str = Path(..., description="测量站ID")):
    """获取特定测量站的详细信息"""
    logger.info(f"获取测量站详情: {station_id}")
    
    try:
        # 首先检查缓存
        cache_key = f"station_{station_id}"
        if cache_key in station_cache and station_cache.get(f"{cache_key}_timestamp", 0) > datetime.now().timestamp() - 3600:
            logger.info(f"返回缓存的测量站详情: {station_id}")
            return {
                "success": True,
                "data": station_cache[cache_key],
                "from_cache": True
            }
        
        # 检查是否有本地保存的测量站详情
        station_file = GAUGING_DATA_DIR / f"station_{station_id}.json"
        if station_file.exists():
            try:
                station_data = await run_in_threadpool(lambda: json.load(open(station_file)))
                
                # 更新缓存
                station_cache[cache_key] = station_data
                station_cache[f"{cache_key}_timestamp"] = datetime.now().timestamp()
                
                return {
                    "success": True,
                    "data": station_data,
                    "from_file": True
                }
            except Exception as e:
                logger.error(f"读取测量站详情文件失败: {e}")
                # 继续尝试从API获取
        
        # 从WaterNSW API获取测量站详情
        if not Config.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="缺少API密钥，无法获取测量站数据"
            )
        
        # 构建请求URL
        api_url = f"{Config.WATERNSW_BASE_URL}{Config.WATERNSW_SURFACE_WATER_ENDPOINT}/{station_id}"
        
        # 执行请求
        async def fetch_station():
            response = requests.get(
                api_url,
                headers={
                    "Authorization": f"ApiKey {Config.API_KEY}",
                    "Accept": "application/json"
                },
                timeout=15
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"WaterNSW API返回错误: {response.text}"
                )
            
            return response.json()
        
        # 在线程池中执行请求
        response_data = await run_in_threadpool(fetch_station)
        
        # 处理响应数据
        station_info = response_data.get("data", {})
        
        # 保存到文件
        with open(station_file, 'w') as f:
            json.dump(station_info, f, indent=2)
        
        # 更新缓存
        station_cache[cache_key] = station_info
        station_cache[f"{cache_key}_timestamp"] = datetime.now().timestamp()
        
        return {
            "success": True,
            "data": station_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测量站详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测量站详情失败: {str(e)}"
        )

@router.get("/stations/{station_id}/data", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_station_data(
    station_id: str = Path(..., description="测量站ID"),
    parameter: str = Query("WATERLEVEL", description="参数类型"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO8601格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO8601格式)"),
    interval: str = Query("day", description="数据间隔 (hour, day, month)")
):
    """获取测量站的时间序列数据"""
    logger.info(f"获取测量站数据: {station_id}, 参数: {parameter}")
    
    try:
        # 处理时间参数
        if not start_time:
            # 默认7天前
            start_time = (datetime.now() - timedelta(days=7)).isoformat()
        
        if not end_time:
            # 默认现在
            end_time = datetime.now().isoformat()
            
        logger.info(f"时间范围: {start_time} 到 {end_time}")
        
        # 缓存键
        cache_key = f"data_{station_id}_{parameter}_{start_time}_{end_time}_{interval}"
        
        # 首先检查缓存
        if cache_key in data_cache and data_cache.get(f"{cache_key}_timestamp", 0) > datetime.now().timestamp() - 1800:
            logger.info(f"返回缓存的测量站数据: {station_id}")
            return {
                "success": True,
                "data": data_cache[cache_key],
                "from_cache": True
            }
        
        # 检查是否有本地保存的数据
        data_file = GAUGING_DATA_DIR / f"data_{station_id}_{parameter}_{interval}.json"
        if data_file.exists():
            try:
                file_data = await run_in_threadpool(lambda: json.load(open(data_file)))
                
                # 检查时间范围
                if file_data.get("start_time") <= start_time and file_data.get("end_time") >= end_time:
                    logger.info(f"返回文件中的测量站数据: {station_id}")
                    
                    # 更新缓存
                    data_cache[cache_key] = file_data["data"]
                    data_cache[f"{cache_key}_timestamp"] = datetime.now().timestamp()
                    
                    return {
                        "success": True,
                        "data": file_data["data"],
                        "from_file": True
                    }
            except Exception as e:
                logger.error(f"读取测量站数据文件失败: {e}")
                # 继续尝试从API获取
        
        # 从WaterNSW API获取数据
        if not Config.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="缺少API密钥，无法获取测量站数据"
            )
        
        # 构建请求URL
        api_url = f"{Config.WATERNSW_BASE_URL}{Config.WATERNSW_SURFACE_WATER_ENDPOINT}/{station_id}/data"
        
        # 执行请求
        async def fetch_data():
            response = requests.get(
                api_url,
                headers={
                    "Authorization": f"ApiKey {Config.API_KEY}",
                    "Accept": "application/json"
                },
                params={
                    "parameter": parameter,
                    "start": start_time,
                    "end": end_time,
                    "interval": interval
                },
                timeout=15
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"WaterNSW API返回错误: {response.text}"
                )
            
            return response.json()
        
        # 在线程池中执行请求
        response_data = await run_in_threadpool(fetch_data)
        
        # 处理响应数据
        series_data = response_data.get("data", {}).get("series", [])
        
        # 保存到文件
        file_content = {
            "station_id": station_id,
            "parameter": parameter,
            "interval": interval,
            "start_time": start_time,
            "end_time": end_time,
            "data": series_data
        }
        
        with open(data_file, 'w') as f:
            json.dump(file_content, f, indent=2)
        
        # 更新缓存
        data_cache[cache_key] = series_data
        data_cache[f"{cache_key}_timestamp"] = datetime.now().timestamp()
        
        return {
            "success": True,
            "data": series_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测量站数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测量站数据失败: {str(e)}"
        ) 
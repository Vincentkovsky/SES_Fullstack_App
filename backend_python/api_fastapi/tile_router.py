#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
地图瓦片API (FastAPI版本)

提供访问和处理地图瓦片的API接口，支持多种数据源和样式。
"""

from fastapi import APIRouter, Path, Query, HTTPException, status, Response
from fastapi.responses import StreamingResponse, FileResponse
from typing import Dict, Any, Optional, List
import os
import logging
from pathlib import Path as FilePath
import io
import requests
from PIL import Image
from io import BytesIO
import json
import asyncio
from starlette.concurrency import run_in_threadpool

# 导入自定义工具
from core.fastapi_helpers import async_handle_exceptions
from core.config import Config

# 设置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/tiles")

# 基础路径
BASE_DIR = FilePath(__file__).parent.parent
TILES_DIR = BASE_DIR / "data/tiles"

# 确保瓦片目录存在
TILES_DIR.mkdir(exist_ok=True, parents=True)

@router.get("/providers", response_model=Dict[str, Any])
@async_handle_exceptions
async def list_tile_providers():
    """获取可用的瓦片提供者列表"""
    providers = [
        {
            "id": "osm",
            "name": "OpenStreetMap",
            "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenStreetMap contributors",
            "max_zoom": 19
        },
        {
            "id": "satellite",
            "name": "Satellite",
            "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attribution": "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            "max_zoom": 19
        },
        {
            "id": "topo",
            "name": "Topographic",
            "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            "attribution": "Esri, HERE, Garmin, USGS, NGA, and the GIS User Community",
            "max_zoom": 19
        }
    ]
    
    return {
        "success": True,
        "data": providers
    }

@router.get("/proxy/{provider}/{z}/{x}/{y}", response_class=Response)
@async_handle_exceptions
async def proxy_tile(
    provider: str = Path(..., description="瓦片提供者 ID"),
    z: int = Path(..., description="缩放级别"),
    x: int = Path(..., description="X坐标"),
    y: int = Path(..., description="Y坐标")
):
    """代理转发瓦片请求到外部服务器，并缓存结果"""
    
    # 构建缓存路径
    cache_dir = TILES_DIR / provider / str(z) / str(x)
    cache_file = cache_dir / f"{y}.png"
    
    # 如果缓存存在，直接返回
    if cache_file.exists():
        return FileResponse(
            path=cache_file,
            media_type="image/png"
        )
    
    # 根据提供者构建URL
    tile_url = ""
    if provider == "osm":
        # OpenStreetMap瓦片服务器
        server = "a"  # 可以是a、b或c
        tile_url = f"https://{server}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    elif provider == "satellite":
        # Esri卫星影像
        tile_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    elif provider == "topo":
        # Esri地形图
        tile_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的瓦片提供者: {provider}"
        )
    
    # 下载瓦片
    try:
        # 在线程池中执行IO密集型操作
        async def download_tile():
            response = requests.get(tile_url, timeout=10)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"获取瓦片失败: {response.status_code}"
                )
            return response.content
            
        tile_data = await run_in_threadpool(lambda: requests.get(tile_url, timeout=10).content)
        
        # 确保缓存目录存在
        cache_dir.mkdir(exist_ok=True, parents=True)
        
        # 保存到缓存
        with open(cache_file, 'wb') as f:
            f.write(tile_data)
        
        # 返回瓦片数据
        return Response(
            content=tile_data,
            media_type="image/png"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"代理瓦片失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"代理瓦片失败: {str(e)}"
        )

@router.get("/capabilities", response_model=Dict[str, Any])
@async_handle_exceptions
async def get_tile_capabilities():
    """获取瓦片服务能力"""
    capabilities = {
        "formats": ["png", "jpg"],
        "tile_size": 256,
        "min_zoom": 0,
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors, Esri, and others",
        "providers": await list_tile_providers()
    }
    
    return {
        "success": True,
        "data": capabilities
    } 
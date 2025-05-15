#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深数据API
提供从GeoTIFF文件中获取指定坐标点的水深数据
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Dict, Any, Optional
import rasterio
from rasterio.windows import Window
import numpy as np
from pathlib import Path
import logging
from pyproj import Transformer, CRS
from functools import lru_cache
import os
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api")

# 基础路径
BASE_DIR = Path(__file__).parent.parent
GEOTIFF_DIR = BASE_DIR / "data/3di_res/geotiff"

# Web墨卡托投影到UTM的转换器
MERC_TO_UTM = Transformer.from_crs(
    CRS.from_epsg(3857),  # Web Mercator
    CRS.from_epsg(32755), # UTM zone 55S
    always_xy=True
)

# 文件修改时间缓存
file_modification_times = {}

def get_file_hash(filepath: str) -> str:
    """获取文件的哈希值，用于缓存键"""
    try:
        mtime = os.path.getmtime(filepath)
        current_mtime = file_modification_times.get(filepath)
        
        if current_mtime != mtime:
            file_modification_times[filepath] = mtime
            get_cached_depth.cache_clear()  # 清除深度缓存
            
        return f"{filepath}_{mtime}"
    except:
        return filepath

@lru_cache(maxsize=1000)
def get_cached_depth(filepath_str: str, lat: float, lng: float) -> Optional[float]:
    """从GeoTIFF文件中获取指定坐标的水深值"""
    # 检查文件修改时间并更新缓存键
    _ = get_file_hash(filepath_str)
    
    filepath = Path(filepath_str)
    
    try:
        with rasterio.open(filepath) as src:
            # 获取源文件的坐标系统
            src_crs = src.crs
            
            # 创建从WGS84到源文件坐标系统的转换器
            wgs84_to_src = Transformer.from_crs(
                CRS.from_epsg(4326),  # WGS84
                src_crs,
                always_xy=True
            )
            
            # 转换坐标
            x, y = wgs84_to_src.transform(lng, lat)
            
            # 检查点是否在栅格范围内
            if not (src.bounds.left <= x <= src.bounds.right and
                   src.bounds.bottom <= y <= src.bounds.top):
                return None
            
            # 将坐标转换为像素坐标
            row, col = src.index(x, y)
            
            # 读取1x1窗口的数据
            window = Window(col, row, 1, 1)
            data = src.read(1, window=window)
            
            # 检查是否为NoData值
            if data.size == 0 or (src.nodata is not None and data[0,0] == src.nodata):
                return None
            
            #trim to 2 decimal places
            return round(float(data[0,0]), 2)
            
    except Exception as e:
        logger.error(f"获取水深失败: {e}")
        return None

@router.get("/water-depth", response_model=Dict[str, Any])
async def get_water_depth(
    lat: float = Query(..., description="纬度"),
    lng: float = Query(..., description="经度"),
    timestamp: str = Query(..., description="时间戳 (格式: waterdepth_YYYYMMDD_HHMM)"),
    simulation: str = Query(..., description="模拟ID")
) -> Dict[str, Any]:
    """获取指定位置和时间的水深数据"""
    try:
        # 构建GeoTIFF文件路径
        filepath = GEOTIFF_DIR / simulation / f"{timestamp}.tif"
        
        if not filepath.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到时间步 {timestamp} 的水深数据"
            )
        
        # 获取水深值
        depth = get_cached_depth(str(filepath), lat, lng)
        
        if depth is None:
            return {
                "success": True,
                "depth": 0,
                "message": "该位置无水深数据"
            }
        
        return {
            "success": True,
            "depth": depth,
            "message": "获取水深成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取水深失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

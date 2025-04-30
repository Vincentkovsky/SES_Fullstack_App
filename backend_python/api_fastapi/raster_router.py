#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
栅格数据API (FastAPI版本)
提供栅格数据的HTTP API，包括获取模拟场景、时间步和栅格瓦片。
"""

from fastapi import APIRouter, HTTPException, status
from fastapi import Path as FastAPIPath
from fastapi.responses import Response
from typing import Dict, Any
import rasterio
from rasterio.windows import Window
from io import BytesIO
from PIL import Image
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import re
from pyproj import Transformer, CRS
from functools import lru_cache
from starlette.concurrency import run_in_threadpool
import os

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api")

# 基础路径
BASE_DIR = Path(__file__).parent.parent
GEOTIFF_DIR = BASE_DIR / "data/3di_res/geotiff"

# Web墨卡托投影常量
TILE_SIZE = 256
EARTH_RADIUS = 6378137.0
ORIGIN_SHIFT = np.pi * EARTH_RADIUS
HALF_EARTH_CIRCUMFERENCE = 20037508.34

# 默认颜色映射
DEFAULT_COLORMAP = {
    "0.0": [0, 0, 0, 0],
    "1.0": [173, 216, 230, 0],
    "10.0": [0, 0, 255, 255]
}

# 全局坐标转换器
MERC_TO_UTM = Transformer.from_crs(
    CRS.from_epsg(3857),
    CRS.from_epsg(32755),
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
            get_cached_tile.cache_clear()  # 清除瓦片缓存
            
        return f"{filepath}_{mtime}"
    except:
        return filepath

def tile_to_meters(x: int, y: int, z: int) -> tuple:
    """将瓦片坐标转换为Web墨卡托投影坐标（米）"""
    n = 1 << z
    res = 2 * HALF_EARTH_CIRCUMFERENCE / (TILE_SIZE * n)
    mx = (x * TILE_SIZE) * res - HALF_EARTH_CIRCUMFERENCE
    my = HALF_EARTH_CIRCUMFERENCE - (y * TILE_SIZE) * res
    mx2 = mx + (TILE_SIZE * res)
    my2 = my - (TILE_SIZE * res)
    return mx, my2, mx2, my

def create_transparent_tile():
    """创建透明瓦片"""
    rgba = np.zeros((256, 256, 4), dtype=np.uint8)
    img = Image.fromarray(rgba)
    buffer = BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return buffer.getvalue()

def apply_colormap(data, colormap):
    """优化的颜色映射应用函数"""
    if data is None or data.size == 0:
        return np.zeros((256, 256, 4), dtype=np.uint8)

    h, w = data.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    sorted_levels = sorted([float(k) for k in colormap.keys()])

    # 创建一个掩码来标记有效数据区域
    valid_mask = ~np.isnan(data)
    
    # 对每个颜色级别应用颜色映射
    for i in range(len(sorted_levels) - 1):
        lower = sorted_levels[i]
        upper = sorted_levels[i + 1]
        lower_color = np.array(colormap[str(lower)])
        upper_color = np.array(colormap[str(upper)])
        
        # 计算主要区域
        mask = (data >= lower) & (data < upper) & valid_mask
        
        if np.any(mask):
            ratio = np.zeros_like(data)
            ratio[mask] = (data[mask] - lower) / (upper - lower)
            for c in range(4):
                rgba[mask, c] = lower_color[c] + ratio[mask] * (upper_color[c] - lower_color[c])

    # 处理最大值
    max_level = sorted_levels[-1]
    max_color = np.array(colormap[str(max_level)])
    max_mask = (data >= max_level) & valid_mask
    if np.any(max_mask):
        rgba[max_mask] = max_color

    # 处理无效数据
    nan_mask = ~valid_mask
    if np.any(nan_mask):
        rgba[nan_mask] = [0, 0, 0, 0]

    return rgba

@lru_cache(maxsize=1000)
def get_cached_tile(filepath_str, z, x, y):
    """获取缓存的瓦片"""
    # 检查文件修改时间并更新缓存键
    _ = get_file_hash(filepath_str)
    
    filepath = Path(filepath_str)
    west_merc, south_merc, east_merc, north_merc = tile_to_meters(x, y, z)
    
    try:
        west_utm, south_utm = MERC_TO_UTM.transform(west_merc, south_merc)
        east_utm, north_utm = MERC_TO_UTM.transform(east_merc, north_merc)
        
        with rasterio.open(filepath) as src:
            src_bounds = src.bounds
            src_nodata = src.nodata
            
            if not (west_utm >= src_bounds.left and east_utm <= src_bounds.right and
                   south_utm >= src_bounds.bottom and north_utm <= src_bounds.top):
                return create_transparent_tile()
            
            # 计算像素坐标
            col_off, row_off = ~src.transform * (west_utm, north_utm)
            col_end, row_end = ~src.transform * (east_utm, south_utm)
            
            # 添加小的缓冲区以改善边缘效果
            buffer_size = 0.5  # 半像素的缓冲区
            minx = max(0, int(np.floor(col_off - buffer_size)))
            miny = max(0, int(np.floor(row_off - buffer_size)))
            maxx = min(src.width, int(np.ceil(col_end + buffer_size)))
            maxy = min(src.height, int(np.ceil(row_end + buffer_size)))
            
            window = Window(minx, miny, maxx - minx, maxy - miny)
            data = src.read(1, window=window)
            
            if data.size == 0 or (src_nodata is not None and np.all(data == src_nodata)):
                return create_transparent_tile()
            
            # 处理NoData值
            if src_nodata is not None:
                mask = (data == src_nodata)
                data = data.astype(np.float32)
                data[mask] = np.nan
            
            # 使用双三次插值进行重采样
            if data.shape != (256, 256):
                data_float = data.astype(np.float32)
                img = Image.fromarray(data_float)
                img_resized = img.resize((256, 256), Image.BICUBIC)
                data = np.array(img_resized)
            
            # 应用颜色映射
            rgba = apply_colormap(data, DEFAULT_COLORMAP)
            
            # 创建最终图像
            img = Image.fromarray(rgba, mode='RGBA')
            
            buffer = BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            return buffer.getvalue()
            
    except Exception as e:
        logger.error(f"生成瓦片失败: {e}")
        return create_transparent_tile()

async def get_simulation_timesteps(simulation_id: str):
    """获取指定模拟场景的时间步列表"""
    sim_dir = GEOTIFF_DIR / simulation_id
    
    def collect_timesteps():
        if not sim_dir.exists() or not sim_dir.is_dir():
            return []
        
        timesteps = []
        for i, file_path in enumerate(sorted(sim_dir.glob("*.tif"))):
            timestamp = file_path.stem
            display_time = timestamp
            
            if re.match(r"\d{8}_\d{6}", timestamp):
                try:
                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            timesteps.append({
                "timestep_id": timestamp,
                "step_number": i,
                "timestamp": display_time,
                "filepath": str(file_path)
            })
        
        return timesteps
    
    return await run_in_threadpool(collect_timesteps)

@router.get("/simulations", response_model=Dict[str, Any])
async def get_simulations():
    """获取所有可用的模拟场景"""
    try:
        simulations = []
        for sim_dir in GEOTIFF_DIR.iterdir():
            if sim_dir.is_dir():
                timesteps = await get_simulation_timesteps(sim_dir.name)
                simulations.append({
                    "simulation_id": sim_dir.name,
                    "name": sim_dir.name,
                    "description": f"Water depth simulation {sim_dir.name}",
                    "num_timesteps": len(timesteps)
                })
        
        return {'success': True, 'data': simulations}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/simulations/{simulation_id}/timesteps", response_model=Dict[str, Any])
async def get_timesteps(simulation_id: str = FastAPIPath(...)):
    """获取特定模拟场景的时间步"""
    try:
        timesteps = await get_simulation_timesteps(simulation_id)
        if not timesteps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到模拟场景 {simulation_id} 或该场景没有时间步数据"
            )
        return {'success': True, 'data': timesteps}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/tiles/{simulation_id}/{timestep_id}/{z}/{x}/{y}.png")
async def get_tile(
    simulation_id: str = FastAPIPath(...),
    timestep_id: str = FastAPIPath(...),
    z: int = FastAPIPath(...),
    x: int = FastAPIPath(...),
    y: int = FastAPIPath(...)
):
    """获取指定模拟场景、时间步、缩放级别和坐标的栅格瓦片"""
    try:
        filepath = GEOTIFF_DIR / simulation_id / f"{timestep_id}.tif"
        
        if not filepath.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'未找到栅格数据: {filepath}'
            )
        
        tile_data = await run_in_threadpool(
            get_cached_tile, str(filepath), z, x, y
        )
        
        return Response(
            content=tile_data,
            media_type="image/png"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/colormap", response_model=Dict[str, Any])
async def get_colormap():
    """获取当前使用的颜色映射"""
    return {
        'success': True,
        'data': DEFAULT_COLORMAP
    }
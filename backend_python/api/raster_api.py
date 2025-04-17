#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
栅格数据API

提供栅格数据的HTTP API，包括获取模拟场景、时间步和栅格瓦片。
直接从文件系统中读取GeoTIFF文件，不依赖数据库。
"""

from flask import Blueprint, request, jsonify, send_file
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window
from io import BytesIO
from PIL import Image
import numpy as np
import os
import json
import glob
from pathlib import Path
import logging
from http import HTTPStatus
from datetime import datetime
import re
from pyproj import Transformer, CRS
from math import ceil
from functools import lru_cache
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import hashlib

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
raster_bp = Blueprint('raster', __name__)

# 基础路径
BASE_DIR = Path(__file__).parent.parent
GEOTIFF_DIR = BASE_DIR / "data/3di_res/geotiff"

# 默认颜色映射
DEFAULT_COLORMAP = {
    "0.0": [240, 249, 232, 0],  # 透明
    "0.1": [240, 249, 232, 50],
    "0.3": [186, 228, 188, 100],
    "0.5": [123, 204, 196, 150],
    "1.0": [43, 140, 190, 200],
    "2.0": [8, 64, 129, 255]
}

# 创建线程池
tile_executor = ThreadPoolExecutor(max_workers=4)

# 添加瓦片缓存
# 使用LRU缓存装饰器，最多缓存1000个结果
@lru_cache(maxsize=1000)
def get_cached_tile(filepath_str, z, x, y, data_type="water_depth"):
    """
    从缓存获取瓦片，如果不存在则生成
    
    Args:
        filepath_str: GeoTIFF文件路径
        z: 缩放级别
        x: 瓦片X坐标
        y: 瓦片Y坐标
        data_type: 数据类型 ('water_depth' 或 'dem')
        
    Returns:
        PNG格式的瓦片图像字节流
    """
    filepath = Path(filepath_str)
    
    # 计算瓦片坐标（只在需要时计算，减少不必要的日志）
    n = 2.0 ** z
    west_merc = x / n * 360.0 - 180.0
    east_merc = (x + 1) / n * 360.0 - 180.0
    north_merc = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y / n))))
    south_merc = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y + 1) / n))))
    
    # 使用静态变量存储转换器，避免重复创建
    if not hasattr(get_cached_tile, "wgs84_to_utm"):
        get_cached_tile.wgs84_to_utm = Transformer.from_crs(
            CRS.from_epsg(4326),  # WGS84
            CRS.from_epsg(32755), # UTM 区域 55S
            always_xy=True
        )
    
    # 转换瓦片四角坐标到UTM
    west_utm, south_utm = get_cached_tile.wgs84_to_utm.transform(west_merc, south_merc)
    east_utm, north_utm = get_cached_tile.wgs84_to_utm.transform(east_merc, north_merc)
    
    # 缓存常用的颜色映射
    if not hasattr(get_cached_tile, "colormap_cache"):
        get_cached_tile.colormap_cache = {
            "water_depth": DEFAULT_COLORMAP,
            "dem": {
                "0.0": [26, 152, 80, 255],    # 低海拔 - 绿色
                "50.0": [145, 207, 96, 255],  # 较低海拔 - 浅绿色
                "100.0": [217, 239, 139, 255], # 中海拔 - 黄绿色
                "200.0": [254, 224, 139, 255], # 较高海拔 - 黄色
                "300.0": [252, 141, 89, 255],  # 高海拔 - 橙色
                "400.0": [215, 48, 39, 255],   # 山峰 - 红色
                "500.0": [215, 48, 39, 255]    # 最高点 - 深红色
            }
        }
    
    try:
        with rasterio.open(filepath) as src:
            # 获取源数据的基本信息
            src_bounds = src.bounds
            src_nodata = src.nodata
            
            # 首先检查UTM坐标是否在源数据范围内
            is_in_bounds = (
                west_utm < src_bounds.right and 
                east_utm > src_bounds.left and 
                south_utm < src_bounds.top and 
                north_utm > src_bounds.bottom
            )
            
            if not is_in_bounds:
                # 返回透明瓦片
                rgba = np.zeros((256, 256, 4), dtype=np.uint8)
                img = Image.fromarray(rgba)
                
                # 保存为PNG
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                return buffer.getvalue()
            
            # 简化坐标转换逻辑，减少日志记录
            src_transform = src.transform
            
            # 将地理坐标转换为栅格像素坐标
            col_off, row_off = ~src_transform * (west_utm, north_utm)  # 左上角
            col_end, row_end = ~src_transform * (east_utm, south_utm)  # 右下角
            
            # 确保坐标顺序正确（如果需要交换）
            if col_off > col_end:
                col_off, col_end = col_end, col_off
            if row_off > row_end:
                row_off, row_end = row_end, row_off
            
            # 确保值在合理范围内
            minx = max(0, int(col_off))
            miny = max(0, int(row_off))
            maxx = min(src.width, int(ceil(col_end)))
            maxy = min(src.height, int(ceil(row_end)))
            
            # 如果窗口无效或太小，返回透明瓦片
            if minx >= maxx or miny >= maxy or maxx - minx < 2 or maxy - miny < 2:
                rgba = np.zeros((256, 256, 4), dtype=np.uint8)
                img = Image.fromarray(rgba)
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                return buffer.getvalue()
            
            width = maxx - minx
            height = maxy - miny
            
            # 创建窗口
            window = Window(minx, miny, width, height)
            
            # 读取数据
            data = src.read(1, window=window)
            
            # 检查数据是否全为NoData
            if data.size == 0 or (src_nodata is not None and np.all(data == src_nodata)):
                rgba = np.zeros((256, 256, 4), dtype=np.uint8)
            else:
                # 重采样到256x256 - 使用PIL直接处理以提高性能
                if data.shape != (256, 256):
                    img = Image.fromarray(data.astype(np.float32))
                    img_resized = img.resize((256, 256), Image.BICUBIC)
                    data_resized = np.array(img_resized)
                else:
                    data_resized = data
                
                # 处理 NoData 值
                if src_nodata is not None:
                    # 创建掩码，标记NoData值
                    mask = (data_resized == src_nodata)
                    # 将NoData值替换为NaN，以便在颜色映射中正确处理
                    data_resized = data_resized.astype(np.float32)
                    data_resized[mask] = np.nan
                
                # 应用优化的颜色映射
                colormap = get_cached_tile.colormap_cache.get(data_type, DEFAULT_COLORMAP)
                colored_data = apply_colormap_optimized(data_resized, colormap, data_type)
                
                rgba = colored_data
    
            # 转换为PIL图像
            img = Image.fromarray(rgba)
            
            # 保存为PNG
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer.getvalue()
            
    except Exception as e:
        logger.error(f"生成瓦片失败: {e}", exc_info=True)
        # 出错时返回透明瓦片
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        img = Image.fromarray(rgba)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()

def apply_colormap_optimized(data, colormap, data_type="water_depth"):
    """优化的颜色映射应用函数"""
    # 处理无效数据
    if data is None or data.size == 0:
        h, w = 256, 256  # 默认瓦片大小
        return np.zeros((h, w, 4), dtype=np.uint8)
    
    # 特殊处理DEM数据
    if data_type == "dem":
        # 计算数据范围
        valid_mask = ~np.isnan(data)
        if not np.any(valid_mask):
            return np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
        
        valid_data = data[valid_mask]
        min_val = np.min(valid_data)
        max_val = np.max(valid_data)
        
        # 使用预计算的颜色映射
        dem_colormap = colormap
        
        # 快速调整颜色映射范围以匹配数据
        adjusted_colormap = {}
        for k, v in dem_colormap.items():
            # 根据实际数据范围调整键值
            new_key = str(min_val + float(k) / 500.0 * (max_val - min_val))
            adjusted_colormap[new_key] = v
        
        colormap = adjusted_colormap
    
    # 创建RGBA图像
    h, w = data.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    
    # 对每个颜色级别应用颜色 - 矢量化操作提高性能
    sorted_levels = sorted([float(k) for k in colormap.keys()])
    
    # 使用numpy的矢量化操作替代循环
    for i in range(len(sorted_levels) - 1):
        lower = sorted_levels[i]
        upper = sorted_levels[i + 1]
        
        lower_color = np.array(colormap[str(lower)])
        upper_color = np.array(colormap[str(upper)])
        
        # 找到该范围内的所有值
        mask = (data >= lower) & (data < upper)
        
        if np.any(mask):
            # 计算插值因子
            ratio = np.zeros_like(data)
            ratio[mask] = (data[mask] - lower) / (upper - lower)
            
            # 对每个通道进行线性插值 - 使用广播操作提高性能
            for c in range(4):
                # 使用更高效的矢量化操作
                rgba[mask, c] = lower_color[c] + ratio[mask] * (upper_color[c] - lower_color[c])
    
    # 处理最大值
    max_level = sorted_levels[-1]
    max_color = np.array(colormap[str(max_level)])
    max_mask = (data >= max_level)
    if np.any(max_mask):
        rgba[max_mask] = max_color
    
    # 处理无效数据（NaN）
    nan_mask = np.isnan(data)
    if np.any(nan_mask):
        rgba[nan_mask] = [0, 0, 0, 0]
    
    return rgba

# 缓存文件的最后修改时间
file_modification_times = {}

def get_file_hash(filepath):
    """获取文件的哈希值，用于决定是否需要刷新缓存"""
    try:
        mtime = os.path.getmtime(filepath)
        return f"{filepath}_{mtime}"
    except:
        # 文件不存在或其他错误
        return filepath

def get_available_simulations():
    """获取可用的模拟场景列表"""
    simulations = []
    
    for sim_dir in GEOTIFF_DIR.iterdir():
        if sim_dir.is_dir():
            sim_info = {
                "simulation_id": sim_dir.name,
                "name": sim_dir.name,
                "description": f"Water depth simulation {sim_dir.name}",
                "num_timesteps": len(list(sim_dir.glob("*.tif")))
            }
            
            # 尝试从名称中提取日期信息（如果名称格式为startTime_endTime）
            if "_" in sim_dir.name:
                try:
                    start_time, end_time = sim_dir.name.split("_")
                    sim_info["start_time"] = start_time
                    sim_info["end_time"] = end_time
                except:
                    pass
            
            # 尝试获取空间范围（从第一个GeoTIFF文件）
            tiff_files = list(sim_dir.glob("*.tif"))
            if tiff_files:
                try:
                    with rasterio.open(tiff_files[0]) as src:
                        bounds = src.bounds
                        sim_info["extent"] = {
                            "west": bounds.left,
                            "south": bounds.bottom,
                            "east": bounds.right,
                            "north": bounds.top,
                            "crs": src.crs.to_string()
                        }
                except Exception as e:
                    logger.error(f"获取模拟{sim_dir.name}空间范围失败: {str(e)}")
            
            simulations.append(sim_info)
    
    return simulations

def get_simulation_timesteps(simulation_id):
    """获取指定模拟场景的时间步列表"""
    sim_dir = GEOTIFF_DIR / simulation_id

    logger.info(f"获取模拟场景 {sim_dir} 的时间步列表")
    
    if not sim_dir.exists() or not sim_dir.is_dir():
        return []
    
    timesteps = []
    tiff_files = sorted(sim_dir.glob("*.tif"))
    
    for i, file_path in enumerate(tiff_files):
        # 从文件名中提取时间戳信息
        timestamp = file_path.stem
        
        # 尝试转换为更友好的日期格式（如果可能）
        display_time = timestamp
        if re.match(r"\d{8}_\d{6}", timestamp):  # 格式如：20220101_120000
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

def from_geographic_bounds(src, west, south, east, north):
    """将地理坐标范围转换为栅格窗口"""
    try:
        # 检查源数据的坐标系统
        src_crs = src.crs
        input_crs = CRS.from_epsg(32755)  # 假设输入坐标是UTM区域55S
        
        # 记录输入坐标
        logger.info(f"输入坐标 (UTM): 西={west:.1f}, 南={south:.1f}, 东={east:.1f}, 北={north:.1f}")
        
        # 获取源数据的变换矩阵
        src_transform = src.transform
        logger.info(f"源数据变换矩阵: {src_transform}")
        
        # 如果源数据不是UTM坐标系，需要进行坐标转换
        if src_crs != input_crs:
            logger.info(f"源数据坐标系 {src_crs} 与输入坐标系 {input_crs} 不同，进行转换")
            # 创建从输入坐标系到源数据坐标系的转换器
            transformer = Transformer.from_crs(input_crs, src_crs, always_xy=True)
            west, south = transformer.transform(west, south)
            east, north = transformer.transform(east, north)
            logger.info(f"转换后坐标: 西={west:.1f}, 南={south:.1f}, 东={east:.1f}, 北={north:.1f}")
            
        # 将地理坐标转换为栅格像素坐标
        try:
            col_off, row_off = ~src_transform * (west, north)  # 左上角
            col_end, row_end = ~src_transform * (east, south)  # 右下角
            
            logger.info(f"栅格像素坐标 (转换前): 列起点={col_off:.1f}, 行起点={row_off:.1f}, 列终点={col_end:.1f}, 行终点={row_end:.1f}")
            
            # 确保坐标顺序正确（如果需要交换）
            if col_off > col_end:
                col_off, col_end = col_end, col_off
            if row_off > row_end:
                row_off, row_end = row_end, row_off
            
            # 确保值在合理范围内
            minx = max(0, int(col_off))
            miny = max(0, int(row_off))
            maxx = min(src.width, int(ceil(col_end)))
            maxy = min(src.height, int(ceil(row_end)))
            
            logger.info(f"栅格像素坐标 (截断后): 列起点={minx}, 行起点={miny}, 列终点={maxx}, 行终点={maxy}")
            
            # 如果窗口无效或太小，返回None
            if minx >= maxx or miny >= maxy:
                logger.warning(f"计算的窗口无效: 列范围=({minx}, {maxx}), 行范围=({miny}, {maxy})")
                return None
            
            width = maxx - minx
            height = maxy - miny
            
            # 校验窗口大小是否合理
            if width < 2 or height < 2:
                logger.warning(f"窗口太小: 宽={width}, 高={height}")
                # 尝试扩展窗口到最小2x2像素
                if width < 2:
                    if maxx < src.width: maxx += (2 - width)
                    elif minx > 0: minx -= (2 - width)
                if height < 2:
                    if maxy < src.height: maxy += (2 - height)
                    elif miny > 0: miny -= (2 - height)
                
                width = maxx - minx
                height = maxy - miny
                logger.info(f"调整后的窗口: 宽={width}, 高={height}")
            
            window = Window(minx, miny, width, height)
            logger.info(f"最终窗口: {window}")
            return window
        except Exception as e:
            logger.error(f"像素转换失败: {str(e)}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"计算栅格窗口失败: {str(e)}", exc_info=True)
        return None

def resize_array(array, target_shape):
    """调整数组大小到目标形状"""
    if array.shape == target_shape:
        return array
    
    # 使用PIL进行重采样
    img = Image.fromarray(array.astype(np.float32))
    img_resized = img.resize(target_shape, Image.BICUBIC)
    return np.array(img_resized)

def apply_colormap(data, colormap=None, data_type="water_depth"):
    """应用颜色映射到数据"""
    if colormap is None:
        colormap = DEFAULT_COLORMAP
    
    # 处理无效数据
    if data is None or data.size == 0:
        logger.warning("apply_colormap收到空数据")
        h, w = 256, 256  # 默认瓦片大小
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        return rgba
    
    # 检查数据类型并应用相应的颜色映射
    if data_type == "dem":
        # DEM高程数据的颜色映射
        # 使用适合地形高程的颜色方案
        dem_colormap = {
            "0.0": [26, 152, 80, 255],    # 低海拔 - 绿色
            "50.0": [145, 207, 96, 255],  # 较低海拔 - 浅绿色
            "100.0": [217, 239, 139, 255], # 中海拔 - 黄绿色
            "200.0": [254, 224, 139, 255], # 较高海拔 - 黄色
            "300.0": [252, 141, 89, 255],  # 高海拔 - 橙色
            "400.0": [215, 48, 39, 255],   # 山峰 - 红色
            "500.0": [215, 48, 39, 255]    # 最高点 - 深红色
        }
        
        # 计算数据范围
        valid_mask = ~np.isnan(data)
        if not np.any(valid_mask):
            logger.warning("DEM数据全为NaN")
            rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
            return rgba
        
        valid_data = data[valid_mask]
        min_val = np.min(valid_data)
        max_val = np.max(valid_data)
        
        logger.info(f"DEM数据范围: 最小={min_val:.2f}, 最大={max_val:.2f}")
        
        # 调整颜色映射范围以匹配数据
        adjusted_colormap = {}
        for k, v in dem_colormap.items():
            # 根据实际数据范围调整键值
            new_key = str(min_val + float(k) / 500.0 * (max_val - min_val))
            adjusted_colormap[new_key] = v
        
        colormap = adjusted_colormap
        logger.info(f"调整后的DEM颜色映射: {colormap}")
    
    # 创建RGBA图像
    rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
    
    # 对每个颜色级别应用颜色
    sorted_levels = sorted([float(k) for k in colormap.keys()])
    
    for i in range(len(sorted_levels) - 1):
        lower = sorted_levels[i]
        upper = sorted_levels[i + 1]
        
        lower_color = np.array(colormap[str(lower)])
        upper_color = np.array(colormap[str(upper)])
        
        # 找到该范围内的所有值
        mask = (data >= lower) & (data < upper)
        
        if np.any(mask):
            # 计算插值因子
            ratio = (data[mask] - lower) / (upper - lower)
            
            # 对每个通道进行线性插值
            for c in range(4):
                rgba[mask, c] = lower_color[c] + ratio * (upper_color[c] - lower_color[c])
    
    # 处理最大值
    max_level = sorted_levels[-1]
    max_color = np.array(colormap[str(max_level)])
    rgba[data >= max_level] = max_color
    
    # 处理无效数据（NaN或NoData）
    if hasattr(data, 'mask'):
        # 对于掩码数组
        rgba[data.mask] = [0, 0, 0, 0]
    else:
        # 对于常规数组，假设NaN为无效
        rgba[np.isnan(data)] = [0, 0, 0, 0]
    
    return rgba

def load_colormap_from_file(file_path):
    """从文件加载颜色映射"""
    colormap = {}
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                    
                parts = line.split()
                if len(parts) >= 5:  # 值 + RGBA
                    depth = float(parts[0])
                    r = int(parts[1])
                    g = int(parts[2])
                    b = int(parts[3])
                    a = int(parts[4])
                    colormap[str(depth)] = [r, g, b, a]
        
        return colormap
    except Exception as e:
        logger.error(f"加载颜色映射文件失败: {str(e)}")
        return None

# 尝试加载颜色映射文件
COLOR_FILE = BASE_DIR / "resources/watercolor.txt"
if COLOR_FILE.exists():
    file_colormap = load_colormap_from_file(str(COLOR_FILE))
    if file_colormap:
        DEFAULT_COLORMAP = file_colormap
        logger.info(f"已从 {COLOR_FILE} 加载颜色映射")
    else:
        logger.warning(f"无法从 {COLOR_FILE} 加载颜色映射，使用默认颜色映射")
else:
    logger.warning(f"颜色映射文件 {COLOR_FILE} 不存在，使用默认颜色映射")

@raster_bp.route('/api/simulations', methods=['GET'])
def get_simulations():
    """获取所有可用的模拟场景"""
    try:
        simulations = get_available_simulations()
        
        return jsonify({
            'success': True,
            'data': simulations
        })
    except Exception as e:
        logger.error(f"获取模拟场景列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取模拟场景列表失败: {str(e)}"
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@raster_bp.route('/api/simulations/<simulation_id>/timesteps', methods=['GET'])
def get_timesteps(simulation_id):
    """获取特定模拟场景的时间步"""
    logger.info(f"获取模拟场景 {simulation_id} 的时间步列表")
    try:
        timesteps = get_simulation_timesteps(simulation_id)
        
        if not timesteps:
            return jsonify({
                'success': False,
                'message': f"未找到模拟场景 {simulation_id} 或该场景没有时间步数据"
            }), HTTPStatus.NOT_FOUND
        
        return jsonify({
            'success': True,
            'data': timesteps
        })
    except Exception as e:
        logger.error(f"获取时间步列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取时间步列表失败: {str(e)}"
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@raster_bp.route('/api/tiles/<simulation_id>/<timestep_id>/<int:z>/<int:x>/<int:y>.png', methods=['GET'])
def get_tile(simulation_id, timestep_id, z, x, y):
    """获取指定模拟场景、时间步、缩放级别和坐标的栅格瓦片"""
    try:
        # 构建GeoTIFF文件路径
        filepath = GEOTIFF_DIR / simulation_id / f"{timestep_id}.tif"
        
        if not filepath.exists():
            # 返回404
            return jsonify({
                'success': False,
                'message': f'未找到栅格数据: {filepath}'
            }), HTTPStatus.NOT_FOUND
        
        # 检测数据类型 (DEM 或 water_depth)
        data_type = "water_depth"  # 默认为水深度数据
        if "dem" in timestep_id.lower():
            data_type = "dem"
        
        # 获取文件哈希，用于缓存键
        file_key = get_file_hash(filepath)
        cache_key = f"{file_key}_{z}_{x}_{y}_{data_type}"
        
        # 使用缓存获取瓦片数据
        tile_data = get_cached_tile(str(filepath), z, x, y, data_type)
        
        # 返回PNG图像
        buffer = BytesIO(tile_data)
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=False
        )
    
    except Exception as e:
        logger.error(f"生成瓦片失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"生成瓦片失败: {str(e)}"
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@raster_bp.route('/api/colormap', methods=['GET'])
def get_colormap():
    """获取当前使用的颜色映射"""
    return jsonify({
        'success': True,
        'data': DEFAULT_COLORMAP
    })

@raster_bp.route('/api/metadata/<simulation_id>', methods=['GET'])
def get_simulation_metadata(simulation_id):
    """获取指定模拟场景的元数据"""
    try:
        sim_dir = GEOTIFF_DIR / simulation_id
        
        if not sim_dir.exists() or not sim_dir.is_dir():
            return jsonify({
                'success': False,
                'message': f"未找到模拟场景 {simulation_id}"
            }), HTTPStatus.NOT_FOUND
        
        # 获取基本信息
        timesteps = get_simulation_timesteps(simulation_id)
        
        # 尝试从第一个GeoTIFF文件获取更详细的元数据
        metadata = {
            "simulation_id": simulation_id,
            "name": simulation_id,
            "description": f"Water depth simulation {simulation_id}",
            "num_timesteps": len(timesteps),
            "timesteps": timesteps
        }
        
        if timesteps:
            filepath = timesteps[0]["filepath"]
            try:
                with rasterio.open(filepath) as src:
                    metadata.update({
                        "width": src.width,
                        "height": src.height,
                        "crs": src.crs.to_string(),
                        "bounds": {
                            "west": src.bounds.left,
                            "south": src.bounds.bottom,
                            "east": src.bounds.right,
                            "north": src.bounds.top
                        },
                        "resolution": {
                            "x": src.res[0],
                            "y": src.res[1]
                        },
                        "nodata": src.nodata
                    })
            except Exception as e:
                logger.error(f"获取GeoTIFF元数据失败: {str(e)}")
        
        return jsonify({
            'success': True,
            'data': metadata
        })
    except Exception as e:
        logger.error(f"获取模拟场景元数据失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取模拟场景元数据失败: {str(e)}"
        }), HTTPStatus.INTERNAL_SERVER_ERROR 
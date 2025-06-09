#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度计算工具模块

提供从DEM和NetCDF计算水深度的功能。
"""

import logging
import numpy as np
import rasterio

# 配置日志
logger = logging.getLogger(__name__)

def get_dem_value(dem_file: str, lat: float, lng: float) -> float:
    """
    获取指定坐标的DEM值
    
    Args:
        dem_file: DEM文件路径
        lat: 纬度
        lng: 经度
        
    Returns:
        float: DEM高程值
    """
    try:
        with rasterio.open(dem_file) as src:
            # 将地理坐标转换为栅格坐标
            row, col = src.index(lng, lat)
            
            # 确保坐标在栅格范围内
            if row < 0 or row >= src.height or col < 0 or col >= src.width:
                logger.warning(f"坐标 ({lat}, {lng}) 超出DEM范围")
                return 0.0
            
            # 读取坐标处的值
            dem_value = src.read(1, window=((row, row+1), (col, col+1)))
            
            # 如果没有有效值，返回0
            if dem_value.size == 0 or np.all(dem_value == src.nodata):
                return 0.0
            
            # 四舍五入到2位小数
            return round(float(dem_value[0][0]), 2)
    except Exception as e:
        logger.error(f"读取DEM值失败: {str(e)}")
        raise

def get_closest_node_level(nc_file: str, lat: float, lng: float, timestamp: str = None) -> float:
    """
    从NetCDF文件获取最近节点的水位
    
    Args:
        nc_file: NetCDF文件路径
        lat: 纬度
        lng: 经度
        timestamp: 时间戳
        
    Returns:
        float: 水位值
    """
    # 这里是模拟实现，实际上应该从NetCDF文件读取
    logger.info(f"模拟从NetCDF获取水位: {nc_file}, 坐标({lat}, {lng}), 时间{timestamp}")
    return 1.0

def calculate_water_depth(dem_value: float, water_level: float) -> float:
    """
    计算水深度
    
    Args:
        dem_value: DEM高程值
        water_level: 水位值
        
    Returns:
        float: 水深度值
    """
    # 水位减去地面高程，如果为负则水深为0
    depth = max(0.0, water_level - dem_value)
    return round(depth, 2) 
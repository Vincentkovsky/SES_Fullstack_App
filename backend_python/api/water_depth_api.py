#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度API接口

提供HTTP接口用于获取指定地理坐标的水深度信息。
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify
from http import HTTPStatus
import logging
import numpy as np
from datetime import datetime
import os
import glob
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_geom

# 导入自定义模块
from utils.water_depth_calculator import (
    get_dem_value, 
    get_closest_node_level,
    calculate_water_depth
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
water_depth_bp = Blueprint('water_depth', __name__)

# 获取基础路径
BASE_DIR = Path(__file__).parent.parent
NETCDF_DIR = BASE_DIR / "data/3di_res/netcdf"
DEM_FILE = BASE_DIR / "data/3di_res/5m_dem.tif"
# 添加GeoTIFF文件路径
GEOTIFF_DIR = BASE_DIR / "data/3di_res/geotiff"


def get_available_simulations() -> List[str]:
    """
    获取可用的模拟数据列表
    
    Returns:
        List[str]: 可用的模拟数据文件名列表
    """
    # 从GeoTIFF目录获取模拟文件夹列表
    simulations = [d.name for d in GEOTIFF_DIR.iterdir() if d.is_dir()]
    return sorted(simulations)


def get_water_depth_from_geotiff(geotiff_path: str, lat: float, lng: float) -> float:
    """
    从GeoTIFF文件读取指定坐标的水深度
    
    Args:
        geotiff_path (str): GeoTIFF文件路径
        lat (float): 纬度
        lng (float): 经度
    
    Returns:
        float: 水深度值
    """
    try:
        with rasterio.open(geotiff_path) as src:
            # 将地理坐标转换为栅格坐标（行列）
            # 使用rasterio.transform.index替代rowcol
            row, col = src.index(lng, lat)
            
            # 确保坐标在栅格范围内
            if row < 0 or row >= src.height or col < 0 or col >= src.width:
                logger.warning(f"坐标 ({lat}, {lng}) 超出栅格范围")
                return 0.0
            
            # 读取坐标处的值
            depth_value = src.read(1, window=((row, row+1), (col, col+1)))
            
            # 如果没有有效值，返回0
            if depth_value.size == 0 or np.all(depth_value == src.nodata):
                return 0.0
            
            # 四舍五入到2位小数
            return round(float(depth_value[0][0]), 2)
    except Exception as e:
        logger.error(f"从GeoTIFF读取水深度失败: {str(e)}")
        raise


@water_depth_bp.route('/api/water-depth', methods=['GET'])
def get_water_depth():
    """
    获取指定地理坐标的水深度（从GeoTIFF文件读取）
    
    查询参数:
        lat (float): 纬度
        lng (float): 经度
        simulation (str, optional): 模拟数据文件夹名称
        timestamp (str, optional): 时间戳，如waterdepth_20230101_120000
        
    Returns:
        JSON: 水深度数据
    """
    try:
        # 获取并验证参数
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        simulation = request.args.get('simulation')
        timestamp = request.args.get('timestamp')
        
        # 参数验证
        if not lat or not lng:
            return jsonify({
                "error": "必须提供lat和lng参数"
            }), HTTPStatus.BAD_REQUEST
            
        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return jsonify({
                "error": "lat和lng参数必须是有效的数值"
            }), HTTPStatus.BAD_REQUEST
        
        # 验证simulation参数
        if not simulation:
            # 获取可用的模拟文件夹
            simulations = get_available_simulations()
            if not simulations:
                return jsonify({
                    "error": "没有可用的模拟数据"
                }), HTTPStatus.NOT_FOUND
            
            simulation = simulations[-1]  # 默认使用最新的模拟
        
        # 构建模拟文件夹路径
        simulation_dir = GEOTIFF_DIR / simulation
        if not simulation_dir.exists() or not simulation_dir.is_dir():
            return jsonify({
                "error": f"指定的模拟 '{simulation}' 不存在"
            }), HTTPStatus.NOT_FOUND
        
        # 获取可用的时间戳
        tiff_files = list(simulation_dir.glob("*.tif"))
        if not tiff_files:
            return jsonify({
                "error": f"模拟 '{simulation}' 没有可用的GeoTIFF文件"
            }), HTTPStatus.NOT_FOUND
        
        # 排序并从文件名提取时间戳
        tiff_files.sort()
        available_timestamps = [f.stem for f in tiff_files]
        
        # 验证timestamp参数
        if not timestamp:
            # 默认使用最新的时间戳
            timestamp = available_timestamps[-1]
        elif timestamp not in available_timestamps:
            # 尝试匹配部分时间戳
            matched_timestamps = [ts for ts in available_timestamps if timestamp in ts]
            if matched_timestamps:
                timestamp = matched_timestamps[0]
            else:
                return jsonify({
                    "error": f"指定的时间戳 '{timestamp}' 不存在",
                    "available_timestamps": available_timestamps
                }), HTTPStatus.NOT_FOUND
        
        # 构建GeoTIFF文件路径
        geotiff_path = str(simulation_dir / f"{timestamp}.tif")
        
        # 从GeoTIFF获取水深度
        try:
            water_depth_value = get_water_depth_from_geotiff(geotiff_path, lat, lng)
        except Exception as e:
            logger.error(f"获取水深度失败: {str(e)}")
            return jsonify({
                "error": "从GeoTIFF获取水深度失败",
                "details": str(e)
            }), HTTPStatus.INTERNAL_SERVER_ERROR
        
        # 获取DEM值（可选，如果需要的话）
        try:
            dem_value = get_dem_value(str(DEM_FILE), lat, lng)
        except Exception as e:
            logger.error(f"获取DEM值失败: {str(e)}")
            dem_value = None
        
        # 构建结果
        result = {
            "location": {
                "latitude": lat,
                "longitude": lng
            },
            "water_depth": water_depth_value,
            "simulation": simulation,
            "timestamp": timestamp,
        }
        
        # 如果有DEM值，添加到结果
        if dem_value is not None:
            result["dem_elevation"] = float(dem_value)
        
        return jsonify(result), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取水深度数据失败: {str(e)}")
        return jsonify({
            "error": "获取水深度数据失败",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR


@water_depth_bp.route('/api/simulations', methods=['GET'])
def get_simulations():
    """
    获取可用的模拟数据列表
    
    Returns:
        JSON: 可用的模拟数据列表
    """
    try:
        # 从GeoTIFF目录获取模拟文件夹列表
        simulations = get_available_simulations()
        
        return jsonify({
            "simulations": simulations,
            "count": len(simulations)
        }), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取模拟数据列表失败: {str(e)}")
        return jsonify({
            "error": "获取模拟数据列表失败",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR


@water_depth_bp.route('/api/timestamps', methods=['GET'])
def get_timestamps():
    """
    获取指定模拟的可用时间戳列表
    
    查询参数:
        simulation (str, optional): 模拟数据文件夹名称，不提供时使用最新的模拟
        
    Returns:
        JSON: 可用的时间戳列表
    """
    try:
        # 获取并验证参数
        simulation = request.args.get('simulation')
        
        # 如果未提供simulation参数
        if not simulation:
            # 获取可用的模拟文件夹
            simulations = get_available_simulations()
            if not simulations:
                return jsonify({
                    "error": "没有可用的模拟数据"
                }), HTTPStatus.NOT_FOUND
            
            simulation = simulations[-1]  # 默认使用最新的模拟
        
        # 构建模拟文件夹路径
        simulation_dir = GEOTIFF_DIR / simulation
        if not simulation_dir.exists() or not simulation_dir.is_dir():
            return jsonify({
                "error": f"指定的模拟 '{simulation}' 不存在"
            }), HTTPStatus.NOT_FOUND
        
        # 获取可用的时间戳
        tiff_files = list(simulation_dir.glob("*.tif"))
        if not tiff_files:
            return jsonify({
                "error": f"模拟 '{simulation}' 没有可用的GeoTIFF文件"
            }), HTTPStatus.NOT_FOUND
        
        # 排序并从文件名提取时间戳
        tiff_files.sort()
        timestamps = [f.stem for f in tiff_files]
        
        return jsonify({
            "simulation": simulation,
            "timestamps": timestamps,
            "count": len(timestamps)
        }), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取时间戳列表失败: {str(e)}")
        return jsonify({
            "error": "获取时间戳列表失败",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR 
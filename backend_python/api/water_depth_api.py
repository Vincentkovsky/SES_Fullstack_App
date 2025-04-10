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


def get_available_simulations() -> List[str]:
    """
    获取可用的模拟数据列表
    
    Returns:
        List[str]: 可用的模拟数据文件名列表
    """
    nc_files = glob.glob(str(NETCDF_DIR / "*.nc"))
    return [os.path.basename(f) for f in sorted(nc_files)]


@water_depth_bp.route('/api/water-depth', methods=['GET'])
def get_water_depth():
    """
    获取指定地理坐标的水深度
    
    查询参数:
        lat (float): 纬度
        lng (float): 经度
        simulation (str, optional): 模拟数据文件名，如不指定则使用最新的模拟
        
    Returns:
        JSON: 水深度数据
    """
    try:
        # 获取并验证参数
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        simulation = request.args.get('simulation')
        
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
            
        # 获取可用的模拟数据
        available_simulations = get_available_simulations()
        if not available_simulations:
            return jsonify({
                "error": "没有可用的模拟数据"
            }), HTTPStatus.NOT_FOUND
            
        # 选择模拟数据
        if not simulation:
            simulation = available_simulations[-1]  # 默认使用最新的模拟
        elif simulation not in available_simulations:
            return jsonify({
                "error": f"指定的模拟数据 '{simulation}' 不存在",
                "available_simulations": available_simulations
            }), HTTPStatus.NOT_FOUND
            
        # 构建NetCDF文件路径
        nc_file = str(NETCDF_DIR / simulation)
        
        # 获取DEM值
        try:
            dem_value = get_dem_value(str(DEM_FILE), lat, lng)
        except Exception as e:
            logger.error(f"获取DEM值失败: {str(e)}")
            return jsonify({
                "error": "获取地面高程数据失败",
                "details": str(e)
            }), HTTPStatus.INTERNAL_SERVER_ERROR
            
        # 获取水位数据
        try:
            times, water_levels = get_closest_node_level(nc_file, lat, lng)
        except Exception as e:
            logger.error(f"获取水位数据失败: {str(e)}")
            return jsonify({
                "error": "获取水位数据失败",
                "details": str(e)
            }), HTTPStatus.INTERNAL_SERVER_ERROR
            
        # 计算水深度
        water_depth = water_levels - dem_value
        
        # 四舍五入到2位小数
        water_depth_rounded = np.round(water_depth, decimals=2)
        
        # 构建结果
        result = {
            "location": {
                "latitude": lat,
                "longitude": lng
            },
            "dem_elevation": float(dem_value),
            "water_levels": water_levels.tolist(),
            "water_depths": water_depth_rounded.tolist(),
            "times": [str(t) for t in times],
            "simulation": simulation,
            "current_water_depth": float(water_depth_rounded[-1]),
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(result), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取水深度数据失败: {str(e)}")
        return jsonify({
            "error": "获取水深度数据失败",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR


@water_depth_bp.route('/api/water-depth/point', methods=['GET'])
def get_water_depth_at_point():
    """
    获取指定地理坐标的当前水深度（简化版，只返回当前值）
    
    查询参数:
        lat (float): 纬度
        lng (float): 经度
        simulation (str, optional): 模拟数据文件名，如不指定则使用最新的模拟
        timestamp (str, optional): 时间戳，如不指定则使用最新的时间点
        
    Returns:
        JSON: 简化的水深度数据
    """
    try:
        # 获取并验证参数
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        simulation = request.args.get('simulation')
        timestamp = request.args.get('timestamp')  # 新增时间戳参数
        
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
            
        # 获取可用的模拟数据
        available_simulations = get_available_simulations()
        if not available_simulations:
            return jsonify({
                "error": "没有可用的模拟数据"
            }), HTTPStatus.NOT_FOUND
            
        # 选择模拟数据
        if not simulation:
            simulation = available_simulations[-1]  # 默认使用最新的模拟
        elif simulation not in available_simulations:
            return jsonify({
                "error": f"指定的模拟数据 '{simulation}' 不存在",
                "available_simulations": available_simulations
            }), HTTPStatus.NOT_FOUND
            
        # 构建NetCDF文件路径
        nc_file = str(NETCDF_DIR / simulation)
        
        # 获取DEM值
        try:
            dem_value = get_dem_value(str(DEM_FILE), lat, lng)
        except Exception as e:
            logger.error(f"获取DEM值失败: {str(e)}")
            return jsonify({
                "error": "获取地面高程数据失败"
            }), HTTPStatus.INTERNAL_SERVER_ERROR
            
        # 获取水位数据
        try:
            times, water_levels = get_closest_node_level(nc_file, lat, lng)
        except Exception as e:
            logger.error(f"获取水位数据失败: {str(e)}")
            return jsonify({
                "error": "获取水位数据失败"
            }), HTTPStatus.INTERNAL_SERVER_ERROR
            
        # 如果提供了时间戳，查找最接近的时间点
        index = -1  # 默认使用最新的时间点
        if timestamp:
            try:
                # 解析时间戳格式 (waterdepth_YYYYMMDD_HHMMSS)
                # 将其转换为numpy datetime64格式，以便与times数组比较
                timestamp_match = timestamp.strip().split('_')
                if len(timestamp_match) >= 3:
                    date_part = timestamp_match[1]
                    time_part = timestamp_match[2]
                    
                    # 构建与times数组相同格式的时间字符串
                    timestamp_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]} {time_part[:2]}:{time_part[2:4]}:00"
                    target_time = np.datetime64(timestamp_str)
                    
                    # 查找最接近的时间点
                    time_diffs = np.abs(np.array(times) - target_time)
                    index = np.argmin(time_diffs)
                    
                    logger.info(f"找到最接近时间戳 {timestamp} 的时间点: {times[index]}, 索引: {index}")
                else:
                    logger.warning(f"无效的时间戳格式: {timestamp}")
            except Exception as e:
                logger.error(f"处理时间戳时出错: {timestamp}, 错误: {str(e)}")
                # 继续使用最新的时间点
        
        # 计算水深度
        water_depth = water_levels[index] - dem_value  # 使用指定或最新的时间点
        
        # 四舍五入到2位小数
        water_depth_rounded = round(float(water_depth), 2)
        
        # 构建简化结果
        result = {
            "latitude": lat,
            "longitude": lng,
            "dem_elevation": float(dem_value),
            "water_level": float(water_levels[index]),
            "water_depth": water_depth_rounded,
            "simulation": simulation,
            "timestamp": str(times[index])
        }
        
        return jsonify(result), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取水深度数据失败: {str(e)}")
        return jsonify({
            "error": "获取水深度数据失败"
        }), HTTPStatus.INTERNAL_SERVER_ERROR


@water_depth_bp.route('/api/simulations', methods=['GET'])
def get_simulations():
    """
    获取可用的模拟数据列表
    
    Returns:
        JSON: 可用的模拟数据列表
    """
    try:
        simulations = get_available_simulations()
        
        return jsonify({
            "simulations": simulations,
            "count": len(simulations)
        }), HTTPStatus.OK
        
    except Exception as e:
        logger.error(f"获取模拟数据列表失败: {str(e)}")
        return jsonify({
            "error": "获取模拟数据列表失败"
        }), HTTPStatus.INTERNAL_SERVER_ERROR 
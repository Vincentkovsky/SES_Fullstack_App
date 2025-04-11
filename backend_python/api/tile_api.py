from flask import Blueprint, jsonify, request, send_file
from http import HTTPStatus
import logging
import os
from pathlib import Path
from utils.helpers import handle_exceptions, is_steed_mode
from services.tile_service import get_tiles_list, get_tile_path, get_historical_simulations
from core.config import Config

logger = logging.getLogger(__name__)

# 创建蓝图
tile_bp = Blueprint('tile', __name__)

@tile_bp.route('/api/tilesList', methods=['GET'])
@handle_exceptions
def get_tiles_list_api():
    """获取瓦片列表的API端点"""
    steed_mode = is_steed_mode()
    simulation = request.args.get('simulation')
    
    timestamps, status_code, error_message = get_tiles_list(steed_mode, simulation)
    
    if status_code != 200:
        return jsonify({"error": error_message}), status_code
    
    return jsonify({"message": timestamps}), HTTPStatus.OK

@tile_bp.route('/api/tiles/<timestamp>/<z>/<x>/<y>', methods=['GET'])
@handle_exceptions
def get_tile_by_coordinates(timestamp, z, x, y):
    """根据坐标获取瓦片的API端点"""
    steed_mode = is_steed_mode()
    simulation = request.args.get('simulation')
    
    tile_path, status_code, error_message = get_tile_path(
        timestamp, z, x, y, steed_mode, simulation
    )
    
    if status_code != 200:
        return jsonify({"error": error_message}), status_code
    
    return send_file(tile_path), HTTPStatus.OK

@tile_bp.route('/api/tiles/simulation/<simulation>/<timestamp>/<z>/<x>/<y>', methods=['GET'])
@handle_exceptions
def get_tile_by_coordinates_with_simulation(simulation, timestamp, z, x, y):
    """明确包含simulation参数的瓦片API端点"""
    tile_path, status_code, error_message = get_tile_path(
        timestamp, z, x, y, False, simulation
    )
    
    if status_code != 200:
        return jsonify({"error": error_message}), status_code
    
    return send_file(tile_path), HTTPStatus.OK

@tile_bp.route('/api/historical-simulations', methods=['GET'])
@handle_exceptions
def get_historical_simulations_api():
    """获取历史模拟文件夹列表的API端点"""
    simulations = get_historical_simulations()
    
    if not simulations:
        return jsonify({"error": "未找到历史模拟目录"}), HTTPStatus.NOT_FOUND
    
    return jsonify({"message": simulations}), HTTPStatus.OK

@tile_bp.route('/api/rainfall-tiles/<simulation>', methods=['GET'])
@handle_exceptions
def get_rainfall_tiles_list(simulation):
    """获取特定模拟的降雨瓦片时间戳列表的API端点"""
    if not simulation:
        return jsonify({"error": "必须指定simulation参数"}), HTTPStatus.BAD_REQUEST
    
    # 构建降雨瓦片目录路径
    rainfall_tiles_dir = Config.DATA_DIR / "rainfall_data" / simulation / "tiles"
    
    # 检查目录是否存在
    if not rainfall_tiles_dir.exists():
        # 如果目录不存在，则创建目录并返回空列表
        rainfall_tiles_dir.mkdir(parents=True, exist_ok=True)
        return jsonify({"message": []}), HTTPStatus.OK
    
    # 获取所有降雨瓦片时间戳目录
    rainfall_timestamps = sorted([
        d.name for d in rainfall_tiles_dir.iterdir() 
        if d.is_dir() and not d.name.startswith('.')
    ])
    
    return jsonify({"message": rainfall_timestamps}), HTTPStatus.OK

@tile_bp.route('/api/rainfall-tiles/<simulation>/<timestamp>/<z>/<x>/<y>', methods=['GET'])
@handle_exceptions
def get_rainfall_tile_by_coordinates(simulation, timestamp, z, x, y):
    """根据坐标获取降雨瓦片的API端点"""
    if not simulation or not timestamp:
        return jsonify({"error": "必须指定simulation和timestamp参数"}), HTTPStatus.BAD_REQUEST
    
    # 构建降雨瓦片路径，与水深瓦片类似
    rainfall_tile_path = Config.DATA_DIR / "rainfall_data" / simulation / "tiles" / timestamp / z / x / f"{y}.png"
    
    # 检查文件是否存在
    if not rainfall_tile_path.exists():
        logger.warning(f"未找到降雨瓦片: {rainfall_tile_path}")
        return jsonify({"error": f"未找到降雨瓦片: {simulation}/{z}/{x}/{y}"}), HTTPStatus.NOT_FOUND
    
    return send_file(str(rainfall_tile_path)), HTTPStatus.OK

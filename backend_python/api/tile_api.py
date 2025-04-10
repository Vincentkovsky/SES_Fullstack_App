from flask import Blueprint, jsonify, request, send_file
from http import HTTPStatus
import logging
from utils.helpers import handle_exceptions, is_steed_mode
from services.tile_service import get_tiles_list, get_tile_path, get_historical_simulations

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
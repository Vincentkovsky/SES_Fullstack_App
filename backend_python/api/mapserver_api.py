#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MapServer API

提供WMS服务接口和元数据查询功能
"""

from flask import Blueprint, request, Response, current_app, jsonify
import os
import logging
from http import HTTPStatus
from typing import Dict, List, Any, Optional
from backend_python.services.mapserver_service import MapServerService

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
mapserver_bp = Blueprint('mapserver', __name__, url_prefix='/api/mapserver')

# 全局服务实例
service = None

@mapserver_bp.before_app_first_request
def initialize_service():
    """初始化MapServer服务"""
    global service
    
    # 获取配置
    config = current_app.config
    
    # 配置目录
    geotiff_dir = config.get('GEOTIFF_DIR', 'backend_python/data/3di_res/geotiff')
    template_path = config.get('MAPFILE_TEMPLATE', 'backend_python/mapserver/templates/simulation_template.map')
    output_dir = config.get('MAPFILE_OUTPUT_DIR', 'backend_python/mapserver/mapfiles')
    mapserver_cgi_url = config.get('MAPSERVER_CGI_URL', 'http://localhost/cgi-bin/mapserv')
    
    # 初始化服务
    service = MapServerService(
        geotiff_base_dir=geotiff_dir,
        mapfile_template_path=template_path,
        mapfile_output_dir=output_dir,
        mapserver_cgi_url=mapserver_cgi_url
    )
    
    logger.info(f"MapServer服务初始化成功")
    
    # 预生成所有MapFile
    service.generate_all_mapfiles()

@mapserver_bp.route('/simulations', methods=['GET'])
def get_simulations():
    """
    获取所有可用的simulation列表
    
    Returns:
        JSON响应: {"simulations": [...]}
    """
    global service
    
    if service is None:
        initialize_service()
    
    simulation_ids = service.get_simulation_ids()
    return jsonify({"simulations": simulation_ids})

@mapserver_bp.route('/simulations/<simulation_id>/timestamps', methods=['GET'])
def get_timestamps(simulation_id):
    """
    获取特定simulation的所有时间戳
    
    Args:
        simulation_id: 模拟ID
        
    Returns:
        JSON响应: {"timestamps": [...]}
    """
    global service
    
    if service is None:
        initialize_service()
    
    timestamps = service.get_timestamps_for_simulation(simulation_id)
    return jsonify({"timestamps": timestamps})

@mapserver_bp.route('/simulations/<simulation_id>/metadata', methods=['GET'])
def get_simulation_metadata(simulation_id):
    """
    获取特定simulation的元数据
    
    Args:
        simulation_id: 模拟ID
        
    Returns:
        JSON响应: 包含元数据信息
    """
    global service
    
    if service is None:
        initialize_service()
    
    # 检查simulation_id是否存在
    if simulation_id not in service.get_simulation_ids():
        return jsonify({"error": f"模拟 {simulation_id} 不存在"}), HTTPStatus.NOT_FOUND
    
    # 获取时间戳列表
    timestamps = service.get_timestamps_for_simulation(simulation_id)
    
    # 获取边界框
    bbox = service.get_bbox_for_simulation(simulation_id)
    
    # 获取MapFile路径
    mapfile_path = service.get_mapfile_path(simulation_id)
    
    metadata = {
        "simulation_id": simulation_id,
        "timestamps": timestamps,
        "bbox": bbox,
        "timestamp_count": len(timestamps),
        "mapfile_path": mapfile_path
    }
    
    return jsonify(metadata)

@mapserver_bp.route('/map/<simulation_id>', methods=['GET'])
def get_map(simulation_id):
    """
    提供WMS地图服务
    
    Args:
        simulation_id: 模拟ID
        
    查询参数:
        timestamp: 可选的特定时间戳
        其他标准WMS参数 (FORMAT, BBOX, WIDTH, HEIGHT等)
        
    Returns:
        图像或XML响应
    """
    global service
    
    if service is None:
        initialize_service()
    
    # 检查simulation_id是否存在
    if simulation_id not in service.get_simulation_ids():
        return jsonify({"error": f"模拟 {simulation_id} 不存在"}), HTTPStatus.NOT_FOUND
    
    # 获取MapFile路径
    mapfile_path = service.get_mapfile_path(simulation_id)
    if not mapfile_path:
        return jsonify({"error": f"无法获取模拟 {simulation_id} 的MapFile"}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    # 从请求中获取时间戳
    timestamp = request.args.get('timestamp')
    
    # 构建MapServer CGI请求参数
    params = dict(request.args)
    params['map'] = mapfile_path
    
    # 如果没有指定SERVICE参数，默认使用WMS
    if 'SERVICE' not in params:
        params['SERVICE'] = 'WMS'
    
    # 如果指定了时间戳但没有指定图层，使用相应的图层
    if timestamp and 'LAYERS' not in params:
        params['LAYERS'] = f"waterdepth_{timestamp}"
    
    # 调用MapServer CGI
    try:
        content, content_type = service.call_mapserver(params)
        return Response(content, mimetype=content_type)
    except Exception as e:
        logger.error(f"调用MapServer CGI出错: {str(e)}")
        return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

@mapserver_bp.route('/legend/<simulation_id>', methods=['GET'])
def get_legend(simulation_id):
    """
    获取水深度图例
    
    Args:
        simulation_id: 模拟ID
        
    Returns:
        图例图像
    """
    global service
    
    if service is None:
        initialize_service()
    
    # 检查simulation_id是否存在
    if simulation_id not in service.get_simulation_ids():
        return jsonify({"error": f"模拟 {simulation_id} 不存在"}), HTTPStatus.NOT_FOUND
    
    # 获取MapFile路径
    mapfile_path = service.get_mapfile_path(simulation_id)
    
    # 构建请求参数
    params = {
        'map': mapfile_path,
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetLegendGraphic',
        'LAYER': request.args.get('LAYER', 'all_waterdepth'),
        'FORMAT': 'image/png'
    }
    
    # 调用MapServer CGI
    try:
        content, content_type = service.call_mapserver(params)
        return Response(content, mimetype=content_type)
    except Exception as e:
        logger.error(f"获取图例时出错: {str(e)}")
        return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR 
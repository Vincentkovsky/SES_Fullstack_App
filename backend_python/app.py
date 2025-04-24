#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask应用主入口

提供REST API服务。
"""

from flask import Flask, jsonify
from flask_cors import CORS
from http import HTTPStatus
from dotenv import load_dotenv
import logging

# 导入核心模块
from core.config import Config
from core.logging import setup_logging

# 导入API蓝图
from api import (
    water_depth_bp,
    tile_bp,
    inference_bp,
    gauging_bp,
    cache_bp,
    health_bp,
    mapserver_bp  # 新增：MapServer API
)

# 加载环境变量
load_dotenv()

# 设置日志
logger = setup_logging()

def create_app():
    """
    创建并配置Flask应用
    
    Returns:
        Flask: 配置好的Flask应用实例
    """
    app = Flask(__name__)
    
    # 允许跨域请求
    CORS(app, resources={
        r"/*": {
            "origins": Config.CORS_ORIGINS.split(','),
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })
    
    # 注册所有蓝图
    app.register_blueprint(water_depth_bp)
    app.register_blueprint(tile_bp)
    app.register_blueprint(inference_bp)
    app.register_blueprint(gauging_bp)
    app.register_blueprint(cache_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(mapserver_bp)  # 新增：注册MapServer API蓝图
    
    # 配置MapServer相关设置
    app.config['GEOTIFF_DIR'] = Config.GEOTIFF_DIR
    app.config['MAPFILE_TEMPLATE'] = Config.MAPFILE_TEMPLATE
    app.config['MAPFILE_OUTPUT_DIR'] = Config.MAPFILE_OUTPUT_DIR
    app.config['MAPSERVER_CGI_URL'] = Config.MAPSERVER_CGI_URL
    
    @app.route('/')
    def index():
        """首页路由"""
        return jsonify({
            "message": "欢迎使用水深度API服务",
            "status": "运行中",
            "api_version": "1.0"
        })
    
    # 错误处理
    @app.errorhandler(404)
    def not_found(error):
        """处理404错误"""
        return jsonify({
            "error": "Not found",
            "message": "The requested resource was not found"
        }), HTTPStatus.NOT_FOUND

    @app.errorhandler(500)
    def server_error(error):
        """处理500错误"""
        return jsonify({
            "error": "Internal server error",
            "message": str(error) if Config.DEBUG else "An unexpected error occurred"
        }), HTTPStatus.INTERNAL_SERVER_ERROR
    
    return app

if __name__ == '__main__':
    # 验证配置
    if not Config.validate():
        logger.warning("配置验证失败，但应用仍将继续启动。某些功能可能不可用。")
    
    # 显示应用配置信息
    logger.info(f"Starting application in {'DEBUG' if Config.DEBUG else 'PRODUCTION'} mode")
    logger.info(f"Listening on {Config.HOST}:{Config.PORT}")
    
    # 运行应用
    app = create_app()
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
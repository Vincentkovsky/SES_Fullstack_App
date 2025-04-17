#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask测试应用

用于测试水深度API和栅格数据API。
"""

from flask import Flask, jsonify
from flask_cors import CORS
import logging

# 导入API蓝图
from api.water_depth_api import water_depth_bp
from api.raster_api import raster_bp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 允许跨域请求
CORS(app)

# 注册蓝图
app.register_blueprint(water_depth_bp)
app.register_blueprint(raster_bp)

@app.route('/')
def index():
    """首页路由"""
    return jsonify({
        "message": "欢迎使用API测试服务",
        "status": "运行中",
        "available_endpoints": [
            "/api/water-depth",
            "/api/simulations",
            "/api/timestamps",
            "/api/tiles/{simulation_id}/{timestep_id}/{z}/{x}/{y}.png",
            "/api/colormap",
            "/api/metadata/{simulation_id}"
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000) 
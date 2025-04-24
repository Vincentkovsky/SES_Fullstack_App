#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置模块

从环境变量加载配置项并提供全局访问。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class Config:
    """配置类"""
    
    # API密钥
    WATERNSW_API_KEY = os.getenv('WATERNSW_API_KEY', '')
    THREEDI_API_PERSONAL_API_TOKEN = os.getenv('THREEDI_API_PERSONAL_API_TOKEN', '')
    
    # 文件路径配置
    TILES_BASE_PATH = os.getenv('TILES_BASE_PATH', '/projects/TCCTVS/FSI/cnnModel/inference')
    INFERENCE_SCRIPT = os.getenv('INFERENCE_SCRIPT', '/projects/TCCTVS/FSI/cnnModel/run_inference_w.sh')
    
    # 数据目录配置
    DATA_DIR = os.getenv('DATA_DIR', 'backend_python/data')
    GEOTIFF_DIR = os.getenv('GEOTIFF_DIR', 'backend_python/data/3di_res/geotiff')
    DEM_FILE = os.getenv('DEM_FILE', 'backend_python/data/3di/dem_wagga_wagga.tif')
    
    # MapServer配置
    MAPFILE_TEMPLATE = os.getenv('MAPFILE_TEMPLATE', 'backend_python/mapserver/templates/simulation_template.map')
    MAPFILE_OUTPUT_DIR = os.getenv('MAPFILE_OUTPUT_DIR', 'backend_python/mapserver/mapfiles')
    MAPSERVER_CGI_URL = os.getenv('MAPSERVER_CGI_URL', 'http://localhost/cgi-bin/mapserv')
    
    # 应用配置
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    HOST = os.getenv('FLASK_HOST', 'localhost')
    PORT = int(os.getenv('FLASK_PORT', '5000'))
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173')
    
    # 缓存配置
    CACHE_DURATION = int(os.getenv('CACHE_DURATION', '3600'))  # 默认缓存1小时
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """
        将配置转换为字典
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        return {key: value for key, value in cls.__dict__.items() 
                if not key.startswith('__') and not callable(value)}
    
    @classmethod
    def validate(cls) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        required_keys = [
            'WATERNSW_API_KEY',
            'THREEDI_API_PERSONAL_API_TOKEN'
        ]
        
        for key in required_keys:
            if not getattr(cls, key):
                return False
        
        return True

def get_env(key: str, default: Any = None) -> Any:
    """获取环境变量，提供类型转换"""
    value = os.getenv(key, default)
    if isinstance(default, bool):
        return value.lower() in ('true', '1', 't') if isinstance(value, str) else bool(value)
    elif isinstance(default, int):
        return int(value) if value else default
    return value 
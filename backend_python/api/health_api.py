from flask import Blueprint, jsonify
from http import HTTPStatus
import logging
import os
from pathlib import Path
from utils.helpers import handle_exceptions, get_timestamp
from dotenv import load_dotenv
from core.config import Config

logger = logging.getLogger(__name__)

# 创建蓝图
health_bp = Blueprint('health', __name__)

@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "timestamp": get_timestamp(),
        "version": "1.0.0"
    }), HTTPStatus.OK

@health_bp.route('/api/sync-env', methods=['POST'])
@handle_exceptions
def sync_env_endpoint():
    """手动触发前端环境变量同步的API端点"""
    try:
        sync_frontend_env_vars()
        return jsonify({
            "message": "环境变量同步成功",
            "timestamp": get_timestamp()
        }), HTTPStatus.OK
    except Exception as e:
        logger.error(f"同步环境变量失败: {str(e)}")
        return jsonify({
            "error": "同步环境变量失败",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR

def sync_frontend_env_vars():
    """
    将前端需要的环境变量从后端.env文件同步到前端.env文件
    只同步以VITE_开头的变量
    """
    backend_env_path = Path(__file__).parent.parent / ".env"
    frontend_env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
    
    if not backend_env_path.exists():
        logger.warning("后端.env文件不存在，无法同步前端环境变量")
        return
    
    # 读取后端.env文件
    vite_vars = {}
    with open(backend_env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                if key.startswith('VITE_'):
                    vite_vars[key] = value
    
    # 如果前端.env文件存在，读取并保留非VITE_变量
    existing_vars = {}
    if frontend_env_path.exists():
        with open(frontend_env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    if not key.startswith('VITE_'):
                        existing_vars[key] = value
    
    # 合并变量并写入前端.env文件
    with open(frontend_env_path, 'w') as f:
        # 首先写入注释
        f.write("# 此文件由后端自动生成，包含前端所需的环境变量\n")
        f.write("# 请勿直接修改，应该修改后端的.env文件\n\n")
        
        # 写入VITE_变量
        for key, value in vite_vars.items():
            f.write(f"{key}={value}\n")
        
        # 写入其他非VITE_变量
        if existing_vars:
            f.write("\n# 其他前端特定变量\n")
            for key, value in existing_vars.items():
                f.write(f"{key}={value}\n")
    
    logger.info(f"已同步前端环境变量到 {frontend_env_path}") 
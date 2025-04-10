import os
import subprocess
import logging
from typing import Dict, Any, Tuple
from http import HTTPStatus
from pathlib import Path
from core.config import Config
from utils.helpers import get_timestamp

logger = logging.getLogger(__name__)

def execute_inference_script() -> Tuple[Dict[str, Any], int]:
    """
    执行推理脚本并返回带有时间戳的结果
    
    Returns:
        Tuple[Dict[str, Any], int]: 响应数据和HTTP状态码
    """
    script_path = Config.INFERENCE_SCRIPT
    
    if not os.path.exists(script_path):
        logger.error(f"未找到推理脚本: {script_path}")
        return {"error": "未找到推理脚本"}, HTTPStatus.NOT_FOUND
    
    try:
        # 生成当前时间戳
        start_tmp = get_timestamp()
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 使用subprocess.run执行脚本，并捕获输出
        result = subprocess.run(
            [script_path],
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=True,
            check=True  # 如果返回非零状态码则抛出异常
        )
        
        return {
            "message": "推理完成",
            "timestamp": start_tmp,
            "output": result.stdout
        }, HTTPStatus.OK
            
    except subprocess.CalledProcessError as e:
        logger.error(f"推理脚本执行失败，返回代码: {e.returncode}, 错误: {e.stderr}")
        return {
            "error": "推理脚本执行失败",
            "details": e.stderr
        }, HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as e:
        logger.error(f"推理过程中发生意外错误: {str(e)}")
        return {
            "error": "推理过程中发生意外错误",
            "details": str(e)
        }, HTTPStatus.INTERNAL_SERVER_ERROR

def get_latest_inference_dir() -> Path:
    """
    获取最新的推理目录
    
    Returns:
        Path: 最新推理目录的路径，如果不存在则返回None
    """
    try:
        inference_dirs = sorted([
            d for d in os.listdir(Config.TILES_BASE_PATH)
            if (Config.TILES_BASE_PATH / d).is_dir()
        ], reverse=True)
        
        if not inference_dirs:
            return None
            
        return Config.TILES_BASE_PATH / inference_dirs[0]
    except (FileNotFoundError, PermissionError):
        logger.error(f"无法访问推理目录: {Config.TILES_BASE_PATH}")
        return None 
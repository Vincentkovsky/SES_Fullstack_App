import os
import glob
import time
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from http import HTTPStatus

from backend_python.core.config import Config
from backend_python.utils.helpers import get_timestamp

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

def get_latest_inference_dir() -> Optional[Path]:
    """
    获取最新的推理目录
    
    Returns:
        Optional[Path]: 最新推理目录的路径，如果不存在则返回None
    """
    base_path = Path(Config.TILES_BASE_PATH)
    
    try:
        if not base_path.exists():
            logger.warning(f"推理目录不存在: {base_path}")
            return None
            
        inference_dirs = sorted([
            d for d in os.listdir(base_path)
            if (base_path / d).is_dir()
        ], reverse=True)
        
        if not inference_dirs:
            logger.info(f"推理目录为空: {base_path}")
            return None
            
        return base_path / inference_dirs[0]
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"无法访问推理目录: {base_path}, 错误: {str(e)}")
        return None 
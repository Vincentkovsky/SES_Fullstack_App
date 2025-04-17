from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, Any
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from core.config import Config
from core.fastapi_helpers import async_handle_exceptions, get_timestamp

logger = logging.getLogger(__name__)

# 创建API路由器
router = APIRouter(prefix="/api")

@router.get("/health", response_model=Dict[str, Any])
async def health_check() -> Dict[str, Any]:
    """健康检查接口"""
    return {
        "status": "ok",
        "timestamp": get_timestamp(),
        "version": "1.0.0"
    }

@router.post("/sync-env", response_model=Dict[str, Any])
@async_handle_exceptions
async def sync_env_endpoint(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """手动触发前端环境变量同步的API端点"""
    try:
        # 使用后台任务进行同步，避免阻塞API响应
        background_tasks.add_task(sync_frontend_env_vars)
        
        return {
            "message": "环境变量同步已开始",
            "timestamp": get_timestamp()
        }
    except Exception as e:
        logger.error(f"同步环境变量失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "同步环境变量失败",
                "details": str(e)
            }
        )

async def sync_frontend_env_vars():
    """
    将前端需要的环境变量从后端.env文件同步到前端.env文件
    只同步以VITE_开头的变量
    
    使用异步IO操作以避免阻塞
    """
    backend_env_path = Path(__file__).parent.parent / ".env"
    frontend_env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
    
    if not backend_env_path.exists():
        logger.warning("后端.env文件不存在，无法同步前端环境变量")
        return
    
    try:
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
    except Exception as e:
        logger.error(f"同步前端环境变量失败: {str(e)}")
        raise e 
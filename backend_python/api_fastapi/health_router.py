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
    将环境变量从后端同步到前端
    1. 读取后端的环境变量
    2. 为所有变量添加VITE_前缀
    3. 写入到前端的单个.env文件中
    """
    # 获取当前环境模式
    env_mode = Config.ENV_MODE
    
    # 确定源文件和目标文件路径
    backend_env_path = Path(__file__).parent.parent / f".env.{env_mode}"
    frontend_env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
    
    try:
        # 读取后端环境变量
        env_vars = {}
        
        if not backend_env_path.exists():
            logger.warning(f"后端配置文件不存在: {backend_env_path}")
            return
            
        logger.info(f"正在读取后端配置文件: {backend_env_path}")
        with open(backend_env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 添加VITE_前缀（如果还没有）
                    if not key.startswith('VITE_'):
                        key = f'VITE_{key}'
                    
                    env_vars[key] = value
        
        # 写入前端配置文件
        os.makedirs(os.path.dirname(frontend_env_path), exist_ok=True)
        
        with open(frontend_env_path, 'w') as f:
            # 写入文件头注释
            f.write("# 此文件由后端自动生成，包含前端所需的环境变量\n")
            f.write(f"# 基于后端 {env_mode} 环境的配置自动生成\n")
            f.write("# 请勿直接修改此文件，应该修改后端的对应.env文件\n\n")
            
            # 写入环境变量，按字母顺序排序
            for key, value in sorted(env_vars.items()):
                f.write(f"{key}={value}\n")
        
        logger.info(f"已同步环境变量到前端 ({len(env_vars)} 个变量)")
        logger.info(f"目标文件: {frontend_env_path}")
        
    except Exception as e:
        logger.error(f"同步前端环境变量失败: {str(e)}")
        raise e 
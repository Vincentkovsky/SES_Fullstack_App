import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Config:
    """应用配置类"""
    
    # 环境模式配置
    ENV_MODE = os.getenv('ENV_MODE', 'development')
    
    @classmethod
    def is_development(cls) -> bool:
        """是否为开发环境"""
        return cls.ENV_MODE == 'development'
    
    @classmethod
    def is_production(cls) -> bool:
        """是否为生产环境"""
        return cls.ENV_MODE == 'production'
    
    # 前端配置
    FRONTEND_PORT = int(os.getenv('FRONTEND_PORT', '5173'))
    
    # API密钥从环境变量获取
    API_KEY = os.getenv('WATERNSW_API_KEY')
    WATERNSW_BASE_URL = "https://api.waternsw.com.au/water/"
    WATERNSW_SURFACE_WATER_ENDPOINT = "surface-water-data-api_download"
    
    # 文件路径使用Path对象，这样更加跨平台兼容
    TILES_BASE_PATH = Path(os.getenv('TILES_BASE_PATH', "/projects/TCCTVS/FSI/cnnModel/inference"))
    HISTORICAL_SIMULATIONS_PATH = Path(__file__).parent.parent / "data/3di_res/tiles"
    DATA_DIR = Path(__file__).parent.parent / "data"
    
    # 创建必要的目录
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "3di_res").mkdir(exist_ok=True)
    
    # 根据环境选择推理脚本路径
    INFERENCE_SCRIPT = os.getenv('INFERENCE_SCRIPT', "/projects/TCCTVS/FSI/cnnModel/run_inference_w.sh")
    
    # CORS配置 - 根据环境和前端端口设置不同的默认值
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 
                            f"http://localhost:{FRONTEND_PORT}" if ENV_MODE == 'development' 
                            else "https://yourdomain.com")
    
    # 应用配置 - 根据环境设置不同的默认值
    DEBUG = os.getenv('BACKEND_DEBUG', 'True' if ENV_MODE == 'development' else 'False').lower() in ('true', '1', 't')
    HOST = os.getenv('HOST', 'localhost' if ENV_MODE == 'development' else '0.0.0.0')
    PORT = int(os.getenv('BACKEND_PORT', '3000'))
    
    # 缓存配置 - 开发环境使用较短的缓存时间
    CACHE_EXPIRY_SECONDS = 60 * 5 if ENV_MODE == 'development' else 60 * 15  # 开发环境5分钟，生产环境15分钟
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置是否有效"""
        missing_vars = []
        
        # 检查关键API密钥
        if not cls.API_KEY:
            missing_vars.append("WATERNSW_API_KEY")
        
        # 检查关键路径
        if not os.path.exists(cls.INFERENCE_SCRIPT):
            logger.warning(f"推理脚本路径不存在: {cls.INFERENCE_SCRIPT}")
        
        # 检查环境模式
        if cls.ENV_MODE not in ['development', 'production']:
            logger.warning(f"未知的环境模式: {cls.ENV_MODE}")
        
        # 检查前端端口
        if not isinstance(cls.FRONTEND_PORT, int) or cls.FRONTEND_PORT <= 0:
            logger.warning(f"无效的前端端口: {cls.FRONTEND_PORT}")
        
        if missing_vars:
            logger.warning(f"缺少关键环境变量: {', '.join(missing_vars)}")
            return False
            
        return True
    
    @classmethod
    def get_environment_info(cls) -> Dict[str, Any]:
        """获取当前环境配置信息"""
        return {
            "mode": cls.ENV_MODE,
            "debug": cls.DEBUG,
            "host": cls.HOST,
            "port": cls.PORT,
            "frontend_port": cls.FRONTEND_PORT,
            "cors_origins": cls.CORS_ORIGINS,
            "cache_expiry": cls.CACHE_EXPIRY_SECONDS
        }

def get_env(key: str, default: Any = None) -> Any:
    """获取环境变量，提供类型转换"""
    value = os.getenv(key, default)
    if isinstance(default, bool):
        return value.lower() in ('true', '1', 't') if isinstance(value, str) else bool(value)
    elif isinstance(default, int):
        return int(value) if value else default
    return value 
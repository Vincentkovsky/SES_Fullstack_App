import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Config:
    """应用配置类"""
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
    
    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000')
    
    # 应用配置
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    HOST = os.getenv('FLASK_HOST', 'localhost')
    PORT = int(os.getenv('FLASK_PORT', 3000))
    
    # 缓存配置
    CACHE_EXPIRY_SECONDS = 60 * 15  # 15分钟
    
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
        
        if missing_vars:
            logger.warning(f"缺少关键环境变量: {', '.join(missing_vars)}")
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
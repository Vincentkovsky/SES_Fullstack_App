# 配置常量
class Config:
    """应用配置类"""
    # API密钥从环境变量获取
    API_KEY = os.getenv('WATERNSW_API_KEY')
    WATERNSW_BASE_URL = "https://api.waternsw.com.au/water/"
    WATERNSW_SURFACE_WATER_ENDPOINT = "surface-water-data-api_download"
    
    # 文件路径使用Path对象，这样更加跨平台兼容
    TILES_BASE_PATH = Path(os.getenv('TILES_BASE_PATH', "/projects/TCCTVS/FSI/cnnModel/inference"))
    LOCAL_TILES_PATH = Path(__file__).parent / "data/3di_res/timeseries_tiles"
    HISTORICAL_SIMULATIONS_PATH = Path(__file__).parent / "data/3di_res/tiles"
    DATA_DIR = Path(__file__).parent / "data"
    
    # 创建必要的目录
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "3di_res").mkdir(exist_ok=True)
    
    # 根据环境选择推理脚本路径
    INFERENCE_SCRIPT = os.getenv('INFERENCE_SCRIPT', "/projects/TCCTVS/FSI/cnnModel/run_inference_w.sh")
    
    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173')
    
    # 应用配置
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    HOST = os.getenv('FLASK_HOST', 'localhost')
    PORT = int(os.getenv('FLASK_PORT', 3001))  # 修改默认端口为3001 
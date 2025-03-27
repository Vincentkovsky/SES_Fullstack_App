from flask import Flask, jsonify, send_file, abort, request
from flask_cors import CORS
import os
import subprocess
from typing import Tuple, Dict, Union, List, Optional, Any
import logging
from datetime import datetime, timedelta
from marshmallow import Schema, fields, ValidationError
import requests
from urllib.parse import urljoin, urlencode
import json
import functools
from pathlib import Path
from http import HTTPStatus
from dotenv import load_dotenv
import shutil
import hashlib
from functools import lru_cache

# 加载环境变量
load_dotenv()

# 同步前端环境变量
def sync_frontend_env_vars():
    """
    将前端需要的环境变量从后端.env文件同步到前端.env文件
    只同步以VITE_开头的变量
    """
    backend_env_path = Path(__file__).parent / ".env"
    frontend_env_path = Path(__file__).parent.parent / "frontend" / ".env"
    
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

# 创建应用实例
app = Flask(__name__)

# 配置常量
class Config:
    """应用配置类"""
    # API密钥从环境变量获取
    API_KEY = os.getenv('WATERNSW_API_KEY')
    WATERNSW_BASE_URL = "https://api.waternsw.com.au/water/"
    WATERNSW_SURFACE_WATER_ENDPOINT = "surface-water-data-api_download"
    
    # 文件路径使用Path对象，这样更加跨平台兼容
    TILES_BASE_PATH = Path(os.getenv('TILES_BASE_PATH', "/projects/TCCTVS/FSI/cnnModel/inference"))
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
    PORT = int(os.getenv('FLASK_PORT', 3000))
    
    @classmethod
    def validate(cls):
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

# 配置日志记录 - 使用更详细的配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 将默认日志级别改为INFO，减少调试日志

# 创建控制台处理器并设置级别为INFO
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 将处理器添加到logger
logger.addHandler(console_handler)

# 移除测试日志输出
logger.info("日志系统已初始化")

# 尝试同步环境变量
try:
    sync_frontend_env_vars()
except Exception as e:
    logger.error(f"同步前端环境变量失败: {str(e)}")

# 配置CORS
CORS(app, resources={
    r"/*": {
        "origins": Config.CORS_ORIGINS.split(','),
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
    }
})

# 错误处理装饰器
def handle_exceptions(func):
    """装饰器: 统一处理API端点的异常"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            return jsonify({
                'error': 'Validation error',
                'message': str(e)
            }), HTTPStatus.BAD_REQUEST
        except requests.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return jsonify({
                'error': 'External API error',
                'message': str(e)
            }), HTTPStatus.BAD_GATEWAY
        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            return jsonify({
                'error': 'Resource not found',
                'message': str(e)
            }), HTTPStatus.NOT_FOUND
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e) if Config.DEBUG else 'An unexpected error occurred'
            }), HTTPStatus.INTERNAL_SERVER_ERROR
    return wrapper

# 添加端点来手动同步环境变量
@app.route('/api/sync-env', methods=['POST'])
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

# 数据模型
class SurfaceWaterRequestSchema(Schema):
    """验证地表水API请求参数的模式"""
    page_number = fields.Integer(required=False, validate=lambda n: n >= 1, default=1)
    data_type = fields.String(required=False, default="autoqc")
    frequency = fields.String(required=False, default="instantaneous")
    site_id = fields.String(required=False, default="410001")
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    variable = fields.String(required=False, default="StreamWaterLevel")

# 工具函数
def get_timestamp() -> str:
    """获取当前时间戳，格式化为字符串"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def is_steed_mode() -> bool:
    """检查是否处于STEED模式"""
    return request.args.get('isSteedMode', 'false').lower() == 'true'

def get_latest_inference_dir() -> Optional[Path]:
    """获取最新的推理目录"""
    try:
        inference_dirs = sorted([
            d for d in os.listdir(Config.TILES_BASE_PATH)
            if (Config.TILES_BASE_PATH / d).is_dir()
        ], reverse=True)
        
        if not inference_dirs:
            return None
            
        return Config.TILES_BASE_PATH / inference_dirs[-1]
    except (FileNotFoundError, PermissionError):
        logger.error(f"无法访问推理目录: {Config.TILES_BASE_PATH}")
        return None

# API端点实现
def execute_inference_script() -> Tuple[Dict[str, Any], int]:
    """执行推理脚本并返回带有时间戳的结果"""
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

# 创建简单的内存缓存
_water_data_cache = {}
_cache_expiry = {}  # 用于存储缓存过期时间

# 缓存的默认过期时间（秒）
CACHE_EXPIRY_SECONDS = 60 * 15  # 15分钟

def get_cache_key(params):
    """生成基于请求参数的缓存键"""
    # 将请求参数转换为排序后的元组列表，然后转为字符串并计算哈希值
    param_str = json.dumps(sorted(params.items()), sort_keys=True)
    return hashlib.md5(param_str.encode()).hexdigest()

def fetch_surface_water_data(site_id: str = "410001", 
                           start_date: str = "2024-03-24 00:00",
                           end_date: str = "2024-03-24 01:00",
                           frequency: str = "Instantaneous",
                           page_number: int = 1,
                           variable: str = "StreamWaterLevel",
                           use_cache: bool = True) -> Dict[str, Any]:
    """
    从WaterNSW API获取地表水数据
    
    Args:
        site_id: 站点ID (默认: 410001)
        start_date: 开始日期，格式为dd-MMM-yyyy HH:mm (例如: "24-Mar-2024 00:00")
        end_date: 结束日期，格式为dd-MMM-yyyy HH:mm (例如: "24-Mar-2024 01:00")
        frequency: 数据频率 (Instantaneous或Latest)
        page_number: 分页的页码
        variable: 变量类型 (StreamWaterLevel或FlowRate)
        use_cache: 是否使用缓存 (默认: True)
    
    Returns:
        Dict[str, Any]: 包含数据和缓存状态的字典
    """
    # 构建参数字典以便生成缓存键
    params = {
        'siteId': site_id,
        'frequency': frequency,
        'dataType': 'AutoQC',
        'pageNumber': page_number,
        'startDate': start_date,
        'endDate': end_date,
        'variable': variable
    }
    
    # 生成缓存键
    cache_key = get_cache_key(params)
    
    # 检查缓存
    if use_cache and cache_key in _water_data_cache:
        # 检查缓存是否过期
        if datetime.now() < _cache_expiry.get(cache_key, datetime.min):
            return {
                'data': _water_data_cache[cache_key],
                'from_cache': True,
                'cache_key': cache_key
            }
        else:
            # 缓存已过期，从缓存中移除
            if cache_key in _water_data_cache:
                del _water_data_cache[cache_key]
            if cache_key in _cache_expiry:
                del _cache_expiry[cache_key]
    
    # 如果缓存中没有或已过期，则从API获取数据
    url = urljoin(Config.WATERNSW_BASE_URL, Config.WATERNSW_SURFACE_WATER_ENDPOINT)
    
    headers = {
        'Ocp-Apim-Subscription-Key': Config.API_KEY,
        'Accept': 'application/json'
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=10)
    
    if response.status_code == 401:
        logger.error("WaterNSW API认证失败，请检查API密钥")
        raise Exception("WaterNSW API认证失败，请检查API密钥配置")
        
    response.raise_for_status()
    
    data = response.json()
    
    # 如果成功获取数据，更新缓存
    if use_cache:
        _water_data_cache[cache_key] = data
        _cache_expiry[cache_key] = datetime.now() + timedelta(seconds=CACHE_EXPIRY_SECONDS)
    
    return {
        'data': data,
        'from_cache': False,
        'cache_key': cache_key
    }

def process_water_data(waternsw_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理从WaterNSW获取的水数据，转换为时间序列格式"""
    timeseries_data = {}
    
    for record in waternsw_data.get('records', []):
        try:
            timestamp = record.get('timeStamp')
            if not timestamp:
                continue

            # 如果时间戳条目不存在则初始化
            if timestamp not in timeseries_data:
                timeseries_data[timestamp] = {
                    'timestamp': timestamp,
                    'waterLevel': None,
                    'flowRate': None
                }
            
            # 根据variableName更新适当的测量值
            variable_name = record.get('variableName')
            value = record.get('value')
            
            if variable_name == 'StreamWaterLevel':
                timeseries_data[timestamp]['waterLevel'] = value
            elif variable_name == 'FlowRate':
                timeseries_data[timestamp]['flowRate'] = value

        except (ValueError, TypeError) as e:
            logger.warning(f"解析记录时出错: {e}")
            continue
    
    # 将字典转换为排序列表
    sorted_timeseries = sorted(
        timeseries_data.values(),
        key=lambda x: x['timestamp']
    )
    
    # 构建响应数据
    site_id = waternsw_data.get('records', [{}])[0].get('siteId', '410001')
    response_data = {
        'site_id': site_id,
        'timeseries': sorted_timeseries,
        'total_records': len(sorted_timeseries)
    }
    
    return response_data

# API路由
@app.route('/api/run-inference', methods=['POST'])
@handle_exceptions
def run_inference():
    """
    API端点用于触发模型推理
    """
    response, status_code = execute_inference_script()
    return jsonify(response), status_code


@app.route('/api/tilesList', methods=['GET'])
@handle_exceptions
def get_tiles_list():
    """获取瓦片列表的API端点"""
    if is_steed_mode():
        # STEED模式: 使用推理输出目录
        latest_inference_dir = get_latest_inference_dir()
        
        if not latest_inference_dir:
            return jsonify({"error": "STEED模式下没有可用的瓦片"}), HTTPStatus.NOT_FOUND

        # 获取最新的推理目录名称
        latest_inference = latest_inference_dir.name
        tiles_path = latest_inference_dir / f"timeseries_tiles_{latest_inference}"
        
        if not tiles_path.exists():
            return jsonify({"error": "STEED模式下瓦片尚未生成"}), HTTPStatus.NOT_FOUND
            
        # 列出瓦片目录中的所有时间戳
        timestamps = sorted(
            name for name in os.listdir(tiles_path)
            if (tiles_path / name).is_dir()
        )
    else:
        # 检查是否指定了特定的模拟
        simulation = request.args.get('simulation')
        
        # 处理特殊的字符串值
        if simulation in ["null", "undefined", ""] or simulation is None:
            return jsonify({"error": "本地模式下必须指定simulation参数"}), HTTPStatus.BAD_REQUEST
            
        # 使用指定的历史模拟目录
        tiles_path = Config.HISTORICAL_SIMULATIONS_PATH / simulation
        if not tiles_path.exists():
            return jsonify({"error": f"未找到指定的历史模拟: {simulation}"}), HTTPStatus.NOT_FOUND
            
        timestamps = sorted(
            name for name in os.listdir(tiles_path)
            if (tiles_path / name).is_dir()
        )
    
    return jsonify({"message": timestamps}), HTTPStatus.OK

@app.route('/api/tiles/<timestamp>/<z>/<x>/<y>', methods=['GET'])
@handle_exceptions
def get_tile_by_coordinates(timestamp, z, x, y):
    """根据坐标获取瓦片的API端点"""
    if is_steed_mode():
        # STEED模式: 使用推理输出目录
        latest_inference_dir = get_latest_inference_dir()
        
        if latest_inference_dir:
            latest_inference = latest_inference_dir.name
            tile_path = (
                latest_inference_dir
                / f"timeseries_tiles_{latest_inference}"
                / timestamp
                / z
                / x
                / f"{y}.png"
            )

            if tile_path.exists():
                return send_file(tile_path), HTTPStatus.OK
        
        return jsonify({"error": "STEED模式下未找到瓦片"}), HTTPStatus.NOT_FOUND
    else:
        # 检查是否指定了特定的模拟
        simulation = request.args.get('simulation')
        
        # 处理特殊的字符串值
        if simulation in ["null", "undefined", ""] or simulation is None:
            # 本地模式下必须提供simulation参数
            return jsonify({"error": "本地模式下必须指定simulation参数"}), HTTPStatus.BAD_REQUEST
        
        # 使用指定的历史模拟目录
        tile_path = (
            Config.HISTORICAL_SIMULATIONS_PATH
            / simulation
            / timestamp
            / z
            / x
            / f"{y}.png"
        )

        # 只保留一条info级别日志语句记录瓦片路径
        logger.info(f"瓦片路径 (simulation={simulation}): {tile_path}")
        
        if tile_path.exists():
            return send_file(tile_path), HTTPStatus.OK
            
        return jsonify({"error": f"未找到瓦片 (simulation={simulation})"}), HTTPStatus.NOT_FOUND

@app.route('/api/tiles/simulation/<simulation>/<timestamp>/<z>/<x>/<y>', methods=['GET'])
@handle_exceptions
def get_tile_by_coordinates_with_simulation(simulation, timestamp, z, x, y):
    """明确包含simulation参数的瓦片API端点"""
    # 使用指定的历史模拟目录
    tile_path = (
        Config.HISTORICAL_SIMULATIONS_PATH
        / simulation
        / timestamp
        / z
        / x
        / f"{y}.png"
    )
    
    # 只保留一条info级别日志语句记录瓦片路径
    logger.info(f"瓦片路径 (simulation={simulation}): {tile_path}")
    
    if tile_path.exists():
        return send_file(tile_path), HTTPStatus.OK
        
    return jsonify({"error": f"未找到瓦片 (simulation={simulation})"}), HTTPStatus.NOT_FOUND

@app.route('/api/gauging', methods=['GET'])
@handle_exceptions
def get_gauging_data():
    """
    获取地表水数据并返回时间序列
    
    查询参数:
    - start_date: 字符串 (可选) - 开始日期，格式为dd-MMM-yyyy HH:mm
    - end_date: 字符串 (可选) - 结束日期，格式为dd-MMM-yyyy HH:mm
    - frequency: 字符串 (可选) - 数据频率 (instantaneous或latest)
    - page_number: 整数 (可选) - 分页页码 (最小值: 1)
    - bypass_cache: 布尔值 (可选) - 是否绕过缓存 (默认: false)
    
    返回:
        包含时间序列数据的JSON响应
    """
    # 获取查询参数
    schema = SurfaceWaterRequestSchema()
    params = schema.load({
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'frequency': request.args.get('frequency', 'instantaneous'),
        'page_number': request.args.get('page_number', type=int, default=1),
        'site_id': '410001'  # Wagga Wagga的固定站点ID
    })
    
    # 检查是否需要绕过缓存
    bypass_cache = request.args.get('bypass_cache', 'false').lower() in ('true', '1', 't', 'yes')
    
    # 从WaterNSW API获取数据
    result = fetch_surface_water_data(**params, use_cache=not bypass_cache)
    
    # 处理并返回数据
    response_data = process_water_data(result['data'])
    
    # 添加缓存信息到响应
    response_data['cache_info'] = {
        'from_cache': result['from_cache'],
        'bypass_cache': bypass_cache,
        'timestamp': get_timestamp(),
        'cache_key': result['cache_key'][:8] + "..." if result['from_cache'] else None
    }
    
    return jsonify(response_data), HTTPStatus.OK

@app.route('/api/test-waternsw', methods=['GET'])
@handle_exceptions
def test_waternsw():
    """测试WaterNSW API连接"""
    # 默认绕过缓存来测试API连接
    bypass_cache = request.args.get('bypass_cache', 'true').lower() in ('true', '1', 't', 'yes')
    
    # 尝试获取最新的读数
    data = fetch_surface_water_data(
        site_id="410001",
        frequency="latest",
        use_cache=not bypass_cache
    )
    
    return jsonify({
        "message": "WaterNSW API连接成功",
        "from_cache": not bypass_cache and get_cache_key({
            'siteId': "410001",
            'frequency': "latest",
            'dataType': 'AutoQC',
            'pageNumber': 1,
            'variable': "StreamWaterLevel"
        }) in _water_data_cache,
        "bypass_cache": bypass_cache,
        "timestamp": get_timestamp(),
        "data": data['data']
    }), HTTPStatus.OK

@app.route('/api/historical-simulations', methods=['GET'])
@handle_exceptions
def get_historical_simulations():
    """获取历史模拟文件夹列表的API端点"""
    if not Config.HISTORICAL_SIMULATIONS_PATH.exists():
        return jsonify({"error": "未找到历史模拟目录"}), HTTPStatus.NOT_FOUND
        
    # 列出历史模拟目录中的所有文件夹
    simulations = sorted(
        name for name in os.listdir(Config.HISTORICAL_SIMULATIONS_PATH)
        if (Config.HISTORICAL_SIMULATIONS_PATH / name).is_dir()
    )
    
    return jsonify({"message": simulations}), HTTPStatus.OK

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "timestamp": get_timestamp(),
        "version": "1.0.0"
    }), HTTPStatus.OK

@app.route('/api/cache/stats', methods=['GET'])
@handle_exceptions
def get_cache_stats():
    """获取缓存统计信息的API端点"""
    stats = {
        "total_entries": len(_water_data_cache),
        "memory_usage_estimate_kb": sum(len(json.dumps(data)) for data in _water_data_cache.values()) // 1024 if _water_data_cache else 0,
        "entries": [
            {
                "cache_key": key[:8] + "...",  # 只显示键的前8个字符
                "expires_at": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "ttl_seconds": max(0, int((expiry - datetime.now()).total_seconds()))
            }
            for key, expiry in _cache_expiry.items()
        ]
    }
    return jsonify(stats), HTTPStatus.OK

@app.route('/api/cache/clear', methods=['POST'])
@handle_exceptions
def clear_cache():
    """清除所有缓存的API端点"""
    global _water_data_cache, _cache_expiry
    cache_size = len(_water_data_cache)
    _water_data_cache = {}
    _cache_expiry = {}
    return jsonify({
        "message": f"已清除缓存，共删除 {cache_size} 条记录",
        "timestamp": get_timestamp()
    }), HTTPStatus.OK

@app.route('/api/cache/prune', methods=['POST'])
@handle_exceptions
def prune_expired_cache():
    """清除过期缓存的API端点"""
    global _water_data_cache, _cache_expiry
    now = datetime.now()
    
    # 收集过期的键
    expired_keys = [key for key, expiry in _cache_expiry.items() if now >= expiry]
    
    # 删除过期的缓存项
    for key in expired_keys:
        if key in _water_data_cache:
            del _water_data_cache[key]
        if key in _cache_expiry:
            del _cache_expiry[key]
    
    return jsonify({
        "message": f"已清除过期缓存，共删除 {len(expired_keys)} 条记录",
        "timestamp": get_timestamp()
    }), HTTPStatus.OK

@app.errorhandler(404)
def not_found(error):
    """处理404错误"""
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found"
    }), HTTPStatus.NOT_FOUND

@app.errorhandler(500)
def server_error(error):
    """处理500错误"""
    return jsonify({
        "error": "Internal server error",
        "message": str(error) if Config.DEBUG else "An unexpected error occurred"
    }), HTTPStatus.INTERNAL_SERVER_ERROR

if __name__ == '__main__':
    # 验证配置
    if not Config.validate():
        logger.warning("配置验证失败，但应用仍将继续启动。某些功能可能不可用。")
    
    # 显示应用配置信息
    logger.info(f"Starting application in {'DEBUG' if Config.DEBUG else 'PRODUCTION'} mode")
    logger.info(f"Listening on {Config.HOST}:{Config.PORT}")
    
    # 运行应用
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
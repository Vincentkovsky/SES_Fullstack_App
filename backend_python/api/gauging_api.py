from flask import Blueprint, request, jsonify
from http import HTTPStatus
import logging
from marshmallow import Schema, fields, ValidationError
from utils.helpers import handle_exceptions, get_timestamp
from services.water_data_service import fetch_surface_water_data, process_water_data

logger = logging.getLogger(__name__)

# 创建蓝图
gauging_bp = Blueprint('gauging', __name__)

# 数据验证模式
class SurfaceWaterRequestSchema(Schema):
    """验证地表水API请求参数的模式"""
    page_number = fields.Integer(required=False, validate=lambda n: n >= 1, default=1)
    data_type = fields.String(required=False, default="autoqc")
    frequency = fields.String(required=False, default="instantaneous")
    site_id = fields.String(required=False, default="410001")
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    variable = fields.String(required=False, default="StreamWaterLevel")

@gauging_bp.route('/api/gauging', methods=['GET'])
@handle_exceptions
def get_gauging_data():
    """
    获取地表水数据并返回时间序列
    
    查询参数:
    - start_date: 字符串 (必需) - 开始日期，格式为dd-MMM-yyyy HH:mm
    - end_date: 字符串 (必需) - 结束日期，格式为dd-MMM-yyyy HH:mm
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

@gauging_bp.route('/api/test-waternsw', methods=['GET'])
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
        "from_cache": data['from_cache'],
        "bypass_cache": bypass_cache,
        "timestamp": get_timestamp(),
        "data": data['data']
    }), HTTPStatus.OK 
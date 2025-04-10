from flask import Blueprint, jsonify
from http import HTTPStatus
import logging
from utils.helpers import handle_exceptions, get_timestamp
from core.cache import get_cache_stats, clear_cache, prune_expired_cache

logger = logging.getLogger(__name__)

# 创建蓝图
cache_bp = Blueprint('cache', __name__)

@cache_bp.route('/api/cache/stats', methods=['GET'])
@handle_exceptions
def get_cache_stats_api():
    """获取缓存统计信息的API端点"""
    stats = get_cache_stats()
    return jsonify(stats), HTTPStatus.OK

@cache_bp.route('/api/cache/clear', methods=['POST'])
@handle_exceptions
def clear_cache_api():
    """清除所有缓存的API端点"""
    cache_size = clear_cache()
    return jsonify({
        "message": f"已清除缓存，共删除 {cache_size} 条记录",
        "timestamp": get_timestamp()
    }), HTTPStatus.OK

@cache_bp.route('/api/cache/prune', methods=['POST'])
@handle_exceptions
def prune_expired_cache_api():
    """清除过期缓存的API端点"""
    expired_count = prune_expired_cache()
    return jsonify({
        "message": f"已清除过期缓存，共删除 {expired_count} 条记录",
        "timestamp": get_timestamp()
    }), HTTPStatus.OK 
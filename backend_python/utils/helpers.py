import functools
from datetime import datetime
from flask import jsonify, request
from http import HTTPStatus
import logging
import requests
from marshmallow import ValidationError
from typing import Callable, Any, Dict, Tuple
from core.config import Config

logger = logging.getLogger(__name__)

def get_timestamp() -> str:
    """获取当前时间戳，格式化为字符串"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def is_steed_mode() -> bool:
    """检查是否处于STEED模式"""
    return request.args.get('isSteedMode', 'false').lower() == 'true'

def handle_exceptions(func: Callable) -> Callable:
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
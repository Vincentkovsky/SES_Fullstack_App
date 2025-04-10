from flask import Blueprint, jsonify
from http import HTTPStatus
import logging
from utils.helpers import handle_exceptions
from services.inference_service import execute_inference_script

logger = logging.getLogger(__name__)

# 创建蓝图
inference_bp = Blueprint('inference', __name__)

@inference_bp.route('/api/run-inference', methods=['POST'])
@handle_exceptions
def run_inference():
    """
    API端点用于触发模型推理
    """
    response, status_code = execute_inference_script()
    return jsonify(response), status_code 
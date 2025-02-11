from flask import Flask, jsonify, send_file, abort, request
from flask_cors import CORS
import os
import subprocess
from typing import Tuple, Dict, Union, List, Optional
import logging
from datetime import datetime, timedelta
import uuid
from marshmallow import Schema, fields, ValidationError
import requests
from urllib.parse import urljoin

app = Flask(__name__)

# # 配置 CORS
CORS(app, resources={
    r"/*": {  # 匹配所有路由
        "origins": "http://localhost:5173",  # 允许的前端地址
        "methods": ["GET", "POST", "PUT", "DELETE"],  # 允许的 HTTP 方法
        "allow_headers": ["Content-Type", "Authorization"],  # 允许的请求头
    }
})

# 添加日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_inference_script() -> Tuple[Dict[str, str], int]:
    """
    执行推理脚本并返回结果
    
    Returns:
        Tuple[Dict, int]: 包含执行结果和状态码的元组
    """
    # script_path = os.path.join(os.path.dirname(__file__), "../../cnnModel/run_inference.sh")

    
    script_path = "/projects/TCCTVS/FSI/cnnModel/run_inference_w.sh"
    
    if not os.path.exists(script_path):
        logger.error(f"Inference script not found at: {script_path}")
        return {"error": "Inference script not found"}, 404
    
    try:
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        print(f"Script path: {script_path}")
        
        # 执行脚本并捕获输出
        result = subprocess.run(
            [script_path],
        )
        print(f"Result: {result}")
        
        logger.info("Inference script executed successfully")
        return {
            "message": "Inference completed successfully",
            "output": result.stdout
        }, 200
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing inference script: {str(e)}")
        return {
            "error": "Inference script execution failed",
            "details": e.stderr
        }, 500
    except Exception as e:
        logger.error(f"Unexpected error during inference: {str(e)}")
        return {
            "error": "Unexpected error during inference",
            "details": str(e)
        }, 500

@app.route('/api/run-inference', methods=['POST'])
def run_inference():
    """
    API端点用于触发模型推理
    """
    response, status_code = execute_inference_script()
    return jsonify(response), status_code

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"message": "Hello, World!"}), 200

# 获取 timeseries_tiles 文件夹下的所有子文件夹名
@app.route('/api/tilesList', methods=['GET'])
def get_tiles_list():
    tiles_path = os.path.join(os.path.dirname(__file__), "data/3di_res/timeseries_tiles")
    try:
        # 列出所有子文件夹并按字母顺序排序
        directories = sorted(
            name for name in os.listdir(tiles_path)
            if os.path.isdir(os.path.join(tiles_path, name))
        )
        return jsonify({"message": directories}), 200
    except Exception as error:
        print(f"Error reading tiles directory: {error}")
        return jsonify({"error": "Unable to retrieve tiles list"}), 500

# 根据时间戳和坐标获取 tile
@app.route('/api/tiles/<timestamp>/<z>/<x>/<y>', methods=['GET'])
def get_tile_by_coordinates(timestamp, z, x, y):
    tile_path = os.path.join(
        os.path.dirname(__file__),
        f"data/3di_res/timeseries_tiles/{timestamp}/{z}/{x}/{y}.png"
    )
    print("Backend API hit")
    try:
        if os.path.exists(tile_path):
            # 如果文件存在，返回文件
            print("Tile found")
            return send_file(tile_path), 200
        else:
            # 如果文件不存在，返回 404
            print("Tile not found")
            return jsonify({"error": "Tile not found"}), 404
    except Exception as error:
        # 处理意外错误
        print(f"Error retrieving tile: {error}")
        return jsonify({"error": "Unable to retrieve tile"}), 500

API_KEY = "74c101d12b334d09b854cee56563e545"
WATERNSW_BASE_URL = "https://api.waternsw.com.au/water/"
WATERNSW_GAUGING_ENDPOINT = "gauging-api"

def fetch_waternsw_data(site_ids: List[str], start_date: str, end_date: Optional[str] = None, 
                       page_number: int = 1, request_id: Optional[str] = None) -> Dict:
    """
    Fetch gauging data from WaterNSW API
    
    Args:
        site_ids: List of site IDs
        start_date: Start date in dd-Mon-yyyy HH:mm format
        end_date: Optional end date in dd-Mon-yyyy HH:mm format
        page_number: Page number for pagination
        request_id: Request ID for pagination
    
    Returns:
        Dict containing the API response
    """
    url = urljoin(WATERNSW_BASE_URL, WATERNSW_GAUGING_ENDPOINT)
    
    params = {
        'SiteID': ','.join(site_ids),
        'StartDate': start_date,
        'PageNumber': page_number
    }
    
    if end_date:
        params['EndDate'] = end_date
    if request_id:
        params['RequestID'] = request_id
        
    headers = {
        'Ocp-Apim-Subscription-Key': API_KEY,
        'Cache-Control': 'no-cache',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        # Log the response for debugging
        logger.info(f"WaterNSW API Response: {response.status_code}")
        logger.info(f"Response Content: {response.text}")
        
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data from WaterNSW API: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response content: {e.response.text}")
        raise Exception(f"Failed to fetch data from WaterNSW: {str(e)}")

class GaugingRequestSchema(Schema):
    """Schema for validating gauging API request parameters"""
    api_key = fields.String(required=True, validate=lambda x: x == API_KEY)
    site_id = fields.String(required=True)
    start_date = fields.String(required=True)
    end_date = fields.String(required=False)
    page_number = fields.Integer(required=False, validate=lambda n: n >= 1)
    request_id = fields.UUID(required=False)

def validate_date_format(date_str: str) -> bool:
    """Validate if the date string matches the required format (dd-Mon-yyyy HH:mm)"""
    try:
        datetime.strptime(date_str, '%d-%b-%Y %H:%M')
        return True
    except ValueError:
        return False

def validate_site_ids(site_ids: List[str]) -> bool:
    """Validate if the number of site IDs is within the limit"""
    return len(site_ids) <= 20

@app.route('/api/gauging', methods=['GET'])
def get_gauging_data():
    """
    Fetch gauging data and return timeseries of MaxDepth values.
    
    Query Parameters:
    - start_date: String (required) - Start date in dd-Mon-yyyy HH:mm format
    - end_date: String (optional) - End date in dd-Mon-yyyy HH:mm format
    - page_number: Integer (optional) - Page number for pagination (min value: 1)
    - request_id: UUID (required when page_number > 1) - Request identifier
    
    Returns:
        JSON response with timeseries MaxDepth data
    """
    try:
        # Use fixed values for api_key and site_id
        site_ids = ['410001']  # Fixed site ID
        
        # Get remaining query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page_number = request.args.get('page_number', type=int, default=1)
        request_id = request.args.get('request_id')

        # Validate required parameters
        if not start_date:
            return jsonify({
                'error': 'Missing required parameters',
                'message': 'start_date is required'
            }), 400

        # Validate date formats
        if not validate_date_format(start_date):
            return jsonify({
                'error': 'Invalid start_date format',
                'message': 'Date format should be dd-Mon-yyyy HH:mm (e.g., 08-Jan-2021 08:30)'
            }), 400

        if end_date and not validate_date_format(end_date):
            return jsonify({
                'error': 'Invalid end_date format',
                'message': 'Date format should be dd-Mon-yyyy HH:mm (e.g., 08-Jan-2021 08:30)'
            }), 400

        # Validate request_id when page_number > 1
        if page_number > 1 and not request_id:
            return jsonify({
                'error': 'Missing request_id',
                'message': 'request_id is required when page_number is greater than 1'
            }), 400

        # Fetch real data from WaterNSW API
        try:
            waternsw_data = fetch_waternsw_data(
                site_ids=site_ids,
                start_date=start_date,
                end_date=end_date,
                page_number=page_number,
                request_id=request_id
            )
            
            # Transform the data into timeseries format
            unique_data = {}  # Use dictionary to track unique entries
            for gauging in waternsw_data.get('gaugings', []):
                try:
                    # Extract date and time components
                    measure_date = gauging.get('MeasureDate', '')
                    start_time = gauging.get('StartTime', '')
                    max_depth = gauging.get('MaxDepth', 0)
                    
                    if measure_date and start_time:
                        # Parse the date components
                        date_obj = datetime.strptime(f"{measure_date} {start_time}", "%d-%b-%Y %H:%M:%S" if ":00" in start_time else "%d-%b-%Y %H:%M")
                        timestamp = date_obj.isoformat()
                        
                        # Only add if timestamp doesn't exist or if the MaxDepth is different
                        if timestamp not in unique_data or unique_data[timestamp]['maxDepth'] != max_depth:
                            unique_data[timestamp] = {
                                'timestamp': timestamp,
                                'maxDepth': max_depth
                            }
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing date: {e}, measure_date: {measure_date}, start_time: {start_time}")
                    continue
            
            # Convert dictionary values to list and sort by timestamp
            timeseries_data = sorted(unique_data.values(), key=lambda x: x['timestamp'])
            
            response_data = {
                'site_id': site_ids[0],
                'timeseries': timeseries_data,
                'total_records': len(timeseries_data)
            }
            
            return jsonify(response_data), 200
            
        except Exception as e:
            return jsonify({
                'error': 'External API Error',
                'message': str(e)
            }), 502

    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in gauging API: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=3000)
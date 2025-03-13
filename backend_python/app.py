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
from urllib.parse import urljoin, urlencode
import json

app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": "http://localhost:5173",
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
    }
})

# Configure logging to only show errors
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Update the tiles path constants at the top of the file
TILES_BASE_PATH = "/projects/TCCTVS/FSI/cnnModel/inference"
LOCAL_TILES_PATH = os.path.join(os.path.dirname(__file__), "data/3di_res/timeseries_tiles")

def execute_inference_script() -> Tuple[Dict[str, str], int]:
    """Execute inference script and return results with timestamp"""
    # script_path = "/projects/TCCTVS/FSI/cnnModel/run_inference_w.sh"
    script_path = "/Users/vincentjin/Desktop/SES/cnnModel/run_inference_w.sh"
    
    if not os.path.exists(script_path):
        logger.error(f"Inference script not found at: {script_path}")
        return {"error": "Inference script not found"}, 404
    
    try:
        # Generate current timestamp
        start_tmp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure script has execution permissions
        os.chmod(script_path, 0o755)
        
        # Execute script with timestamp parameter
        result = subprocess.run(
            [script_path],
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # Use this instead of text=True
            shell=True  # Enable shell to modify the script inline
        )
        
        if result.returncode == 0:
            return {
                "message": "Inference completed successfully",
                "timestamp": start_tmp,
                "output": result.stdout
            }, 200
        else:
            logger.error(f"Inference script failed with return code {result.returncode} {result.stderr}")
            return {
                "error": "Inference script execution failed",
                "details": result.stderr
            }, 500
            
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


@app.route('/api/tilesList', methods=['GET'])
def get_tiles_list():
    try:
        is_steed_mode = request.args.get('isSteedMode', 'false').lower() == 'true'
        
        if is_steed_mode:
            # STEED mode: Use inference output directory
            inference_dirs = sorted([
                d for d in os.listdir(TILES_BASE_PATH)
                if os.path.isdir(os.path.join(TILES_BASE_PATH, d))
            ], reverse=True)  # Sort in reverse to get newest first
            
            if not inference_dirs:
                return jsonify({"error": "No tiles available in STEED mode"}), 404

            # Get the latest inference directory
            latest_inference = inference_dirs[-1]
            tiles_path = os.path.join(TILES_BASE_PATH, latest_inference, f"timeseries_tiles_{latest_inference}")
            
            if not os.path.exists(tiles_path):
                return jsonify({"error": "Tiles not yet generated in STEED mode"}), 404
                
            # List all timestamps in the tiles directory
            timestamps = sorted(
                name for name in os.listdir(tiles_path)
                if os.path.isdir(os.path.join(tiles_path, name))
            )
        else:
            # Local mode: Use local tiles directory
            if not os.path.exists(LOCAL_TILES_PATH):
                return jsonify({"error": "No tiles available in local mode"}), 404
                
            timestamps = sorted(
                name for name in os.listdir(LOCAL_TILES_PATH)
                if os.path.isdir(os.path.join(LOCAL_TILES_PATH, name))
            )
        
        return jsonify({"message": timestamps}), 200
        
    except Exception as error:
        logger.error(f"Error reading tiles directory: {error}")
        return jsonify({"error": "Unable to retrieve tiles list"}), 500

@app.route('/api/tiles/<timestamp>/<z>/<x>/<y>', methods=['GET'])
def get_tile_by_coordinates(timestamp, z, x, y):
    try:
        is_steed_mode = request.args.get('isSteedMode', 'false').lower() == 'true'

        
        if is_steed_mode:
            # STEED mode: Use inference output directory
            inference_dirs = sorted([
                d for d in os.listdir(TILES_BASE_PATH)
                if os.path.isdir(os.path.join(TILES_BASE_PATH, d))
            ], reverse=True)
            
            if inference_dirs:
                latest_inference = inference_dirs[-1]
                tile_path = os.path.join(
                    TILES_BASE_PATH,
                    latest_inference,
                    f"timeseries_tiles_{latest_inference}",
                    timestamp,
                    z,
                    x,
                    f"{y}.png"
                )

                print("tile_path:", tile_path)

                if os.path.exists(tile_path):
                    return send_file(tile_path), 200
            
            return jsonify({"error": "Tile not found in STEED mode"}), 404
        else:
            # Local mode: Use local tiles directory
            tile_path = os.path.join(
                LOCAL_TILES_PATH,
                timestamp,
                z,
                x,
                f"{y}.png"
            )

            print("tile_path:", tile_path)
            
            if os.path.exists(tile_path):
                return send_file(tile_path), 200
                
            return jsonify({"error": "Tile not found in local mode"}), 404
            
    except Exception as error:
        logger.error(f"Error serving tile: {error}")
        return jsonify({"error": "Unable to retrieve tile"}), 500

API_KEY = "74c101d12b334d09b854cee56563e545"
WATERNSW_BASE_URL = "https://api.waternsw.com.au/water/"
WATERNSW_SURFACE_WATER_ENDPOINT = "surface-water-data-api_download"

class SurfaceWaterRequestSchema(Schema):
    """Schema for validating surface water API request parameters"""
    page_number = fields.Integer(required=False, validate=lambda n: n >= 1, default=1)
    data_type = fields.String(required=False, default="autoqc")
    frequency = fields.String(required=False, default="instantaneous")
    site_id = fields.String(required=False, default="410001")
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    variable = fields.String(required=True, default="StreamWaterLevel")

def fetch_surface_water_data(site_id: str = "410001", 
                           start_date: str = "2024-03-24 00:00",
                           end_date: str = "2024-03-24 01:00",
                           frequency: str = "Instantaneous",
                           page_number: int = 1,
                           variable: str = "StreamWaterLevel") -> Dict:
    """
    Fetch surface water data from WaterNSW API
    
    Args:
        site_id: Site ID (default: 410001)
        start_date: Start date in dd-MMM-yyyy HH:mm format (e.g., "24-Mar-2024 00:00")
        end_date: End date in dd-MMM-yyyy HH:mm format (e.g., "24-Mar-2024 01:00")
        frequency: Data frequency (Instantaneous or Latest)
        page_number: Page number for pagination
    """
    url = urljoin(WATERNSW_BASE_URL, WATERNSW_SURFACE_WATER_ENDPOINT)
    
    params = {
        'siteId': site_id,
        'frequency': frequency,
        'dataType': 'AutoQC',
        'pageNumber': page_number,
        'startDate': start_date,
        'endDate': end_date,
        'variable': variable
    }
    
    
    headers = {
        'Ocp-Apim-Subscription-Key': API_KEY,
        'Cache-Control': 'no-cache',
        'Accept': 'application/json'
    }
    
    
    try:
        logger.info(f"Requesting WaterNSW API with params: {params}")
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 401:
            logger.error("Authentication failed with WaterNSW API. Check API key.")
            raise Exception("Authentication failed with WaterNSW API. Please check API key configuration.")
            
        response.raise_for_status()
        
        data = response.json()
        
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"waternsw_data_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Save response to JSON file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return data
    except requests.RequestException as e:
        logger.error(f"Error fetching data from WaterNSW API: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
        raise Exception(f"Failed to fetch data from WaterNSW: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while fetching data: {str(e)}")
        raise

@app.route('/api/gauging', methods=['GET'])
def get_gauging_data():
    """
    Fetch surface water data and return timeseries.
    
    Query Parameters:
    - start_date: String (optional) - Start date in dd-MMM-yyyy HH:mm format
    - end_date: String (optional) - End date in dd-MMM-yyyy HH:mm format
    - frequency: String (optional) - Data frequency (instantaneous or latest)
    - page_number: Integer (optional) - Page number for pagination (min value: 1)
    
    Returns:
        JSON response with timeseries data
    """
    try:
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        frequency = request.args.get('frequency', 'instantaneous')
        page_number = request.args.get('page_number', type=int, default=1)
        site_id = '410001'  # Fixed site ID for Wagga Wagga

        # Fetch data from WaterNSW API
        try:
            waternsw_data = fetch_surface_water_data(
                site_id=site_id,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                page_number=page_number
            )
            
            # Transform the data into timeseries format
            timeseries_data = {}
            for record in waternsw_data.get('records', []):
                try:
                    timestamp = record.get('timeStamp')
                    if not timestamp:
                        continue

                    # Initialize the timestamp entry if it doesn't exist
                    if timestamp not in timeseries_data:
                        timeseries_data[timestamp] = {
                            'timestamp': timestamp,
                            'waterLevel': None,
                            'flowRate': None
                        }
                    
                    # Update the appropriate measurement based on variableName
                    variable_name = record.get('variableName')
                    value = record.get('value')
                    
                    if variable_name == 'StreamWaterLevel':
                        timeseries_data[timestamp]['waterLevel'] = value
                    elif variable_name == 'FlowRate':
                        timeseries_data[timestamp]['flowRate'] = value

                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing record: {e}")
                    continue
            
            # Convert dictionary to sorted list
            sorted_timeseries = sorted(
                timeseries_data.values(),
                key=lambda x: x['timestamp']
            )
            
            response_data = {
                'site_id': site_id,
                'timeseries': sorted_timeseries,
                'total_records': len(sorted_timeseries)
            }

            # Save processed data
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            os.makedirs(data_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            processed_filename = f"processed_waternsw_data_{timestamp}.json"
            processed_filepath = os.path.join(data_dir, processed_filename)
            
            with open(processed_filepath, 'w') as f:
                json.dump(response_data, f, indent=2)
            
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
        logger.error(f"Error in surface water API: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

@app.route('/api/test-waternsw', methods=['GET'])
def test_waternsw():
    """Test the WaterNSW API connection"""
    try:
        # Try to fetch the latest reading
        data = fetch_surface_water_data(
            site_id="410001",
            frequency="latest"
        )
        return jsonify({
            "message": "WaterNSW API connection successful",
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "error": "WaterNSW API connection failed",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=3000)
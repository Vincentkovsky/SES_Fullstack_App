from flask import Flask, jsonify, send_file, abort
from flask_cors import CORS
import os
import subprocess
from typing import Tuple, Dict, Union
import logging

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
    script_path = os.path.join(os.path.dirname(__file__), "../../cnnModel/run_inference.sh")
    
    if not os.path.exists(script_path):
        logger.error(f"Inference script not found at: {script_path}")
        return {"error": "Inference script not found"}, 404
    
    try:
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 执行脚本并捕获输出
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            check=True
        )
        
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
    tiles_path = os.path.join(os.path.dirname(__file__), "timeseries_tiles")
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
        f"timeseries_tiles/{timestamp}/{z}/{x}/{y}.png"
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

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=3000)
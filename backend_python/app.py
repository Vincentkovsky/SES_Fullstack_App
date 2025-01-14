from flask import Flask, jsonify, send_file, abort
from flask_cors import CORS
import os

app = Flask(__name__)

# # 配置 CORS
CORS(app, resources={
    r"/*": {  # 匹配所有路由
        "origins": "http://localhost:5173",  # 允许的前端地址
        "methods": ["GET", "POST", "PUT", "DELETE"],  # 允许的 HTTP 方法
        "allow_headers": ["Content-Type", "Authorization"],  # 允许的请求头
    }
})


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
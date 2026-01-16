"""
Locust性能测试脚本
用于进行API负载测试，测试吞吐量和并发处理能力
"""

from locust import HttpUser, task, between
import random


class APIUser(HttpUser):
    """API用户模拟类"""
    
    wait_time = between(1, 3)  # 请求之间的等待时间（1-3秒）
    
    def on_start(self):
        """测试开始时的初始化"""
        # 配置测试参数
        self.simulation_id = "test_simulation"  # 修改为实际的simulation_id
        self.timestep_id = "waterdepth_20221024_1200"  # 修改为实际的timestep_id
        self.z_levels = [10, 12, 14, 16]
        
        # 测试端点列表
        self.endpoints = [
            "/api/health",
            "/api/inference/cuda_info",
            f"/api/tiles/{self.simulation_id}/{self.timestep_id}/14/931/619.png",
        ]
    
    @task(5)
    def get_tile(self):
        """获取瓦片（高频率任务）"""
        z = random.choice(self.z_levels)
        # 生成随机瓦片坐标
        max_tile = 2 ** z
        x = random.randint(0, max_tile - 1)
        y = random.randint(0, max_tile - 1)
        
        endpoint = f"/api/tiles/{self.simulation_id}/{self.timestep_id}/{z}/{x}/{y}.png"
        self.client.get(endpoint, name="Get Tile")
    
    @task(2)
    def get_tile_cached(self):
        """获取已缓存的瓦片（测试缓存性能）"""
        # 使用固定坐标，可能命中缓存
        endpoint = f"/api/tiles/{self.simulation_id}/{self.timestep_id}/14/931/619.png"
        self.client.get(endpoint, name="Get Tile (Cached)")
    
    @task(1)
    def get_health(self):
        """健康检查（低频率任务）"""
        self.client.get("/api/health", name="Health Check")
    
    @task(1)
    def get_cuda_info(self):
        """获取CUDA信息"""
        self.client.get("/api/inference/cuda_info", name="CUDA Info")
    
    @task(1)
    def get_water_depth(self):
        """获取水位深度"""
        params = {
            'lat': -35.117,
            'lng': 147.356,
            'timestamp': self.timestep_id,
            'simulation': self.simulation_id
        }
        self.client.get("/api/water-depth", params=params, name="Water Depth")


# 运行说明:
# 1. 安装Locust: pip install locust
# 2. 修改上面的simulation_id和timestep_id为实际值
# 3. 启动测试: locust -f locustfile.py --host=http://localhost:3000
# 4. 打开浏览器访问 http://localhost:8089
# 5. 设置用户数和生成速率，开始测试
#
# 命令行方式:
# locust -f locustfile.py --host=http://localhost:3000 --users=100 --spawn-rate=10 --run-time=5m --headless

# API性能测试工具使用说明

本目录包含用于测试API性能的测试脚本和工具。

## 文件说明

- `performance_test.py`: 自定义Python性能测试脚本
- `locustfile.py`: Locust负载测试脚本
- `README.md`: 本文件

## 安装依赖

```bash
pip install aiohttp locust
```

## 使用方法

### 1. 使用自定义测试脚本

```bash
# 运行所有测试
python tests/performance_test.py --base-url http://localhost:3000

# 只测试瓦片生成速度
python tests/performance_test.py --test-type tile --simulation-id your_simulation_id --timestep-id waterdepth_20221024_1200

# 只测试吞吐量
python tests/performance_test.py --test-type throughput

# 只测试并发能力
python tests/performance_test.py --test-type concurrent

# 测试多个端点
python tests/performance_test.py --test-type endpoints
```

### 2. 使用Locust进行负载测试

#### Web界面方式:
```bash
# 启动Locust
locust -f tests/locustfile.py --host=http://localhost:3000

# 打开浏览器访问 http://localhost:8089
# 设置用户数和生成速率，开始测试
```

#### 命令行方式（无头模式）:
```bash
# 100个用户，每秒生成10个用户，运行5分钟
locust -f tests/locustfile.py \
    --host=http://localhost:3000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless \
    --html=test_results/locust_report.html
```

### 3. 修改测试参数

在使用前，请修改以下参数：

1. **performance_test.py**: 
   - 修改 `--simulation-id` 和 `--timestep-id` 为实际值

2. **locustfile.py**:
   - 修改 `self.simulation_id` 和 `self.timestep_id` 为实际值

## 测试结果

测试结果会保存在 `test_results/` 目录下：

- `performance_test_YYYYMMDD_HHMMSS.json`: 自定义测试脚本的JSON结果
- `concurrent_capacity.csv`: 并发能力测试的CSV结果
- `locust_report.html`: Locust的HTML报告（如果使用--html参数）

## 测试指标说明

### 响应时间百分位数
- **P50 (中位数)**: 50%的请求响应时间低于此值
- **P95**: 95%的请求响应时间低于此值
- **P99**: 99%的请求响应时间低于此值

### 吞吐量
- **吞吐量 (req/s)**: 每秒处理的请求数

### 并发能力
- **最大并发数**: 系统能稳定处理的并发请求数
- **错误率**: 在高并发下的错误请求比例

### 瓦片生成速度
- **首次请求**: 缓存未命中时的生成时间
- **后续请求**: 缓存命中时的响应时间

## 注意事项

1. 确保后端服务正在运行
2. 确保有可用的测试数据（GeoTIFF文件）
3. 测试时注意系统资源使用情况
4. 建议在非生产环境进行测试
5. 长时间测试时注意监控系统稳定性

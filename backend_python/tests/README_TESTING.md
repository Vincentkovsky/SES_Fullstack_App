# 性能测试使用指南

## 概述

本目录包含用于测试系统性能的脚本，专注于以下4个关键指标：
1. REST API响应时间（P50/P95/P99）
2. 吞吐量（requests/sec）
3. 并发处理能力
4. 实时从GeoTIFF生成瓦片的速度

## 文件说明

- `performance_test_api.py`: API性能测试脚本（响应时间、吞吐量、并发能力）
- `performance_test_tile_generation.py`: 瓦片生成速度专门测试脚本

## 安装依赖

```bash
pip install aiohttp
```

## 使用方法

### 1. API响应时间测试

测试单个端点的响应时间分布：

```bash
# 测试健康检查端点
python tests/performance_test_api.py \
    --endpoint /api/health \
    --requests 1000 \
    --concurrency 10 \
    --test-type response

# 测试瓦片端点（需要先获取simulation_id和timestep_id）
python tests/performance_test_api.py \
    --endpoint "/api/tiles/{simulation_id}/{timestep_id}/14/931/619.png" \
    --requests 500 \
    --concurrency 5 \
    --test-type response
```

### 2. 吞吐量测试

测试系统在指定时间内的最大吞吐量：

```bash
python tests/performance_test_api.py \
    --endpoint /api/health \
    --duration 60 \
    --concurrency 20 \
    --test-type throughput
```

### 3. 并发处理能力测试

测试不同并发级别下的性能：

```bash
python tests/performance_test_api.py \
    --endpoint /api/health \
    --requests 100 \
    --concurrency 100 \
    --test-type concurrency
```

### 4. 瓦片生成速度测试

测试从GeoTIFF实时生成瓦片的速度：

```bash
# 测试不同缩放级别的生成速度
python tests/performance_test_tile_generation.py \
    --simulation-id "inference_1751611329_20221008" \
    --timestep-id "waterdepth_20221024_120000" \
    --zoom-levels 13 14 15 16 \
    --tiles-per-zoom 20 \
    --test-type speed

# 测试批量生成的吞吐量
python tests/performance_test_tile_generation.py \
    --simulation-id "inference_1751611329_20221008" \
    --timestep-id "waterdepth_20221024_120000" \
    --zoom-levels 14 \
    --num-tiles 100 \
    --concurrency 10 \
    --test-type throughput
```

## 获取测试参数

### 获取可用的simulation_id

```bash
curl http://localhost:3000/api/simulations
```

### 获取某个simulation的timestep_id

```bash
curl http://localhost:3000/api/simulations/{simulation_id}/timesteps
```

## 测试结果

测试结果会保存在 `test_results/` 目录下：
- JSON格式的详细结果
- CSV格式的并发测试结果（用于生成图表）

## 结果分析

### 响应时间指标
- **P50**: 中位数响应时间
- **P95**: 95%的请求响应时间低于此值
- **P99**: 99%的请求响应时间低于此值

### 吞吐量指标
- **requests/sec**: 每秒处理的请求数
- **error_rate**: 错误率百分比

### 瓦片生成速度
- **实时生成时间**: 从GeoTIFF生成新瓦片的平均时间
- **缓存命中时间**: 从缓存获取瓦片的平均时间
- **加速比**: 缓存带来的性能提升倍数

## 注意事项

1. **测试前准备**:
   - 确保后端服务正在运行
   - 确保有可用的测试数据（GeoTIFF文件）
   - 建议在测试环境中运行，避免影响生产环境

2. **测试参数调整**:
   - 根据系统性能调整并发数
   - 瓦片测试需要真实的simulation_id和timestep_id
   - 建议从低并发开始，逐步增加

3. **结果解释**:
   - 第一次请求瓦片会触发实时生成（较慢）
   - 后续相同瓦片的请求会命中缓存（较快）
   - 测试脚本会自动区分这两种情况

## 生成图表

可以使用Python脚本分析测试结果并生成图表：

```python
import json
import matplotlib.pyplot as plt
import pandas as pd

# 读取并发测试结果
with open('test_results/concurrency_api_health.csv') as f:
    df = pd.read_csv(f)
    
# 绘制吞吐量曲线
plt.plot(df['concurrency'], df['throughput'])
plt.xlabel('Concurrency')
plt.ylabel('Throughput (req/s)')
plt.title('API Throughput vs Concurrency')
plt.savefig('throughput_curve.png')
```

#!/bin/bash
# 简单的性能测试脚本，使用curl进行测试

BASE_URL="http://localhost:3000"
SIMULATION_ID="inference_1751611329_20221008"
TIMESTEP_ID="waterdepth_20221008_000000"
Z=14
X=931
Y=619

OUTPUT_DIR="test_results"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "API性能测试"
echo "=========================================="
echo "API地址: $BASE_URL"
echo "模拟ID: $SIMULATION_ID"
echo "时间步: $TIMESTEP_ID"
echo ""

# 测试1: 健康检查端点响应时间
echo "测试1: 健康检查端点响应时间"
echo "----------------------------------------"
HEALTH_TIMES=()
for i in {1..100}; do
    START=$(date +%s%N)
    curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/health" > /dev/null
    END=$(date +%s%N)
    ELAPSED=$((($END - $START) / 1000000))  # 转换为毫秒
    HEALTH_TIMES+=($ELAPSED)
    if [ $((i % 20)) -eq 0 ]; then
        echo "  已完成 $i/100 请求..."
    fi
done

# 计算统计信息
IFS=$'\n' SORTED=($(sort -n <<<"${HEALTH_TIMES[*]}"))
COUNT=${#HEALTH_TIMES[@]}
P50_IDX=$((COUNT * 50 / 100))
P95_IDX=$((COUNT * 95 / 100))
P99_IDX=$((COUNT * 99 / 100))

SUM=0
for time in "${HEALTH_TIMES[@]}"; do
    SUM=$((SUM + time))
done
MEAN=$((SUM / COUNT))

echo "  总请求数: $COUNT"
echo "  平均响应时间: ${MEAN}ms"
echo "  P50: ${SORTED[$P50_IDX]}ms"
echo "  P95: ${SORTED[$P95_IDX]}ms"
echo "  P99: ${SORTED[$P99_IDX]}ms"
echo "  最小: ${SORTED[0]}ms"
echo "  最大: ${SORTED[$((COUNT-1))]}ms"
echo ""

# 测试2: 瓦片生成端点响应时间（首次请求，缓存未命中）
echo "测试2: 瓦片生成端点响应时间（首次请求）"
echo "----------------------------------------"
TILE_ENDPOINT="/api/tiles/$SIMULATION_ID/$TIMESTEP_ID/$Z/$X/$Y.png"
TILE_TIMES=()

# 测试10个不同的瓦片坐标（确保缓存未命中）
for i in {0..9}; do
    TEST_X=$((X + i))
    TEST_Y=$((Y + i))
    TEST_ENDPOINT="/api/tiles/$SIMULATION_ID/$TIMESTEP_ID/$Z/$TEST_X/$TEST_Y.png"
    
    START=$(date +%s%N)
    curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$TEST_ENDPOINT" > /dev/null
    END=$(date +%s%N)
    ELAPSED=$((($END - $START) / 1000000))
    TILE_TIMES+=($ELAPSED)
    echo "  瓦片 ($TEST_X, $TEST_Y): ${ELAPSED}ms"
    sleep 0.1
done

# 计算统计信息
IFS=$'\n' TILE_SORTED=($(sort -n <<<"${TILE_TIMES[*]}"))
TILE_COUNT=${#TILE_TIMES[@]}
TILE_P50_IDX=$((TILE_COUNT * 50 / 100))
TILE_P95_IDX=$((TILE_COUNT * 95 / 100))
TILE_P99_IDX=$((TILE_COUNT * 99 / 100))

TILE_SUM=0
for time in "${TILE_TIMES[@]}"; do
    TILE_SUM=$((TILE_SUM + time))
done
TILE_MEAN=$((TILE_SUM / TILE_COUNT))

echo ""
echo "  总请求数: $TILE_COUNT"
echo "  平均响应时间: ${TILE_MEAN}ms"
echo "  P50: ${TILE_SORTED[$TILE_P50_IDX]}ms"
echo "  P95: ${TILE_SORTED[$TILE_P95_IDX]}ms"
echo "  P99: ${TILE_SORTED[$TILE_P99_IDX]}ms"
echo "  最小: ${TILE_SORTED[0]}ms"
echo "  最大: ${TILE_SORTED[$((TILE_COUNT-1))]}ms"
echo ""

# 测试3: 缓存命中测试（重复请求相同瓦片）
echo "测试3: 瓦片生成端点响应时间（缓存命中）"
echo "----------------------------------------"
CACHED_TIMES=()
for i in {1..50}; do
    START=$(date +%s%N)
    curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$TILE_ENDPOINT" > /dev/null
    END=$(date +%s%N)
    ELAPSED=$((($END - $START) / 1000000))
    CACHED_TIMES+=($ELAPSED)
    if [ $((i % 10)) -eq 0 ]; then
        echo "  已完成 $i/50 请求..."
    fi
    sleep 0.05
done

# 计算统计信息
IFS=$'\n' CACHED_SORTED=($(sort -n <<<"${CACHED_TIMES[*]}"))
CACHED_COUNT=${#CACHED_TIMES[@]}
CACHED_P50_IDX=$((CACHED_COUNT * 50 / 100))
CACHED_P95_IDX=$((CACHED_COUNT * 95 / 100))
CACHED_P99_IDX=$((CACHED_COUNT * 99 / 100))

CACHED_SUM=0
for time in "${CACHED_TIMES[@]}"; do
    CACHED_SUM=$((CACHED_SUM + time))
done
CACHED_MEAN=$((CACHED_SUM / CACHED_COUNT))

echo ""
echo "  总请求数: $CACHED_COUNT"
echo "  平均响应时间: ${CACHED_MEAN}ms"
echo "  P50: ${CACHED_SORTED[$CACHED_P50_IDX]}ms"
echo "  P95: ${CACHED_SORTED[$CACHED_P95_IDX]}ms"
echo "  P99: ${CACHED_SORTED[$CACHED_P99_IDX]}ms"
echo "  最小: ${CACHED_SORTED[0]}ms"
echo "  最大: ${CACHED_SORTED[$((CACHED_COUNT-1))]}ms"
echo ""

# 测试4: 吞吐量测试（并发请求）
echo "测试4: 吞吐量测试（20并发，持续10秒）"
echo "----------------------------------------"
CONCURRENT=20
DURATION=10
START_TIME=$(date +%s)
REQUEST_COUNT=0
ERROR_COUNT=0

# 启动并发请求
for i in $(seq 1 $CONCURRENT); do
    (
        while [ $(($(date +%s) - START_TIME)) -lt $DURATION ]; do
            if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$TILE_ENDPOINT" | grep -q "200"; then
                REQUEST_COUNT=$((REQUEST_COUNT + 1))
            else
                ERROR_COUNT=$((ERROR_COUNT + 1))
            fi
            sleep 0.1
        done
    ) &
done

wait
END_TIME=$(date +%s)
ACTUAL_DURATION=$((END_TIME - START_TIME))
THROUGHPUT=$((REQUEST_COUNT / ACTUAL_DURATION))

echo "  总请求数: $REQUEST_COUNT"
echo "  错误数: $ERROR_COUNT"
echo "  持续时间: ${ACTUAL_DURATION}秒"
echo "  吞吐量: ${THROUGHPUT} requests/sec"
echo ""

# 生成报告
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$OUTPUT_DIR/performance_test_$TIMESTAMP.txt"

cat > "$REPORT_FILE" <<EOF
API性能测试报告
生成时间: $(date)
API地址: $BASE_URL
模拟ID: $SIMULATION_ID
时间步: $TIMESTEP_ID

==========================================
1. 健康检查端点响应时间
==========================================
总请求数: $COUNT
平均响应时间: ${MEAN}ms
P50: ${SORTED[$P50_IDX]}ms
P95: ${SORTED[$P95_IDX]}ms
P99: ${SORTED[$P99_IDX]}ms
最小: ${SORTED[0]}ms
最大: ${SORTED[$((COUNT-1))]}ms

==========================================
2. 瓦片生成端点响应时间（缓存未命中）
==========================================
总请求数: $TILE_COUNT
平均响应时间: ${TILE_MEAN}ms
P50: ${TILE_SORTED[$TILE_P50_IDX]}ms
P95: ${TILE_SORTED[$TILE_P95_IDX]}ms
P99: ${TILE_SORTED[$TILE_P99_IDX]}ms
最小: ${TILE_SORTED[0]}ms
最大: ${TILE_SORTED[$((TILE_COUNT-1))]}ms

==========================================
3. 瓦片生成端点响应时间（缓存命中）
==========================================
总请求数: $CACHED_COUNT
平均响应时间: ${CACHED_MEAN}ms
P50: ${CACHED_SORTED[$CACHED_P50_IDX]}ms
P95: ${CACHED_SORTED[$CACHED_P95_IDX]}ms
P99: ${CACHED_SORTED[$CACHED_P99_IDX]}ms
最小: ${CACHED_SORTED[0]}ms
最大: ${CACHED_SORTED[$((CACHED_COUNT-1))]}ms

缓存加速比: $(echo "scale=2; ${TILE_MEAN} / ${CACHED_MEAN}" | bc)x

==========================================
4. 吞吐量测试
==========================================
并发数: $CONCURRENT
持续时间: ${ACTUAL_DURATION}秒
总请求数: $REQUEST_COUNT
错误数: $ERROR_COUNT
吞吐量: ${THROUGHPUT} requests/sec
EOF

echo "=========================================="
echo "测试完成！"
echo "报告已保存到: $REPORT_FILE"
echo "=========================================="

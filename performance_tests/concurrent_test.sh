#!/bin/bash
# 并发处理能力测试脚本

BASE_URL="http://localhost:3000"
SIMULATION_ID="inference_1751611329_20221008"
TIMESTEP_ID="waterdepth_20221008_000000"
TILE_ENDPOINT="/api/tiles/$SIMULATION_ID/$TIMESTEP_ID/14/931/619.png"

OUTPUT_DIR="test_results"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "并发处理能力测试"
echo "=========================================="
echo "测试端点: $TILE_ENDPOINT"
echo ""

# 测试不同并发级别
CONCURRENCY_LEVELS=(1 5 10 20 50)
REQUESTS_PER_LEVEL=50

RESULTS_FILE="$OUTPUT_DIR/concurrent_test_results.csv"
echo "并发数,总请求数,成功数,失败数,总时间(秒),吞吐量(req/s),平均响应时间(ms),P50(ms),P95(ms),P99(ms)" > "$RESULTS_FILE"

for CONCURRENT in "${CONCURRENCY_LEVELS[@]}"; do
    echo "测试并发数: $CONCURRENT"
    echo "----------------------------------------"
    
    # 创建临时文件存储响应时间
    TEMP_FILE=$(mktemp)
    
    # 启动并发请求
    START_TIME=$(date +%s%N)
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    for i in $(seq 1 $CONCURRENT); do
        (
            for j in $(seq 1 $REQUESTS_PER_LEVEL); do
                REQ_START=$(date +%s%N)
                HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$TILE_ENDPOINT")
                REQ_END=$(date +%s%N)
                ELAPSED=$((($REQ_END - $REQ_START) / 1000000))
                
                if [ "$HTTP_CODE" = "200" ]; then
                    echo "$ELAPSED" >> "$TEMP_FILE"
                    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
                else
                    FAIL_COUNT=$((FAIL_COUNT + 1))
                fi
            done
        ) &
    done
    
    wait
    END_TIME=$(date +%s%N)
    TOTAL_TIME=$((($END_TIME - $START_TIME) / 1000000000))
    
    # 计算统计信息
    if [ -s "$TEMP_FILE" ]; then
        SORTED_TIMES=($(sort -n < "$TEMP_FILE"))
        COUNT=${#SORTED_TIMES[@]}
        
        # 计算总和
        SUM=0
        for time in "${SORTED_TIMES[@]}"; do
            SUM=$((SUM + time))
        done
        MEAN=$((SUM / COUNT))
        
        # 计算百分位数
        P50_IDX=$((COUNT * 50 / 100))
        P95_IDX=$((COUNT * 95 / 100))
        P99_IDX=$((COUNT * 99 / 100))
        
        P50=${SORTED_TIMES[$P50_IDX]}
        P95=${SORTED_TIMES[$P95_IDX]}
        P99=${SORTED_TIMES[$P99_IDX]}
        
        THROUGHPUT=$((COUNT / TOTAL_TIME))
        
        echo "  总请求数: $((CONCURRENT * REQUESTS_PER_LEVEL))"
        echo "  成功数: $COUNT"
        echo "  失败数: $FAIL_COUNT"
        echo "  总时间: ${TOTAL_TIME}秒"
        echo "  吞吐量: ${THROUGHPUT} req/s"
        echo "  平均响应时间: ${MEAN}ms"
        echo "  P50: ${P50}ms"
        echo "  P95: ${P95}ms"
        echo "  P99: ${P99}ms"
        echo ""
        
        # 写入CSV
        echo "$CONCURRENT,$((CONCURRENT * REQUESTS_PER_LEVEL)),$COUNT,$FAIL_COUNT,$TOTAL_TIME,$THROUGHPUT,$MEAN,$P50,$P95,$P99" >> "$RESULTS_FILE"
    else
        echo "  错误: 没有成功的请求"
        echo "$CONCURRENT,$((CONCURRENT * REQUESTS_PER_LEVEL)),0,$FAIL_COUNT,$TOTAL_TIME,0,0,0,0,0" >> "$RESULTS_FILE"
    fi
    
    rm -f "$TEMP_FILE"
    sleep 2  # 短暂休息，避免系统过载
done

echo "=========================================="
echo "测试完成！"
echo "结果已保存到: $RESULTS_FILE"
echo "=========================================="
cat "$RESULTS_FILE"

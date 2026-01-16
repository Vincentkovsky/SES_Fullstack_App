#!/bin/bash
# 吞吐量和并发处理能力测试脚本

BASE_URL="http://localhost:3000"
SIMULATION_ID="inference_1751611329_20221008"
TIMESTEP_ID="waterdepth_20221008_000000"
TILE_ENDPOINT="/api/tiles/$SIMULATION_ID/$TIMESTEP_ID/14/931/619.png"

OUTPUT_DIR="test_results"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "吞吐量和并发处理能力测试"
echo "=========================================="
echo "API地址: $BASE_URL"
echo "测试端点: $TILE_ENDPOINT"
echo ""

# 测试1: 吞吐量测试（不同并发级别）
echo "=========================================="
echo "测试1: 吞吐量测试"
echo "=========================================="

THROUGHPUT_FILE="$OUTPUT_DIR/throughput_results.csv"
echo "并发数,持续时间(秒),总请求数,成功数,失败数,吞吐量(req/s),平均响应时间(ms),P50(ms),P95(ms),P99(ms)" > "$THROUGHPUT_FILE"

CONCURRENCY_LEVELS=(1 5 10 20 50)
DURATION=30  # 每个测试持续30秒

for CONCURRENT in "${CONCURRENCY_LEVELS[@]}"; do
    echo "测试并发数: $CONCURRENT (持续${DURATION}秒)"
    
    # 创建临时文件存储响应时间
    TEMP_FILE=$(mktemp)
    REQUEST_COUNT=0
    ERROR_COUNT=0
    
    # 启动并发请求
    START_TIME=$(date +%s)
    END_TIME=$((START_TIME + DURATION))
    
    for i in $(seq 1 $CONCURRENT); do
        (
            while [ $(date +%s) -lt $END_TIME ]; do
                REQ_START=$(date +%s%N)
                HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL$TILE_ENDPOINT" 2>/dev/null)
                REQ_END=$(date +%s%N)
                ELAPSED=$((($REQ_END - $REQ_START) / 1000000))
                
                if [ "$HTTP_CODE" = "200" ]; then
                    echo "$ELAPSED" >> "$TEMP_FILE"
                    REQUEST_COUNT=$((REQUEST_COUNT + 1))
                else
                    ERROR_COUNT=$((ERROR_COUNT + 1))
                fi
                
                # 短暂延迟，避免过载
                sleep 0.01
            done
        ) &
    done
    
    wait
    ACTUAL_END=$(date +%s)
    ACTUAL_DURATION=$((ACTUAL_END - START_TIME))
    
    # 计算统计信息
    if [ -s "$TEMP_FILE" ]; then
        SORTED_TIMES=($(sort -n < "$TEMP_FILE"))
        COUNT=${#SORTED_TIMES[@]}
        
        # 计算总和和平均值
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
        
        # 计算吞吐量
        if [ $ACTUAL_DURATION -gt 0 ]; then
            THROUGHPUT=$((COUNT / ACTUAL_DURATION))
        else
            THROUGHPUT=0
        fi
        
        echo "  总请求数: $COUNT"
        echo "  失败数: $ERROR_COUNT"
        echo "  持续时间: ${ACTUAL_DURATION}秒"
        echo "  吞吐量: ${THROUGHPUT} req/s"
        echo "  平均响应时间: ${MEAN}ms"
        echo "  P50: ${P50}ms"
        echo "  P95: ${P95}ms"
        echo "  P99: ${P99}ms"
        echo ""
        
        # 写入CSV
        echo "$CONCURRENT,$ACTUAL_DURATION,$COUNT,$COUNT,$ERROR_COUNT,$THROUGHPUT,$MEAN,$P50,$P95,$P99" >> "$THROUGHPUT_FILE"
    else
        echo "  错误: 没有成功的请求"
        echo "$CONCURRENT,$ACTUAL_DURATION,0,0,$ERROR_COUNT,0,0,0,0,0" >> "$THROUGHPUT_FILE"
    fi
    
    rm -f "$TEMP_FILE"
    sleep 3  # 休息3秒，避免系统过载
done

echo "吞吐量测试完成！结果已保存到: $THROUGHPUT_FILE"
echo ""

# 测试2: 并发处理能力测试（固定请求数，不同并发级别）
echo "=========================================="
echo "测试2: 并发处理能力测试"
echo "=========================================="

CONCURRENT_FILE="$OUTPUT_DIR/concurrent_capacity_results.csv"
echo "并发数,总请求数,成功数,失败数,总时间(秒),吞吐量(req/s),平均响应时间(ms),P50(ms),P95(ms),P99(ms),错误率(%)" > "$CONCURRENT_FILE"

CONCURRENCY_LEVELS=(1 5 10 20 50 100)
REQUESTS_PER_LEVEL=100

for CONCURRENT in "${CONCURRENCY_LEVELS[@]}"; do
    echo "测试并发数: $CONCURRENT (每并发$REQUESTS_PER_LEVEL请求)"
    
    # 创建临时文件存储响应时间
    TEMP_FILE=$(mktemp)
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    # 启动并发请求
    START_TIME=$(date +%s%N)
    
    for i in $(seq 1 $CONCURRENT); do
        (
            for j in $(seq 1 $REQUESTS_PER_LEVEL); do
                REQ_START=$(date +%s%N)
                HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL$TILE_ENDPOINT" 2>/dev/null)
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
        TOTAL_REQUESTS=$((CONCURRENT * REQUESTS_PER_LEVEL))
        
        # 计算总和和平均值
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
        
        # 计算吞吐量和错误率
        if [ $TOTAL_TIME -gt 0 ]; then
            THROUGHPUT=$((COUNT / TOTAL_TIME))
        else
            THROUGHPUT=0
        fi
        
        ERROR_RATE=$(echo "scale=2; $FAIL_COUNT * 100 / $TOTAL_REQUESTS" | bc 2>/dev/null || echo "0")
        
        echo "  总请求数: $TOTAL_REQUESTS"
        echo "  成功数: $COUNT"
        echo "  失败数: $FAIL_COUNT"
        echo "  错误率: ${ERROR_RATE}%"
        echo "  总时间: ${TOTAL_TIME}秒"
        echo "  吞吐量: ${THROUGHPUT} req/s"
        echo "  平均响应时间: ${MEAN}ms"
        echo "  P50: ${P50}ms"
        echo "  P95: ${P95}ms"
        echo "  P99: ${P99}ms"
        echo ""
        
        # 写入CSV
        echo "$CONCURRENT,$TOTAL_REQUESTS,$COUNT,$FAIL_COUNT,$TOTAL_TIME,$THROUGHPUT,$MEAN,$P50,$P95,$P99,$ERROR_RATE" >> "$CONCURRENT_FILE"
        
        # 如果错误率过高，提前结束
        if [ $(echo "$ERROR_RATE > 10" | bc 2>/dev/null || echo "0") -eq 1 ]; then
            echo "  警告: 错误率过高 (${ERROR_RATE}%)，停止测试"
            break
        fi
    else
        echo "  错误: 没有成功的请求"
        TOTAL_REQUESTS=$((CONCURRENT * REQUESTS_PER_LEVEL))
        echo "$CONCURRENT,$TOTAL_REQUESTS,0,$FAIL_COUNT,$TOTAL_TIME,0,0,0,0,0,100" >> "$CONCURRENT_FILE"
        break
    fi
    
    rm -f "$TEMP_FILE"
    sleep 2  # 休息2秒
done

echo "并发处理能力测试完成！结果已保存到: $CONCURRENT_FILE"
echo ""

# 生成汇总报告
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SUMMARY_FILE="$OUTPUT_DIR/throughput_concurrent_summary_$TIMESTAMP.txt"

cat > "$SUMMARY_FILE" <<EOF
吞吐量和并发处理能力测试报告
生成时间: $(date)
API地址: $BASE_URL
测试端点: $TILE_ENDPOINT

==========================================
1. 吞吐量测试结果
==========================================
$(cat "$THROUGHPUT_FILE")

==========================================
2. 并发处理能力测试结果
==========================================
$(cat "$CONCURRENT_FILE")

==========================================
关键发现
==========================================
EOF

# 分析结果并添加到报告
if [ -f "$THROUGHPUT_FILE" ] && [ $(wc -l < "$THROUGHPUT_FILE") -gt 1 ]; then
    echo "" >> "$SUMMARY_FILE"
    echo "吞吐量分析:" >> "$SUMMARY_FILE"
    echo "- 最大吞吐量出现在并发数: $(tail -n +2 "$THROUGHPUT_FILE" | awk -F',' '{print $1","$6}' | sort -t',' -k2 -rn | head -1 | cut -d',' -f1)" >> "$SUMMARY_FILE"
    echo "- 最大吞吐量: $(tail -n +2 "$THROUGHPUT_FILE" | awk -F',' '{print $6}' | sort -rn | head -1) req/s" >> "$SUMMARY_FILE"
fi

if [ -f "$CONCURRENT_FILE" ] && [ $(wc -l < "$CONCURRENT_FILE") -gt 1 ]; then
    echo "" >> "$SUMMARY_FILE"
    echo "并发能力分析:" >> "$SUMMARY_FILE"
    echo "- 在错误率<1%的情况下，最大并发数: $(tail -n +2 "$CONCURRENT_FILE" | awk -F',' '$11 < 1 {print $1}' | tail -1)" >> "$SUMMARY_FILE"
    echo "- 在错误率<5%的情况下，最大并发数: $(tail -n +2 "$CONCURRENT_FILE" | awk -F',' '$11 < 5 {print $1}' | tail -1)" >> "$SUMMARY_FILE"
fi

echo "" >> "$SUMMARY_FILE"
echo "详细数据请查看CSV文件。" >> "$SUMMARY_FILE"

echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo "吞吐量测试结果: $THROUGHPUT_FILE"
echo "并发能力测试结果: $CONCURRENT_FILE"
echo "汇总报告: $SUMMARY_FILE"
echo "=========================================="

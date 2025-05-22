#!/bin/bash

# 检查PM2是否在运行并停止它
echo "检查PM2进程管理器..."
PM2_PID=$(ps -ef | grep "PM2 v" | grep -v grep | awk '{print $2}')

if [ -n "$PM2_PID" ]; then
    echo "发现PM2进程管理器 (PID: $PM2_PID)，尝试停止所有PM2管理的进程..."
    
    # 尝试使用PM2命令停止进程
    if command -v pm2 &> /dev/null; then
        echo "使用PM2命令停止所有进程..."
        pm2 stop all
        pm2 delete all
        pm2 kill
    else
        echo "未找到PM2命令，尝试直接终止进程..."
        kill $PM2_PID
        sleep 2
        if ps -p $PM2_PID > /dev/null; then
            echo "PM2进程仍在运行，尝试强制终止..."
            kill -9 $PM2_PID
        fi
    fi
    
    echo "等待所有PM2子进程终止..."
    sleep 3
fi

# 定义一个终止端口上所有进程的函数
kill_port() {
    local PORT=$1
    local PIDS=$(lsof -t -i:$PORT)
    
    if [ -n "$PIDS" ]; then
        echo "终止端口 $PORT 上的所有进程..."
        for PID in $PIDS; do
            echo "  尝试终止进程 PID: $PID"
            kill $PID 2>/dev/null
        done
        
        # 等待一秒后检查是否还有进程
        sleep 1
        PIDS=$(lsof -t -i:$PORT)
        if [ -n "$PIDS" ]; then
            echo "  进程仍在运行，尝试强制终止..."
            for PID in $PIDS; do
                kill -9 $PID 2>/dev/null
            done
        fi
        
        # 最终检查
        sleep 1
        if lsof -i:$PORT > /dev/null 2>&1; then
            echo "  警告: 端口 $PORT 仍被占用!"
            return 1
        else
            echo "  端口 $PORT 已成功释放"
            return 0
        fi
    else
        echo "端口 $PORT 没有被占用"
        return 0
    fi
}

# 定义一个清理进程的函数
kill_process() {
    local PROCESS_PATTERN=$1
    local PIDS=$(ps aux | grep "$PROCESS_PATTERN" | grep -v grep | awk '{print $2}')
    
    if [ -n "$PIDS" ]; then
        echo "清理匹配 '$PROCESS_PATTERN' 的进程..."
        for PID in $PIDS; do
            echo "  尝试终止进程 PID: $PID"
            kill $PID 2>/dev/null
        done
        
        # 等待一秒后检查是否还有进程
        sleep 1
        PIDS=$(ps aux | grep "$PROCESS_PATTERN" | grep -v grep | awk '{print $2}')
        if [ -n "$PIDS" ]; then
            echo "  进程仍在运行，尝试强制终止..."
            for PID in $PIDS; do
                kill -9 $PID 2>/dev/null
            done
        fi
    fi
}

# 停止所有相关服务
echo "===== 开始停止所有服务 ====="

# 1. 终止特定端口上的进程
echo "步骤1: 终止端口上的进程"
kill_port 3000  # 后端
kill_port 5173  # 前端
kill_port 5174  # 前端备用端口

# 2. 根据进程名称查找并终止残留进程
echo "步骤2: 清理残留进程"
kill_process "python backend_python/fastapi_app.py"  # 后端进程
kill_process "npm run dev"                           # 前端进程

# 3. 最终检查所有端口
echo "步骤3: 最终检查"
if lsof -i:3000,5173,5174 > /dev/null 2>&1; then
    echo "警告: 仍有端口被占用:"
    lsof -i:3000,5173,5174
    echo "尝试最后的强制终止..."
    lsof -t -i:3000,5173,5174 | xargs -r kill -9 2>/dev/null
    
    # 再次检查
    sleep 1
    if lsof -i:3000,5173,5174 > /dev/null 2>&1; then
        echo "严重警告: 无法完全释放所有端口!"
        echo "可能需要手动终止以下进程:"
        lsof -i:3000,5173,5174
    else
        echo "所有端口已成功释放"
    fi
else
    echo "所有端口已成功释放"
fi

echo "===== 服务停止完成 =====" 
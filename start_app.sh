#!/bin/bash

source /projects/TCCTVS/.bashrc

# 检查conda环境
if ! command -v conda &> /dev/null; then
    echo "错误: 未找到conda命令，请确保已安装conda"
    exit 1
fi

# 检查flood_new环境是否存在
if ! conda env list | grep -q "flood_new"; then
    echo "错误: 未找到flood_new环境，请先创建该环境"
    exit 1
fi

# 激活conda环境
eval "$(conda shell.bash hook)"
conda activate flood_new || { echo "错误: 无法激活flood_new环境"; exit 1; }

# 创建日志目录并设置权限
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    # 设置目录权限为777，允许所有用户读写
    chmod 777 "$LOGS_DIR"
elif [ ! -w "$LOGS_DIR" ]; then
    echo "警告: logs目录不可写，尝试修改权限..."
    chmod 777 "$LOGS_DIR" || {
        echo "错误: 无法修改logs目录权限，请使用sudo运行此命令："
        echo "sudo chmod 777 $LOGS_DIR"
        exit 1
    }
fi

# 先检查端口是否被占用，如果被占用则先释放
echo "检查端口占用情况..."

# 检查并释放后端端口3000
if lsof -i:3000 > /dev/null 2>&1; then
    echo "端口3000已被占用，尝试释放..."
    for PID in $(lsof -t -i:3000); do
        kill $PID
        echo "终止进程 PID: $PID"
    done
    sleep 2
fi

# 检查并释放前端端口5173
if lsof -i:5173 > /dev/null 2>&1; then
    echo "端口5173已被占用，尝试释放..."
    for PID in $(lsof -t -i:5173); do
        kill $PID
        echo "终止进程 PID: $PID"
    done
    sleep 2
fi

# 在一个终端运行后端，强制使用3000端口
echo "启动后端服务 (端口3000)..."
(cd "$SCRIPT_DIR" && BACKEND_PORT=3000 python backend_python/fastapi_app.py > "$LOGS_DIR/backend.log" 2>&1) &
BACKEND_PID=$!
echo "后端服务已启动，PID: $BACKEND_PID，日志保存在 logs/backend.log"

# 等待后端启动
sleep 3

# 在另一个终端运行前端，强制使用5173端口
echo "启动前端服务 (端口5173)..."
if ! command -v npm &> /dev/null; then
    echo "错误: 未找到npm命令，请确保已安装Node.js和npm"
    kill $BACKEND_PID
    exit 1
fi

(cd "$SCRIPT_DIR/frontend" && npm run dev -- --port 5173 > "$LOGS_DIR/frontend.log" 2>&1) &
FRONTEND_PID=$!
echo "前端服务已启动，PID: $FRONTEND_PID，日志保存在 logs/frontend.log"

# 显示服务状态
echo ""
echo "服务已启动:"
echo "============================="
echo "后端服务: http://localhost:3000"
echo "前端服务: http://localhost:5173"
echo "============================="
echo "后端进程: $BACKEND_PID"
echo "前端进程: $FRONTEND_PID"
echo "============================="
echo ""
echo "使用以下命令查看日志:"
echo "后端日志: tail -f logs/backend.log"
echo "前端日志: tail -f logs/frontend.log"
echo ""
echo "使用以下命令停止服务:"
echo "./stop_app.sh"
echo ""
echo "按下 Ctrl+C 退出..."

# 等待用户中断
wait
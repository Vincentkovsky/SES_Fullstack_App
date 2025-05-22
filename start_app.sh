#!/bin/bash
source /projects/TCCTVS/.bashrc
conda activate flood_new

# 创建日志目录
mkdir -p logs

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
(cd $(dirname $0) && BACKEND_PORT=3000 python backend_python/fastapi_app.py > logs/backend.log 2>&1) &
BACKEND_PID=$!
echo "后端服务已启动，PID: $BACKEND_PID，日志保存在 logs/backend.log"

# 等待后端启动
sleep 3

# 在另一个终端运行前端，强制使用5173端口
echo "启动前端服务 (端口5173)..."
(cd $(dirname $0)/frontend && npm run dev -- --port 5173 > ../logs/frontend.log 2>&1) &
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
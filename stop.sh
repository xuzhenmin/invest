#!/bin/bash

# Function to kill process by port
kill_by_port() {
    local port=$1
    local service_name=$2
    echo "Stopping $service_name on port $port..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || echo "No process found on port $port"
}

# Stop backend on port 5001
kill_by_port 5001 "backend service"

# Stop frontend on port 3000
kill_by_port 3000 "frontend service"

# Clean up PID files if they exist
rm -f backend/backend.pid frontend/frontend.pid 2>/dev/null
echo "Cleaned up PID files."

# 停止后端服务
echo "正在停止后端服务..."
cd backend
./stop.sh

# 停止前端服务
echo "正在停止前端服务..."
cd ../frontend
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "没有找到运行在端口 3000 的进程"

echo "所有服务已停止" 

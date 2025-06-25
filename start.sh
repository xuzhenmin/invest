#!/bin/bash

echo "Starting backend..."
cd backend || exit # Change directory, exit if it fails
source venv/bin/activate  # 激活虚拟环境
export DEEPSEEK_API_KEY="your-api-key-here"  # 设置 Deepseek API Key
nohup python3 app.py > ../backend_log.out 2>&1 & 
BACKEND_PID=$!
cd ..

echo "Waiting for backend to fully start (5 seconds)..."
sleep 5 # Give Flask time to start

if [ -z "$BACKEND_PID" ]; then
    echo "Warning: Could not start backend process"
    exit 1
else
    echo "$BACKEND_PID" > backend_pid.txt
    echo "Backend started with PID: $BACKEND_PID"
fi

echo "Starting frontend..."
cd frontend || exit # Change directory, exit if it fails
nohup npm start > ../frontend_log.out 2>&1 & 
FRONTEND_PID=$!
cd ..

echo "Waiting for frontend to fully start (10 seconds)..."
sleep 10 # npm start can take longer

if [ -z "$FRONTEND_PID" ]; then
    echo "Warning: Could not start frontend process"
    exit 1
else
    echo "$FRONTEND_PID" > frontend_pid.txt
    echo "Frontend started with PID: $FRONTEND_PID"
fi

echo "Services started. PIDs saved to backend_pid.txt and frontend_pid.txt"
echo "Check backend_log.out and frontend_log.out for logs." 

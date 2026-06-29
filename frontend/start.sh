#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/frontend.log"
PID_FILE="$SCRIPT_DIR/frontend.pid"

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "前端服务已在运行 (PID: $OLD_PID)，如需重启请先执行 stop.sh"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

echo "启动前端服务..."
echo "日志文件: $LOG_FILE"

nohup npm --prefix "$SCRIPT_DIR" start > "$LOG_FILE" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PID_FILE"

echo "前端服务已启动 (PID: $FRONTEND_PID)"
echo "查看日志: tail -f $LOG_FILE"

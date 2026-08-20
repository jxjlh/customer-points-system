#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PORT=8765

if [ ! -f "$PYTHON" ]; then
    echo "[错误] 虚拟环境不存在: $VENV_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
exec "$PYTHON" script/run_backend.py --host 127.0.0.1 --port $PORT
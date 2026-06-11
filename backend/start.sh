#!/bin/bash

# Startup script for Songify Backend
# Usage: ./start.sh [port]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=${1:-8000}

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

cd "$SCRIPT_DIR"

# Create logs directory
mkdir -p logs

# Install the full dependency set when the virtualenv is incomplete.
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "Installing backend dependencies..."
    python -m pip install -r "$SCRIPT_DIR/requirments.txt"
fi

# Run the server with logging to file
echo "Starting Songify API on port $PORT..."
echo "Logs will be written to: $SCRIPT_DIR/logs/app.log"
"$SCRIPT_DIR/.venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload 2>&1 | tee -a logs/app.log

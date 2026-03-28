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

# Check if numpy is installed (needed for basic-pitch)
if ! python -c "import numpy" 2>/dev/null; then
    echo "Installing numpy..."
    pip install "numpy<2" --only-binary=:all:
fi

# Check if basic-pitch is installed
if ! python -c "import basic_pitch" 2>/dev/null; then
    echo "Installing basic-pitch and dependencies..."
    
    # Install mir-eval first (required by basic-pitch)
    pip install mir-eval --no-deps 2>/dev/null || true
    
    # Install basic-pitch without dependencies
    pip install basic-pitch --no-deps
    
    # Install required dependencies manually
    pip install librosa pretty_midi onnxruntime 2>/dev/null || true
fi

# Run the server with logging to file
echo "Starting Songify API on port $PORT..."
echo "Logs will be written to: $SCRIPT_DIR/logs/app.log"
uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload 2>&1 | tee -a logs/app.log

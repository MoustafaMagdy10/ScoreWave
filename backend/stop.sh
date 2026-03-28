#!/bin/bash

echo "Stopping Songify server..."

pgrep -f "uvicorn" | xargs -r kill 2>/dev/null
pgrep -f "python.*main" | xargs -r kill 2>/dev/null

sleep 1

if pgrep -f "uvicorn" > /dev/null || pgrep -f "python.*main" > /dev/null; then
    echo "Forcing kill..."
    pkill -9 -f "uvicorn" 2>/dev/null
    pkill -9 -f "python.*main" 2>/dev/null
fi

echo "Cleaning logs..."
> logs/app.log 2>/dev/null
rm -f logs/*.log 2>/dev/null

echo "Server stopped and logs cleaned."

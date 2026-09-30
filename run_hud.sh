#!/bin/bash
# AGY Context HUD launcher for macOS
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Kill existing instance if running
pkill -f "python.*hud_app.py" 2>/dev/null || true

# Run with python3 in background
nohup python3 hud_app.py > /dev/null 2>&1 &
echo "AGY Context HUD launched in background."

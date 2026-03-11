#!/bin/bash
# Run the bot (Linux/Mac). Auto-restarts on crash.
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true
while true; do
    python main.py
    echo "Bot stopped. Restarting in 5s..."
    sleep 5
done

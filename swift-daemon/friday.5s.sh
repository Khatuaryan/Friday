#!/bin/bash
# F.R.I.D.A.Y. SwiftBar Plugin
# Shows status in macOS menubar
# Refresh: every 5 seconds

# Check if FRIDAY Python process is running
FRIDAY_PID=$(pgrep -f "friday" 2>/dev/null | head -1)

if [ -n "$FRIDAY_PID" ]; then
    # FRIDAY is active
    MEM_MB=$(ps -o rss= -p "$FRIDAY_PID" 2>/dev/null | awk '{printf "%.0f", $1/1024}')
    echo "🤖 ${MEM_MB}MB"
    echo "---"
    echo "Status: Active | color=green"
    echo "Memory: ${MEM_MB} MB"
    echo "PID: ${FRIDAY_PID}"
    echo "---"
    echo "Stop FRIDAY | bash='kill ${FRIDAY_PID}' terminal=false"
else
    # FRIDAY is idle
    echo "🤖"
    echo "---"
    echo "Status: Idle | color=gray"
    AVAIL=$(vm_stat | awk '/free/ {printf "%.1f", $3*4096/1024/1024/1024}')
    echo "Available RAM: ${AVAIL} GB"
    echo "---"
    echo "Start FRIDAY | bash='cd ~/PycharmProjects/Friday && source .venv/bin/activate && python -m src.core' terminal=true"
fi
echo "---"
echo "Memory Monitor | bash='cd ~/PycharmProjects/Friday && source .venv/bin/activate && python scripts/monitor_pressure.py' terminal=true"
echo "Benchmark RAM | bash='cd ~/PycharmProjects/Friday && source .venv/bin/activate && python scripts/benchmark_memory.py' terminal=true"
echo "Refresh | refresh=true"

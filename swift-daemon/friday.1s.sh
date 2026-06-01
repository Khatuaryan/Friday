#!/bin/bash
# F.R.I.D.A.Y. SwiftBar Plugin v2
# Real-time status via file-based IPC
# Refresh: every 1 second

STATUS_FILE="$HOME/.cache/friday/status.json"
PID_FILE="$HOME/.cache/friday/friday.pid"
COMMAND_DIR="$HOME/.cache/friday/commands"
FRIDAY_DIR="$HOME/PycharmProjects/Friday"
VENV_PYTHON="$FRIDAY_DIR/.venv/bin/python"

ICON_SVG="$FRIDAY_DIR/assets/friday-icon.svg"

# ── Read status ──────────────────────────────────────────────
if [ -f "$STATUS_FILE" ]; then
    STATE=$(python3 -c "import json,sys; d=json.load(open('$STATUS_FILE')); print(d.get('state','unknown'))" 2>/dev/null)
    RSS=$(python3 -c "import json,sys; d=json.load(open('$STATUS_FILE')); print(d.get('rss_mb',0))" 2>/dev/null)
    PRESSURE=$(python3 -c "import json,sys; d=json.load(open('$STATUS_FILE')); print(d.get('pressure','normal'))" 2>/dev/null)
else
    STATE="offline"
    RSS="0"
    PRESSURE="normal"
fi

# ── Status icon (SVG with fallback to emoji) ─────────────────
if [ -f "$ICON_SVG" ]; then
    ICON_B64=$(base64 < "$ICON_SVG" | tr -d '\n')
    ICON_PART="| templateImage=$ICON_B64"
else
    case "$STATE" in
        "idle"|"listening")  ICON_PART="🟢" ;;
        "verifying")         ICON_PART="🔵" ;;
        "ready")             ICON_PART="🔵" ;;
        "processing")        ICON_PART="🟡" ;;
        "speaking")          ICON_PART="🔊" ;;
        "offline")           ICON_PART="⚫" ;;
        *)                   ICON_PART="⚪" ;;
    esac
fi

# Memory pressure color
case "$PRESSURE" in
    "critical") MEM_COLOR="red" ;;
    "warning")  MEM_COLOR="orange" ;;
    *)          MEM_COLOR="green" ;;
esac

# ── Menu bar display ─────────────────────────────────────────
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
    # Running: click will toggle listening state
    echo "${RSS}MB $ICON_PART bash='touch $COMMAND_DIR/toggle_listening.cmd' terminal=false refresh=true"
else
    # Not running: click will start FRIDAY silently in background
    echo "${RSS}MB $ICON_PART bash='cd $FRIDAY_DIR && source .venv/bin/activate && nohup $VENV_PYTHON -m src.core >/dev/null 2>&1 &' terminal=false refresh=true"
fi
echo "---"

# Status section
echo "F.R.I.D.A.Y. | size=14 color=#888888"
echo "Status: $STATE | color=white"
echo "Memory: ${RSS} MB | color=$MEM_COLOR"
echo "---"

# Controls (only shown when process is running)
if [ -f "$PID_FILE" ]; then
    FRIDAY_PID=$(cat "$PID_FILE" 2>/dev/null)

    if kill -0 "$FRIDAY_PID" 2>/dev/null; then
        # Process is alive
        if [ "$STATE" = "listening" ]; then
            echo "⏸ Pause Listening | bash='touch $COMMAND_DIR/toggle_listening.cmd' terminal=false refresh=true"
        else
            echo "▶ Resume Listening | bash='touch $COMMAND_DIR/toggle_listening.cmd' terminal=false refresh=true"
        fi

        echo "🗑 Clear Conversation History | bash='touch $COMMAND_DIR/clear_history.cmd' terminal=false refresh=true"
        echo "---"
        echo "🛑 Stop FRIDAY | bash='touch $COMMAND_DIR/stop.cmd' terminal=false refresh=true color=red"
    else
        # PID file exists but process is dead — stale
        echo "FRIDAY crashed | color=red"
        echo "---"
        echo "▶ Start FRIDAY | bash='cd $FRIDAY_DIR && source .venv/bin/activate && nohup $VENV_PYTHON -m src.core >/dev/null 2>&1 &' terminal=false refresh=true"
        # Clean up stale PID
        rm -f "$PID_FILE"
    fi
else
    # Not running
    echo "---"
    echo "▶ Start FRIDAY | bash='cd $FRIDAY_DIR && source .venv/bin/activate && nohup $VENV_PYTHON -m src.core >/dev/null 2>&1 &' terminal=false refresh=true"
fi

echo "---"

# Diagnostic submenu
echo "Diagnostics"
echo "--📊 Run Benchmark | bash='cd $FRIDAY_DIR && $VENV_PYTHON scripts/benchmark_memory.py' terminal=true"
echo "--📈 Monitor Memory | bash='cd $FRIDAY_DIR && $VENV_PYTHON scripts/monitor_pressure.py' terminal=true"
echo "--📋 Open Logs | bash='open $FRIDAY_DIR/logs/friday.log' terminal=false"
echo "--👤 Enroll Face | bash='cd $FRIDAY_DIR && $VENV_PYTHON scripts/setup/enroll_face.py' terminal=true"

echo "---"
echo "🔄 Refresh | refresh=true"

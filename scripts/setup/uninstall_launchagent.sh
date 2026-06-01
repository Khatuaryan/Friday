#!/bin/bash
# Removes F.R.I.D.A.Y. LaunchAgent
# Usage: bash scripts/setup/uninstall_launchagent.sh

PLIST_PATH="$HOME/Library/LaunchAgents/com.aryan.friday.plist"

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm "$PLIST_PATH"
    echo "✅ LaunchAgent removed. FRIDAY will not start automatically."
else
    echo "LaunchAgent not installed."
fi

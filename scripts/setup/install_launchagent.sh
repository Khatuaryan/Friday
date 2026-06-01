#!/bin/bash
# Install F.R.I.D.A.Y. as a macOS LaunchAgent
# Runs automatically on login, restarts on crash
# Usage: bash scripts/setup/install_launchagent.sh

set -euo pipefail

FRIDAY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PYTHON="$FRIDAY_DIR/.venv/bin/python"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.aryan.friday.plist"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "Installing F.R.I.D.A.Y. LaunchAgent..."
echo "Project directory: $FRIDAY_DIR"

# Verify entry point exists
if [ ! -f "$FRIDAY_DIR/src/core/__main__.py" ]; then
    echo "❌ Entry point not found: src/core/__main__.py"
    echo "   Complete Phase 6B before installing LaunchAgent"
    exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Virtual environment not found: $VENV_PYTHON"
    echo "   Run: make install"
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/.cache/friday/commands"
mkdir -p "$FRIDAY_DIR/logs"

# Write plist
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aryan.friday</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PYTHON</string>
        <string>-m</string>
        <string>src.core</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$FRIDAY_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>$FRIDAY_DIR/logs/friday.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$FRIDAY_DIR/logs/friday.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>FRIDAY_HOME</key>
        <string>$FRIDAY_DIR</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Plist written to: $PLIST_PATH"

# Load the agent
if launchctl list 2>/dev/null | grep -q "com.aryan.friday"; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

launchctl load "$PLIST_PATH"
echo "✅ LaunchAgent loaded"
echo ""
echo "FRIDAY will now start automatically on login."
echo ""
echo "Management commands:"
echo "  Start:   launchctl start com.aryan.friday"
echo "  Stop:    launchctl stop com.aryan.friday"
echo "  Disable: launchctl unload $PLIST_PATH"
echo "  Status:  launchctl list | grep friday"

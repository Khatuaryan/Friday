"""
IPC State Bridge — File-based communication between Python core and SwiftBar menu bar.

Design:
    Python → SwiftBar:  Writes ~/.cache/friday/status.json on every ActivationState change.
    SwiftBar → Python:  Creates .cmd marker files in ~/.cache/friday/commands/.
                        A daemon thread polls this directory every 0.5s, processes commands,
                        and deletes the marker files.

No sockets. No subprocess. Reliable across restarts and cold starts.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("friday.ipc")

STATUS_FILE = Path("~/.cache/friday/status.json").expanduser()
COMMAND_DIR = Path("~/.cache/friday/commands").expanduser()
PID_FILE = Path("~/.cache/friday/friday.pid").expanduser()


class IPCBridge:
    """
    File-based IPC bridge between Python core and SwiftBar menu bar.

    Python → SwiftBar: writes status.json on every state change
    SwiftBar → Python: creates command files, Python polls and deletes them
    """

    VALID_COMMANDS = {
        "toggle_listening",  # SIGUSR1 equivalent
        "stop",              # Graceful shutdown
        "clear_history",     # Clear conversation history
    }

    def __init__(self, activation_handler=None):
        self.handler = activation_handler
        self._running = False
        self._thread: threading.Thread | None = None

        # Ensure directories exist
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        COMMAND_DIR.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start command polling thread and write PID."""
        # Write PID file for SwiftBar to send signals
        PID_FILE.write_text(str(os.getpid()))

        self._running = True
        self._thread = threading.Thread(
            target=self._command_poll_loop,
            daemon=True,
            name="friday-ipc",
        )
        self._thread.start()
        logger.info("IPC bridge started (PID: %d)", os.getpid())

    def stop(self):
        """Stop polling and clean up state files."""
        self._running = False
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
        self.write_status("offline", {})
        logger.info("IPC bridge stopped")

    def write_status(
        self,
        state: str,
        extra: dict | None = None,
    ) -> None:
        """
        Write current state to status.json.
        Called by ActivationHandler on every state transition.

        state: "idle" | "listening" | "verifying" | "ready" |
               "processing" | "speaking" | "offline"
        """
        try:
            from src.memory.manager import memory_manager
            mem_status = memory_manager.get_status()
            rss_mb = mem_status.friday_rss_gb * 1024
            pressure = mem_status.pressure_level.value
        except Exception:
            rss_mb = 0
            pressure = "unknown"

        payload = {
            "state": state,
            "timestamp": datetime.now().isoformat(),
            "rss_mb": round(rss_mb, 1),
            "pressure": pressure,
            "pid": os.getpid(),
        }
        if extra:
            payload.update(extra)

        try:
            STATUS_FILE.write_text(json.dumps(payload))
        except Exception as e:
            logger.debug("IPC write failed: %s", e)

    def _command_poll_loop(self):
        """Poll command directory every 0.5 seconds."""
        while self._running:
            try:
                for cmd_file in COMMAND_DIR.iterdir():
                    if cmd_file.suffix == ".cmd":
                        command = cmd_file.stem
                        if command in self.VALID_COMMANDS:
                            logger.info("IPC command received: %s", command)
                            self._execute_command(command)
                        try:
                            cmd_file.unlink()  # Always delete, even unknown
                        except OSError:
                            pass
            except Exception as e:
                logger.debug("IPC poll error: %s", e)

            time.sleep(0.5)

    def _execute_command(self, command: str):
        """Execute a received command."""
        if not self.handler:
            return

        if command == "toggle_listening":
            import signal as _signal
            os.kill(os.getpid(), _signal.SIGUSR1)

        elif command == "stop":
            import signal as _signal
            os.kill(os.getpid(), _signal.SIGTERM)

        elif command == "clear_history":
            if (
                hasattr(self.handler, "_voice_pipeline")
                and self.handler._voice_pipeline
                and self.handler._voice_pipeline.brain
            ):
                self.handler._voice_pipeline.brain.clear_history()
                logger.info("Conversation history cleared via IPC")

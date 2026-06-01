# Walkthrough — Phase Set 6: System Integration & Infrastructure

## Summary

Transformed F.R.I.D.A.Y. from a functional research demo into a production-grade macOS product with centralized infrastructure, a proper CLI entry point, real-time menu bar integration via IPC, auto-start on login, a transparent floating siri-like visualizer HUD, and clean management commands.

---

## Changes Made

### Phase 6A — Infrastructure Foundation

**New files:**

| File | Purpose |
|------|---------|
| [constants.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/constants.py) | Centralizes audio sample rates, wake-word sizes, memory thresholds, face verification limits, file-based IPC paths, and constants. |
| [logger.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/logger.py) | Configures a custom rotating file logger (10MB rotations, 3 backups) with thread-safe formatting. |
| [config.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/config.py) | Sets up Pydantic v2 `FridayConfig` configuration validation layer. |
| [overlay.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/overlay.py) | Designed and implemented the transparent Siri-like floating neon orb visualizer overlay in a dedicated Tkinter background graphics thread, pulsing concentric circles based on real-time ASR, CPU processing, and streamed TTS audio amplitude updates. |

**Cross-cutting migration:** 28 source files migrated from `import logging` / `logging.getLogger()` to `from src.utils.logger import get_logger` / `get_logger()`.

---

### Phase 6B — Production Entry Point

**New file:** [\_\_main\_\_.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/__main__.py)
* Entry point supporting CLI switches: `--debug` for verbose debugging, `--dry-run` for pre-flight environment diagnostics, `--no-face` to bypass facial check, `--no-brain` to skip reasoning model boot, and `--camera N` to specify device index.
* Signal hooks for SIGINT/SIGTERM graceful shutdowns and SIGUSR1 manual toggling.

**Modified:** [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
* Added `skip_face_verification` and `load_brain` parameters.
* Instantiates and drives the Tkinter glowing orb visualizer background graphics thread dynamically during state transitions.

---

### Phase 6C — IPC State Bridge & Plugins

**New file:** [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)
* Python writes system state, RSS memory usage, and status to `~/.cache/friday/status.json` on every state change, while polling for `.cmd` files representing SwiftBar actions.

---

### Phase 6D — SwiftBar Plugin

**New file:** [friday.1s.sh](file:///Users/khatuaryan/PycharmProjects/Friday/swift-daemon/friday.1s.sh)
* Real-time 1-second SwiftBar plugin displaying status, visual indicators, active RAM limits, and manual triggers.

---

### Phase 6E — macOS launchd Integration

**New files:**
* [install_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/install_launchagent.sh) — Creates `com.aryan.friday.plist`, sets `RunAtLoad=true`, `KeepAlive.SuccessfulExit=false`
* [uninstall_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/uninstall_launchagent.sh) — Clean uninstaller

---

### Phase 6F — Makefile Targets

**Modified:** [Makefile](file:///Users/khatuaryan/PycharmProjects/Friday/Makefile)
* New targets: `run`, `run-debug`, `run-no-face`, `dry-run`, `install-agent`, `uninstall-agent`, `agent-status`, `agent-logs`.

---

## Testing

* **101 automated unit and integration tests successfully pass** (8.80s) under local mock/hardware setups.
* `make dry-run` validates config, models, biometric face signature PKLs, and memory limits.

# Walkthrough — Phase Set 6: System Integration & Infrastructure

## Summary

Transformed F.R.I.D.A.Y. from a functional research demo into a production-grade macOS product with centralized infrastructure, a proper CLI entry point, real-time menu bar integration via IPC, auto-start on login, and clean management commands.

---

## Changes Made

### Phase 6A — Infrastructure Foundation

**New files:**

| File | Purpose |
|------|---------|
| [constants.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/constants.py) | All magic numbers centralized (audio, memory, brain, storage, IPC, paths, face) |
| [logger.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/logger.py) | `setup_logging()` with rotating file handler (10MB, 3 backups) + `get_logger()` |
| [config.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/config.py) | Pydantic v2 `FridayConfig` with `model_validator` ensuring active_model ∈ registry |

**Cross-cutting migration:** 28 source files migrated from `import logging` / `logging.getLogger()` to `from src.utils.logger import get_logger` / `get_logger()`. Automated via migration script.

---

### Phase 6B — Production Entry Point

**New file:** [\_\_main\_\_.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/__main__.py)

```
python -m src.core                # Production start
python -m src.core --debug        # DEBUG logging
python -m src.core --dry-run      # Validate config → exit
python -m src.core --no-face      # Skip face verification
python -m src.core --no-brain     # Skip LLM loading
python -m src.core --camera 1     # Override camera device
```

**Signal handling:**
- `SIGINT` / `SIGTERM` → graceful shutdown
- `SIGUSR1` → toggle listening on/off

**Modified:** [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Added `skip_face_verification` and `load_brain` parameters
- Face bypass auto-proceeds to READY state
- Brain-skip mode initializes voice pipeline without LLM

---

### Phase 6C — IPC State Bridge

**New file:** [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)

```
Python → SwiftBar:  ~/.cache/friday/status.json  (written on every state change)
SwiftBar → Python:  ~/.cache/friday/commands/*.cmd  (polled every 0.5s, deleted after processing)
```

Payload includes: `state`, `timestamp`, `rss_mb`, `pressure`, `pid`

Valid commands: `toggle_listening`, `stop`, `clear_history`

---

### Phase 6D — SwiftBar Plugin

**New file:** [friday.1s.sh](file:///Users/khatuaryan/PycharmProjects/Friday/swift-daemon/friday.1s.sh)

Replaces old `friday.5s.sh`. Reads `status.json` instead of running `pgrep`.

| State | Icon |
|-------|------|
| listening | 🟢 |
| verifying/ready | 🔵 |
| processing | 🟡 |
| speaking | 🔊 |
| offline | ⚫ |

Click controls: Pause/Resume, Clear History, Stop. Diagnostics submenu.

**Deleted:** `friday.5s.sh`

---

### Phase 6E — LaunchAgent

**New files:**
- [install_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/install_launchagent.sh) — Creates `com.aryan.friday.plist`, sets `RunAtLoad=true`, `KeepAlive.SuccessfulExit=false`
- [uninstall_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/uninstall_launchagent.sh) — Clean removal

---

### Phase 6F — Makefile Targets

**Modified:** [Makefile](file:///Users/khatuaryan/PycharmProjects/Friday/Makefile)

New targets: `run`, `run-debug`, `run-no-face`, `dry-run`, `install-agent`, `uninstall-agent`, `agent-status`, `agent-logs`. Help reorganized into Run/LaunchAgent/Setup/Test/Diagnostics sections.

---

## Testing

- **104 unit tests passed** (9.14s) after the 28-file logger migration
- `make dry-run` validates config, model, face encodings, memory
- No regressions introduced

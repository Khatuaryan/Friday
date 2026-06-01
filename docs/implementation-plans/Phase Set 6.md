# Implementation Plan — Phase Set 6: System Integration & Infrastructure

This plan transforms F.R.I.D.A.Y. from a functional research demo into a production-grade macOS product with a clean entry point, real-time menu bar integration, auto-start on login, centralized logging, type-safe configuration, and a transparent neon visualizer HUD.

---

## User Review Required

> [!IMPORTANT]
> - **Cross-cutting Logger Migration**: Migrates all modules to use a centralized rotating file logger (`src/utils/logger.py`) with 10MB rotations and 3 backups.
> - **Unified Pydantic Config Validation**: boot fails fast on invalid YAML config files (`config/friday_config.yaml`).
> - **Transparent Siri-Like Neon visualizer**: Implements the glowing concentric Tkinter visualizer overlay HUD in a dedicated graphics thread, synchronized with the activation handler status changes.

---

## Proposed Changes

### Component 1: Centralized Utilities (Phase 6A)

#### [NEW] [constants.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/constants.py)
* Centralize all magical numbers (audio sample rates, wake-word sizes, memory thresholds, face verification limits, file-based IPC paths, constants).

#### [NEW] [logger.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/logger.py)
* Setup rotating console and log files, migrating 28 source files from generic `logging.getLogger` calls to our custom centralized `get_logger()`.

#### [NEW] [config.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/config.py)
* Pydantic v2 `FridayConfig` configuration validation layer.

#### [NEW] [overlay.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/overlay.py)
* Floating visualizer HUD module in Tkinter. Implements a borderless, transparent, floating screen overlay with concentric glowing neon rings.
* Driven by a thread-safe graphics thread loop that dynamically polls the main voice activation handler's state to transition ring colors and pulse amplitudes in real-time.

---

### Component 2: Production CLI Entry Point (Phase 6B)

#### [NEW] [\_\_main\_\_.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/__main__.py)
* Entry point supporting CLI switches: `--debug` for verbose debugging, `--dry-run` for pre-flight environment diagnostics, `--no-face` to bypass facial check, `--no-brain` to skip reasoning model boot, and `--camera N` to specify device index.
* Signal hooks for SIGINT/SIGTERM graceful shutdowns and SIGUSR1 manual toggling.

---

### Component 3: IPC State Bridge & Plugins (Phase 6C & 6D)

#### [NEW] [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)
* File-based IPC state bridge. Python writes system state, RSS memory usage, and status to `~/.cache/friday/status.json` on every state change, while polling for `.cmd` files representing SwiftBar actions.

#### [NEW] [friday.1s.sh](file:///Users/khatuaryan/PycharmProjects/Friday/swift-daemon/friday.1s.sh)
* Real-time 1-second SwiftBar plugin displaying status, visual indicators, active RAM limits, and manual triggers.

---

### Component 4: macOS launchd Integration (Phase 6E)

#### [NEW] [install_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/install_launchagent.sh)
* Automatically generates `~/Library/LaunchAgents/com.aryan.friday.plist` plists to start F.R.I.D.A.Y. silently in the background at user log-in.

---

## Verification Plan

### Automated Tests
```bash
# Verify all unit tests continue to pass after system-wide migrations
python -m pytest tests/ -v
```

### Manual Verification
1. Run pre-flight check to verify config:
   ```bash
   make dry-run
   ```
2. Launch daemon and verify the floating circular neon visualizer overlay boots and pulses correctly:
   ```bash
   make run
   ```
3. Click SwiftBar triggers and verify actions (Pause, Resume, Stop) route seamlessly.

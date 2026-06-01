# Implementation Plan — Phase Set 6: System Integration & Infrastructure

This plan transforms F.R.I.D.A.Y. from a functional research demo into a production-grade macOS product with a clean entry point, real-time menu bar integration, auto-start on login, centralized logging, and type-safe configuration.

---

## User Review Required

> [!IMPORTANT]
> - **28 source files will be modified** for the logger migration (`logging.getLogger()` → `get_logger()`). This is a cross-cutting refactor that touches every module in `src/`.
> - **Pydantic config validation** will make boot fail-fast on invalid YAML. The current `friday_config.yaml` has a `models.llm` section that duplicates `models_registry`. The Pydantic model will validate `models_registry` and `active_model`; the legacy `models` section will be ignored (not deleted, for backward compat).
> - **IPC mechanism is file-based JSON** (`~/.cache/friday/status.json`), not Unix sockets. SwiftBar reads this file every 1 second — acceptable since it's just a `cat` of a ~200-byte file.
> - **LaunchAgent**: The plist will use `KeepAlive.SuccessfulExit = false`, meaning macOS restarts F.R.I.D.A.Y. automatically if it crashes, but not if you stop it cleanly via `Ctrl+C` or `launchctl stop`.

> [!WARNING]
> - **`ActivationHandler.__init__` signature changes**: Two new optional parameters (`skip_face_verification`, `load_brain`). All existing callers (integration tests) will continue to work since both default to `False`/`True`.
> - **The old `swift-daemon/friday.5s.sh` will be replaced** with `swift-daemon/friday.1s.sh`. If you have the old script symlinked in SwiftBar's plugins directory, you'll need to update the symlink.

---

## Proposed Changes

### Component 1: Infrastructure Foundation (Phase 6A)

#### [NEW] [\_\_init\_\_.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/__init__.py)
Empty init to make `src/utils` a package.

---

#### [NEW] [constants.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/constants.py)
Centralized constants file — zero imports, pure Python literals. Groups:
- **Audio**: `SAMPLE_RATE`, `CHANNELS`, `VAD_FRAME_SAMPLES`, `VAD_FRAME_BYTES`, `WAKE_WORD_CHUNK_SIZE`, `DEFAULT_LISTEN_TIMEOUT`, `DEFAULT_SILENCE_DURATION`, `CONFIRMATION_TIMEOUT`
- **Memory**: `FRIDAY_BUDGET_GB`, `DEFAULT_SAFETY_BUFFER_GB`, `MIN_SAFETY_BUFFER_GB`, `WARNING_THRESHOLD_PERCENT`, `CRITICAL_THRESHOLD_PERCENT`, `MAX_CONVERSATION_TURNS`, `MAX_RAG_RESULTS`, `EMBEDDING_DIM`, `EMBEDDING_IDLE_TIMEOUT_S`
- **Brain**: `MAX_INPUT_CHARS`, `MAX_RESPONSE_CHARS`, `MAX_TOOL_CALLS`, `DEFAULT_MAX_TOKENS`, `DEFAULT_TEMPERATURE`, `REPETITION_PENALTY`, `REPETITION_CONTEXT_SIZE`
- **Storage**: `MAX_FILE_READ_BYTES`, `MAX_FILE_WRITE_BYTES`, `MAX_CLIPBOARD_CHARS`, `MAX_SHELL_OUTPUT_CHARS`, `MAX_CONVERSATION_HISTORY`, `SHELL_TIMEOUT_S`
- **Tools**: `RATE_LIMIT_CALLS`, `RATE_LIMIT_WINDOW_S`
- **IPC**: `STATUS_FILE`, `COMMAND_DIR`, `STATUS_UPDATE_INTERVAL_S`
- **Paths**: `CONFIG_FILE`, `MODELS_DIR`, `DATA_DIR`, `LOGS_DIR`, `FACES_DIR`, `MEMORY_DB`, `BENCHMARKS_DIR`
- **Face**: `FACE_THRESHOLD`, `FACE_TIMEOUT_S`, `MIN_ENROLLMENT_PHOTOS`

After creating this file, replace scattered magic numbers across the codebase with constant imports from here.

---

#### [NEW] [logger.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/logger.py)
Centralized logging setup with:
- `setup_logging(level, log_to_file)` — configures root logger with console + rotating file handler (10MB, 3 backups)
- `get_logger(name)` — ensures setup is called, returns named logger

**Cross-cutting migration** — replace `logging.getLogger("friday.X")` with `get_logger("friday.X")` in all 28 source files under `src/`:

| Directory | Files |
|-----------|-------|
| `src/core/` | `brain.py`, `activation_handler.py`, `prompts.py` |
| `src/memory/` | `manager.py`, `store.py`, `embeddings.py`, `encryption.py` |
| `src/modules/audio/` | `wake_word.py`, `stt.py`, `tts.py` |
| `src/modules/vision/` | `face_recognizer.py` |
| `src/modules/` | `voice_pipeline.py` |
| `src/tools/` | `base.py`, `server.py`, `calendar_tool.py`, `calendar_write_tool.py`, `reminder_tool.py`, `file_tool.py`, `file_write_tool.py`, `shell_tool.py`, `app_tool.py`, `media_tool.py`, `clipboard_tool.py`, `message_tool.py`, `email_tool.py`, `web_tool.py`, `system_tool.py` |
| `src/context/` | `tracker.py` |
| `src/proactive/` | `engine.py` |

---

#### [NEW] [config.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/config.py)
Pydantic v2 configuration validation:
- `FridayConfig` model with `HardwareConfig`, `ModelEntry`, `MemoryConfig` sub-models
- `@field_validator` to ensure `active_model` exists in `models_registry`
- `load_config()` / `get_config()` singleton pattern
- Replaces raw `yaml.safe_load()` usage in `brain.py` and `manager.py`

**Pydantic is already installed** (`pydantic==2.13.4` in `.venv`).

---

### Component 2: Production Entry Point (Phase 6B)

#### [NEW] [\_\_main\_\_.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/__main__.py)
Clean CLI entry point supporting:
- `python -m src.core` — production start
- `python -m src.core --debug` — DEBUG logging
- `python -m src.core --dry-run` — validate config & environment, exit
- `python -m src.core --no-face` — skip face verification (dev mode)
- `python -m src.core --no-brain` — skip LLM loading (tool testing)
- `python -m src.core --camera N` — override camera index

Signal handlers:
- `SIGINT` → graceful shutdown
- `SIGTERM` → graceful shutdown (for LaunchAgent)
- `SIGUSR1` → toggle listening on/off

Pre-flight `validate_environment()` checks: config validity, model files, face encodings, memory status.

#### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Add `skip_face_verification: bool = False` and `load_brain: bool = True` to `__init__`
- If `skip_face_verification=True`, `_handle_activation()` auto-proceeds as if boss verified
- If `load_brain=False`, skip `FridayBrain` initialization in `start()`
- Add `ipc_bridge` attribute wired in Phase 6C

---

### Component 3: IPC State Bridge (Phase 6C)

#### [NEW] [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)
File-based IPC bridge:
- **Python → SwiftBar**: Writes `~/.cache/friday/status.json` on every `ActivationState` change. Payload: `state`, `timestamp`, `rss_mb`, `pressure`, `pid`.
- **SwiftBar → Python**: Creates `.cmd` marker files in `~/.cache/friday/commands/`. A daemon thread polls every 0.5s, processes valid commands (`toggle_listening`, `stop`, `clear_history`), and deletes the files.
- Writes PID to `~/.cache/friday/friday.pid` for SwiftBar signal routing.

#### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Initialize `IPCBridge` in `start()` and wire `write_status()` into `_set_state()`
- Call `ipc_bridge.stop()` in `stop()`

---

### Component 4: SwiftBar Plugin (Phase 6D)

#### [NEW] [friday.1s.sh](file:///Users/khatuaryan/PycharmProjects/Friday/swift-daemon/friday.1s.sh)
Replaces the old `friday.5s.sh` polling script. Reads `~/.cache/friday/status.json` instead of running `pgrep`. Features:
- Dynamic status icon: 🟢 idle/listening, 🔵 verifying, 🟡 processing, 🔊 speaking, ⚫ offline
- Memory display with pressure-based coloring (green/orange/red)
- Click controls: Pause/Resume Listening, Clear History, Stop — via `.cmd` file creation
- Diagnostics submenu: benchmarks, memory monitor, open logs, enroll face
- Crash detection: stale PID file → "FRIDAY crashed" + start button

#### [DELETE] [friday.5s.sh](file:///Users/khatuaryan/PycharmProjects/Friday/swift-daemon/friday.5s.sh)
Replaced by `friday.1s.sh`.

---

### Component 5: LaunchAgent (Phase 6E)

#### [NEW] [install_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/install_launchagent.sh)
Installer script that:
- Validates entry point and venv exist
- Creates `~/Library/LaunchAgents/com.aryan.friday.plist`
- Sets `RunAtLoad=true`, `KeepAlive.SuccessfulExit=false`, `ThrottleInterval=10`
- Routes stdout/stderr to `logs/friday.stdout.log` and `logs/friday.stderr.log`
- Loads the agent via `launchctl load`

#### [NEW] [uninstall_launchagent.sh](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/uninstall_launchagent.sh)
Clean uninstaller.

---

### Component 6: Makefile Targets (Phase 6F)

#### [MODIFY] [Makefile](file:///Users/khatuaryan/PycharmProjects/Friday/Makefile)
Add targets:
- `make run` — `python -m src.core`
- `make run-debug` — `python -m src.core --debug`
- `make run-no-face` — `python -m src.core --no-face`
- `make dry-run` — `python -m src.core --dry-run`
- `make install-agent` / `make uninstall-agent` / `make agent-status` / `make agent-logs`

Update `help` target to list all new commands.

---

## Verification Plan

### Automated Tests
```bash
# After Phase 6A — constants, logger, config all import correctly
python -c "from src.utils.constants import SAMPLE_RATE; assert SAMPLE_RATE == 16000; print('✅ constants')"
python -c "from src.utils.logger import get_logger; l = get_logger('test'); l.info('ok'); print('✅ logger')"
python -c "from src.utils.config import load_config; c = load_config(); print(f'✅ config: {c.active_model}')"

# Full test suite still passes after logger migration
FRIDAY_MEM_BUFFER=0.0 .venv/bin/pytest tests/ -v
```

### Manual Verification
```bash
# Phase 6B — entry point
python -m src.core --dry-run          # validates config, exits 0
python -m src.core --no-brain --no-face &  # starts without LLM
kill -SIGTERM $!                      # graceful shutdown logged

# Phase 6C — IPC bridge writes status
python -m src.core --no-brain --no-face &
sleep 3 && cat ~/.cache/friday/status.json  # valid JSON with state
kill $!

# Phase 6D — SwiftBar shows real state (visual check)
# Phase 6E — LaunchAgent installs and auto-starts
bash scripts/setup/install_launchagent.sh
launchctl list | grep friday

# Phase 6F — Makefile
make dry-run && make run-debug  # Ctrl+C after 5s
```

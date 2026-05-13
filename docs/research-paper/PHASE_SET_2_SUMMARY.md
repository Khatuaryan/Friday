# Phase Set 2 Summary — Voice & Brain Integration

**Completed:** May 2026  
**Status:** ✅ All phases implemented, tested, merged to main  
**Test Suite:** 45/45 passing (21 new tests added)

---

## Phase 3: Voice Pipeline (STT + TTS)

### Speech-to-Text (STT)
- **Engine:** Distil-Whisper Small via `mlx-whisper` (Apple Silicon optimized)
- **Architecture:** Queue-based (mirrors `wake_word.py` pattern)
  - Audio thread: PyAudio callback → enqueues raw int16 chunks
  - Worker thread: WebRTC VAD in separate thread (not callback)
  - Auto-stop: Silence detection after speech (configurable duration)
- **Memory:** ~600 MB (lazy loaded on first transcription)
- **Model:** `mlx-community/distil-whisper-small.en` (downloaded via `make download-whisper`)

### Text-to-Speech (TTS)
- **Engine:** macOS native `say` command
- **Architecture:** Queue-based with `threading.Lock` for thread safety
- **Memory:** 0 MB (uses OS built-in speech synthesis)
- **Features:** Configurable voice/rate, subprocess stdin for shell safety

### Voice Pipeline Orchestrator
- **Flow:** STT → Brain → TTS (sequential)
- **Location:** `src/modules/voice_pipeline.py`
- **Brain integration:** Optional — falls back to echo mode if brain unavailable

---

## Phase 4: Brain Integration

### Conversation History
- **10-turn cap** to stay within 8GB memory budget
- **Phi-3.5-mini chat template** with proper `<|end|>` tags per turn
- **API:** `clear_history()`, `get_history_length()`
- `think()` accepts `add_to_history=True|False`
- `think_stream()` commits history after stream completes

### Activation Handler Integration
- Brain loaded on `start()` with graceful fallback
- Full pipeline: Wake Word → Face → TTS greeting → STT → Brain → TTS response

---

## Phase 5: MCP Tool Servers

### Tool Infrastructure
- **Base class:** `src/tools/base.py` — `name`, `description`, `execute()`, `safe_execute()`
- **Server:** `src/tools/server.py` — Registration, `<tool_call>` regex parsing, execution routing
- **Brain method:** `think_with_tools()` — Accumulates tool results in message chain

### Tools Implemented
| Tool | Module | Description | Memory |
|------|--------|-------------|--------|
| Calendar | `calendar_tool.py` | EventKit with async semaphore auth | ~0 MB |
| File | `file_tool.py` | Sandboxed read (~/Documents, ~/Desktop, ~/Downloads) | ~0 MB |
| System | `system_tool.py` | Battery, storage, memory, network via psutil | ~0 MB |

### Safety
- File tool: Path traversal blocked, 100KB size limit
- Calendar: Proper async authorization with 30s timeout
- Tool server: JSON parse error handling, unknown tool rejection

---

## Memory Budget

```
Component                    Allocated    Actual
─────────────────────────────────────────────────
Python runtime                 300 MB     ~300 MB
OpenWakeWord                    50 MB      ~50 MB
Phi-3.5-mini (4-bit)         2,200 MB   ~2,200 MB
Distil-Whisper (lazy)          600 MB     ~600 MB*
macOS TTS (say)                  0 MB       0 MB
MCP Tools (psutil/pyobjc)       <5 MB      <5 MB
Overhead                       150 MB     ~150 MB
─────────────────────────────────────────────────
Total                        3,305 MB   ~3,305 MB
Budget                       3,500 MB
Buffer remaining               195 MB
```
*Whisper loaded lazily on first transcription, unloaded when idle

---

## Test Summary

| Category | File | Tests | Type |
|----------|------|-------|------|
| STT | `test_stt.py` | 4 | Automated |
| TTS | `test_tts.py` | 6 | Automated |
| Brain | `test_brain.py` | 9 | Automated |
| Tools | `test_tools.py` | 16 | Automated |
| Memory | `test_memory_manager.py` | 7 | Automated |
| Wake Word | `test_wake_word.py` | 3 | Automated |
| **Total Automated** | | **45** | |
| STT Manual | `manual_test_stt.py` | 1 | Manual |
| TTS Manual | `manual_test_tts.py` | 4 | Manual |
| Voice Pipeline | `pipeline_v2_voice.py` | 3 cycles | Integration |
| Brain Pipeline | `pipeline_v3_brain.py` | 4 | Integration |

---

## Files Changed (21 files, +1702 lines)

### New Files
- `src/modules/audio/stt.py` — STT module
- `src/modules/audio/tts.py` — TTS module (rewritten)
- `src/modules/voice_pipeline.py` — Orchestrator
- `src/tools/base.py` — Tool base class
- `src/tools/calendar_tool.py` — Calendar tool
- `src/tools/file_tool.py` — File tool
- `src/tools/system_tool.py` — System tool
- `src/tools/server.py` — MCP server
- `tests/unit/test_stt.py`, `test_tts.py`, `test_tools.py`
- `tests/unit/manual_test_stt.py`, `manual_test_tts.py`
- `tests/integration/pipeline_v2_voice.py`, `pipeline_v3_brain.py`

### Modified Files
- `src/core/brain.py` — +history, +think_with_tools()
- `src/core/activation_handler.py` — +voice pipeline integration
- `src/core/prompts.py` — Updated capabilities
- `scripts/setup/download_models.py` — Fixed PROJECT_ROOT, +whisper download
- `Makefile` — +8 new targets

---

## Make Targets

```bash
make test                   # Run all 45 automated tests
make test-stt               # Manual STT test
make test-tts               # Manual TTS test
make test-voice-pipeline    # Voice pipeline integration
make test-brain             # Brain integration (requires model)
make test-pipeline          # Full pipeline (wake word + face)
make download-whisper       # Download Distil-Whisper model
```

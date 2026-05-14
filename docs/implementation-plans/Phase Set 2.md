# Phase Set 2: Voice & Brain Integration (8GB)

## Overview

Phases 3–5 will transform F.R.I.D.A.Y. from a "wake + verify" demo into a fully conversational assistant with tool-calling capabilities. The 800MB remaining memory budget is tight but achievable.

> [!IMPORTANT]
> **Execution order**: Phase 3 (Voice) → Phase 4 (Brain) → Phase 5 (Tools). Each phase builds on the previous. I will implement and test each phase sequentially, requesting your approval before moving to the next.

## Open Questions

> [!WARNING]
> **Piper TTS on Apple Silicon**: `piper-tts` uses ONNX Runtime for inference. On some M-series Macs, the ARM64 wheel is not published and must be built from source. If installation fails, we fall back to macOS `say` (0MB) and revisit TTS later. **Do you want me to try Piper first, or go straight to `say` fallback to save time?**

> [!IMPORTANT]
> **`mlx-whisper` API**: The user prompt references `mlx_whisper.load_model()` and `mlx_whisper.transcribe()`. However, the actual `mlx-whisper` package API is `mlx_whisper.transcribe(audio_path_or_array, path_or_hf_repo=...)` — there is no separate `load_model()` call; the model is loaded lazily on first transcription. I will adapt the implementation accordingly. This is actually *better* for our memory budget since the model isn't resident when idle.

> [!NOTE]
> **`scripts/setup/` vs `config/`**: Setup scripts should **stay in `scripts/setup/`**. The `config/` directory is for declarative data (YAML, .env, JSON). Mixing executable Python/Shell scripts into `config/` violates the separation of concerns and confuses developer navigation. The current structure is correct.

---

## Phase 3: Voice Pipeline (STT + TTS)

**Branch**: `feature/phase-03-voice-pipeline`
**Memory Impact**: +600MB (STT) + ~150MB (TTS) = ~750MB

### Proposed Changes

---

#### [Dependencies]

##### [MODIFY] [requirements.txt](file:///Users/khatuaryan/PycharmProjects/Friday/requirements.txt)
- Verify existing entries for `mlx-whisper`, `piper-tts`, `sounddevice`, `webrtcvad` (already present).
- Install and validate each package.

##### [MODIFY] [download_models.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/setup/download_models.py)
- Fix `PROJECT_ROOT` (currently `.parent.parent`, needs `.parent.parent.parent`).
- Add `download_whisper()` function for `mlx-community/distil-whisper-small.en`.
- Add `download_piper_voice()` function for `en_US-lessac-medium`.
- Update `main()` to support `--model whisper`, `--model piper`, `--model all`.

---

#### [Audio Modules]

##### [MODIFY] [stt.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/stt.py)
Replace stub with full implementation:
- `SpeechToText.__init__()`: Store model path, lazy-load flag.
- `SpeechToText.listen(timeout, silence_duration)`:  Record via `sounddevice`, use `webrtcvad` for silence detection, transcribe with `mlx_whisper.transcribe()`.
- `SpeechToText.transcribe_file(path)`: For testing with pre-recorded audio.
- Memory check before first transcription via `memory_manager`.

##### [MODIFY] [tts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/tts.py)
Replace stub with full implementation:
- `TextToSpeech.__init__(voice_path, use_fallback)`: Queue-based, thread-safe.
- `TextToSpeech.speak(text, blocking)`: Piper primary, `say` fallback.
- `TextToSpeech._speak_piper(text)`: Streaming synthesis + `sounddevice` playback.
- `TextToSpeech._speak_macos(text)`: Existing `say` logic, improved.
- `TextToSpeech.stop()`: Clear queue, stop playback.

---

#### [Voice Pipeline]

##### [MODIFY] [voice_pipeline.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/voice_pipeline.py)
Replace stub with orchestrator:
- `VoicePipeline.__init__(stt, tts, brain=None)`.
- `VoicePipeline.process_voice_command(timeout)`: Listen → Transcribe → (Brain in Phase 4) → Speak.

---

#### [Integration]

##### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Import and initialize `SpeechToText`, `TextToSpeech`, `VoicePipeline` in `start()`.
- Update `_on_wake_word()`: After boss verified, greet with TTS, then run `voice_pipeline.process_voice_command()`.
- Use `ActivationState.PROCESSING` and `ActivationState.SPEAKING` states.

---

#### [Testing]

##### [NEW] `tests/unit/test_stt.py`
- Automated pytest: init, model path validation, memory guard.

##### [NEW] `tests/unit/test_tts.py`
- Automated pytest: init, queue behavior, fallback logic.

##### [NEW] `tests/unit/manual_test_stt.py`
- Manual: Record 5 seconds, transcribe, print result.

##### [NEW] `tests/unit/manual_test_tts.py`
- Manual: Speak a test sentence with Piper + fallback.

##### [NEW] `tests/integration/pipeline_v2_voice.py`
- Integration: Wake Word → Face → STT → (placeholder Brain) → TTS.

---

## Phase 4: Brain Integration

**Branch**: `feature/phase-04-brain-integration`
**Memory Impact**: 0MB (model already loaded)

### Proposed Changes

##### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
- Add `_conversation_history: List[Tuple[str, str]]` with 10-turn cap.
- Add `_add_to_history()`, `clear_history()`, `get_history_length()`.
- Update `_format_prompt()` to include conversation history.
- Add `think_with_tools()` method (Phase 5 prep).

##### [MODIFY] [prompts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/prompts.py)
- Enrich `DEFAULT_SYSTEM_PROMPT` with current capabilities.
- Keep existing `TOOL_CALLING_PROMPT` and `CONTEXT_AWARE_PROMPT`.

##### [MODIFY] [voice_pipeline.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/voice_pipeline.py)
- Wire `brain.think()` into `process_voice_command()`.

##### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Initialize `FridayBrain` in `start()`, pass to `VoicePipeline`.

##### [NEW] `tests/integration/pipeline_v3_brain.py`
- Integration: Full voice loop with LLM responses.

---

## Phase 5: MCP Tool Servers

**Branch**: `feature/phase-05-mcp-tools`
**Memory Impact**: <50MB

### Proposed Changes

##### [NEW] `src/tools/base.py`
- Abstract `Tool` class with `name`, `description`, `parameters`, `execute()`.

##### [NEW] `src/tools/calendar_tool.py`
- `CalendarTool`: Read macOS Calendar via `EventKit` (PyObjC).

##### [NEW] `src/tools/file_tool.py`
- `FileTool`: Sandboxed file read (~/Documents, ~/Desktop, ~/Downloads only).

##### [NEW] `src/tools/system_tool.py`
- `SystemTool`: Battery, storage, memory, network via `psutil`.

##### [NEW] `src/tools/server.py`
- `MCPToolServer`: Tool registration, `<tool_call>` parsing, execution routing.

##### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
- Add `think_with_tools()` implementation: Generate → Parse tool call → Execute → Feed result back → Re-generate.

##### [NEW] `tests/integration/pipeline_v4_tools.py`
- Integration: Full voice loop with tool calling.

---

## Verification Plan

### Phase 3
1. `make test` — All automated tests pass (including new STT/TTS unit tests).
2. `make test-pipeline` — v2 integration test: Wake → Face → Voice round-trip.
3. Memory check: `make benchmark-memory` confirms <3.5GB total.

### Phase 4
4. Manual brain test: Multi-turn conversation with FRIDAY persona.
5. `make test-pipeline` — v3 integration test with LLM responses.
6. Memory check: No increase from Phase 3 baseline.

### Phase 5
7. Tool server unit tests: Calendar, File (sandboxed), System.
8. `make test-pipeline` — v4 integration test: "What's my battery level?" triggers tool.
9. Security check: Restricted path access denied.

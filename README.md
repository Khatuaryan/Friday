# F.R.I.D.A.Y. v2 — 8GB-Optimized AI Assistant

Privacy-first, local-only AI assistant for macOS optimized for 8GB RAM MacBook Air.

## 📁 Project Structure

- **`src/core/`**: Orchestrators (Activation Handler, Brain, Prompts)
- **`src/memory/`**: Memory Management & Pressure Monitoring
- **`src/modules/audio/`**: Wake Word, STT, TTS
- **`src/modules/vision/`**: Face Recognition
- **`src/tools/`**: MCP Tool Servers (Calendar, File, System)
- **`tests/`**: Automated (unit) and Manual (unit/integration) tests
- **`scripts/setup/`**: One-time setup operations (Enrollment, Downloads)

## 🚀 Quick Start

```bash
# 1. Install environment & download models
make install
make download-model       # Phi-3.5-mini (2.2 GB) + Distil-Whisper (500 MB)

# 2. Enroll your face (one-time)
make enroll-face

# 3. Verify everything works
make verify-env
make test                 # Run all 45 automated tests
```

## 🧪 Systematic Testing

We use a layered testing approach:

```bash
# Unit Tests (automated + manual hardware)
make test                      # Run all 45 automated tests
make test-wake-word            # Manual: verify mic hears wake word
make test-face                 # Manual: verify camera sees your face
make test-stt                  # Manual: speak → transcribe
make test-tts                  # Manual: text → speech

# Integration Tests (sequential pipeline)
make test-pipeline             # Wake Word → Face → Voice loop
make test-voice-pipeline       # STT → Brain placeholder → TTS (3 cycles)
make test-brain                # Brain: load, converse, history (requires model)
```

## 🏗️ Architecture

| Component | Technology | Memory |
|-----------|-----------|--------|
| LLM | Phi-3.5-mini 4-bit (MLX) | 2.2 GB |
| STT | Distil-Whisper Small (mlx-whisper) | 600 MB |
| TTS | macOS `say` | 0 MB |
| Wake Word | OpenWakeWord | 50 MB |
| Face | Apple Vision Framework | 0 MB |
| MCP Tools | psutil + PyObjC | <5 MB |
| **Total** | | **~3.3 GB** |

### Voice Pipeline Flow

```
Wake Word → Face Verify → TTS "How can I help?"
                          → STT (listen + VAD)
                          → Brain.think_with_tools()
                          → Tool execution (if needed)
                          → TTS response
                          → Return to wake word
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `get_calendar_events` | Read macOS Calendar (EventKit) |
| `read_file` | Read files from sandboxed directories |
| `get_system_info` | Battery, storage, memory, network |

## 🛠️ Requirements

- macOS 13+ (Ventura or later)
- Apple Silicon (M1/M2/M3)
- 8 GB RAM minimum
- Python 3.11

## 📊 Monitoring

```bash
make monitor           # Live memory pressure monitor
make benchmark-memory  # Deep RAM analysis
make clean             # Remove caches
```

## 📄 License

Private — Personal use only.

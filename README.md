# F.R.I.D.A.Y. v2 — 8GB-Optimized AI Assistant

Privacy-first, local-only AI assistant for macOS optimized for 8GB RAM MacBook Air.

## 📁 Project Structure

- **`src/core/`**: Orchestrators (Activation Handler, Brain, Prompts)
- **`src/memory/`**: Memory Management & Pressure Monitoring
- **`src/modules/audio/`**: Wake Word, STT, TTS
- **`src/modules/vision/`**: Face Recognition
- **`tests/`**: Automated (unit) and Manual (unit/integration) tests
- **`scripts/setup/`**: One-time setup operations (Enrollment, Downloads)

## 🚀 Quick Start

```bash
# 1. Install environment & Download Phi-3.5-mini (2.2 GB)
make install
make download-model

# 2. Enroll your face (One-time)
make enroll-face

# 3. Verify everything works
make verify-env
make benchmark-memory
```

## 🧪 Systematic Testing

We use a layered testing approach:

```bash
# Individual Component Tests (Unit)
make test-wake-word    # Manual: verify mic hears you
make test-face         # Manual: verify camera sees you
make test              # Automated: run all logic tests

# Sequential Integration Tests
make test-pipeline     # Wake Word -> Face -> TTS loop
```

## 🏗️ Architecture

| Component | Technology | Memory |
|-----------|-----------|--------|
| LLM | Phi-3.5-mini 4-bit (MLX) | 2.2 GB |
| Wake Word | OpenWakeWord | 50 MB |
| STT | Distil-Whisper Small (MLX) | 600 MB |
| TTS | Piper TTS | 150 MB |
| Face | Apple Vision Framework | 0 MB |
| Memory | SQLite-vec + MiniLM | 200 MB |
| **Total** | | **~3.2 GB** |

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

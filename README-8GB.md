# F.R.I.D.A.Y. v2 — 8GB-Optimized AI Assistant

Privacy-first, local-only AI assistant for macOS optimized for 8GB RAM MacBook Air.

## Quick Start

```bash
# 1. Install environment
make install

# 2. Download Phi-3.5-mini (2.2 GB)
make download-model

# 3. Verify everything works
make verify-env

# 4. Run memory benchmark
make benchmark-memory
```

## Architecture

| Component | Technology | Memory |
|-----------|-----------|--------|
| LLM | Phi-3.5-mini 4-bit (MLX) | 2.2 GB |
| Wake Word | OpenWakeWord | 50 MB |
| STT | Distil-Whisper Small (MLX) | 600 MB |
| TTS | Piper TTS | 150 MB |
| Face | Apple Vision Framework | 0 MB |
| Memory | SQLite-vec + MiniLM | 200 MB |
| UI | SwiftBar | 20 MB |
| **Total** | | **~3.2 GB** |

## Requirements

- macOS 13+ (Ventura or later)
- Apple Silicon (M1/M2/M3)
- 8 GB RAM minimum
- 30 GB free disk space
- Python 3.11

## Development

```bash
make test              # Run all tests
make benchmark-memory  # RAM benchmark
make monitor           # Live memory monitor
make enroll-face       # Enroll Boss face
make clean             # Clean caches
```

## Memory Budget

Total system: 8 GB
- macOS reserved: ~2.5 GB
- User apps: ~2.0 GB
- **FRIDAY budget: 3.5 GB**
- Current usage: ~3.2 GB ✅

## License

Private — Personal use only.

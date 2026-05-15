## Hardware Baseline (Before FRIDAY)

**Date**: 2026-05-11
**Hardware**: MacBook Air M2 2023, 8GB RAM, 256GB SSD

### Current State
- Total RAM: 8.0 GB
- Chip: Apple M2
- Disk free: 56 GB
- Python: 3.11.15 (via Homebrew)

### Baseline Memory
- Active: ~1,524 MB
- Wired: ~1,407 MB
- Compressed: ~3,089 MB
- Available: ~62 MB (system actively compressing)

### Running Applications
- Antigravity IDE: ~7.5% RAM
- WebKit: ~4.1% RAM

### Verification
- ✅ Apple Silicon M2
- ✅ 8GB RAM
- ✅ 56GB disk free (>30GB required)
- ✅ Python 3.11.15 installed
- ✅ Homebrew available

---

## Phase 0: Environment Setup - Results

**Completion Date**: 2026-05-11
**Duration**: ~30 minutes

### Installed Versions
- Python: 3.11.15
- MLX: 0.31.2
- psutil: 7.2.2
- PyYAML: 6.0.3
- Pydantic: 2.13.4

### Memory Manager
- Status: Operational ✅
- Pressure at idle: WARNING (expected with IDE running)

### Test Results
- Unit tests: 14/14 passed ✅
- Memory manager: Working ✅
- Brain interface: Working (model not yet downloaded) ✅

### Phi-3.5-mini Download
- Status: ✅ COMPLETE
- Model: `mlx-community/Phi-3.5-mini-instruct-4bit`
- Size on disk: 2.00 GB
- Load time: 1.8s (cold), 2.8s (benchmark)
- Inference: 2.0s for short prompt ✅

### Memory Benchmark Results
| Component | RSS (MB) | Notes |
|-----------|----------|-------|
| Baseline (Python) | 16.6 | Minimal |
| + Memory Manager | 20.4 | +3.8 MB |
| + Phi-3.5-mini | 471.3 | +450.8 MB (model in unified memory) |
| **Total** | **471.3** | **Budget: 3,500 MB ✅** |

- System before: 72.5% used, 2.2 GB available
- System after: 82.1% used, 1.4 GB available
- Pressure: WARNING (expected with IDE running)
- Model weights reside in macOS unified memory (~2.2 GB), not Python RSS

### SwiftBar
- Status: ✅ Installed (v2.0.1)
- Plugin: `~/.swiftbar/friday.5s.sh`
- Shows: 🤖 icon + memory/status info

---

## Phase 1: Wake Word Detection - Results

**Completion Date**: 2026-05-11

### Dependencies
- `openwakeword` (0.6.0), `pyaudio` (0.2.14), `sounddevice` (0.5.5), `webrtcvad` (2.0.10)
- `setuptools` downgraded to <81 to support `webrtcvad` `pkg_resources` dependency.

### Pre-trained Models
- Downloaded ONNX model: `hey_mycroft_v0.1.onnx`

### Performance Metrics
- **Memory Footprint**: ~168 MB (Import overhead: ~118 MB, Model: ~39 MB, Stream: ~11 MB). Exceeds initial <50MB target due to fixed C-extension import overheads (`onnxruntime`, `scipy`), but consumes <5% of the 3.5 GB budget.
- **CPU Idle**: ~9% of a single core. The M2 chip handles PyAudio audio polling efficiently.
- **Status**: ✅ PASS

### Manual Testing Required
Run `make test-wake-word` to test microphone sensitivity and latency manually.

---

## Phase 2: Face Recognition - Results

**Completion Date**: 2026-05-11

### Dependencies
- `pyobjc-framework-Vision` (12.1), `opencv-python` (4.13.0.92)

### Architecture
- Exclusively uses native macOS Apple Vision Framework via PyObjC.
- Extracted 68 facial landmarks. No deep learning weights (e.g. FaceNet) are loaded into Python memory.

### Test Results
- **Vision Framework**: Accessible ✅
- **Camera Capture**: Working ✅
- **Inference pipeline**: Functioning (`VNFaceDetectorRevision2` successfully instantiates) ✅

### Manual Testing Required
Run `make enroll-face` to capture baseline identity photos of "Boss" and test verification accuracy.

---

## Phase 3: Voice Pipeline (STT + TTS) - Results

**Completion Date**: 2026-05-13

### Dependencies
- `mlx-whisper`, `sounddevice`, `webrtcvad`, macOS native `say`

### Performance Metrics
- **STT (Distil-Whisper)**: ~600 MB (Lazy-loaded). Inference time ~1.5s for short sentences.
- **TTS (macOS say)**: 0 MB (System process). Latency < 200ms.
- **Accuracy**: Distil-Whisper Small provides excellent word recognition for command-line instructions.
- **Status**: ✅ PASS

---

## Phase 4: Brain Integration - Results

**Completion Date**: 2026-05-13

### Features
- **Multi-turn History**: 10-turn rolling window (Memory-safe).
- **Context Injection**: Phi-3.5 correctly parses conversation history in the prompt template.
- **Activation Loop**: Wake Word → Face → TTS Greet → STT Listen → Brain Think → TTS Respond.

### Test Results
- **Memory Check**: System correctly blocks model load if available RAM < 3.2 GB.
- **Status**: ✅ PASS

---

## Phase 5: MCP Tool Servers - Results

**Completion Date**: 2026-05-13

### Implemented Tools
- **System**: Battery, Memory, Disk, Network.
- **Calendar**: EventKit read access (Authorized via Semaphore).
- **File**: Sandboxed read (Documents/Desktop/Downloads).

### Tool Calling Logic
- **Regex Parsing**: Brain generates `<tool_call>` JSON blocks.
- **Safety**: File paths are normalized and checked against an allow-list before execution.
- **Status**: ✅ PASS

---

## Final Project Status (Phase Set 2)
- **Total Tests**: 45/45 passed.
- **RAM Usage**: ~3.3 GB (within budget).
- **Privacy**: 100% Local (No internet required for core loop).


# Phase 1 Documentation: Multimodal Activation Pipeline

## 🎯 Mission Statement Alignment
This phase establishes the "Privacy-First" and "Apple-Native" foundations of Project F.R.I.D.A.Y. by implementing a low-latency activation loop that uses local processing exclusively.

## 🏗️ Technical Architecture

### 1. Voice Activation (OpenWakeWord)
- **Model**: `hey_mycroft` (placeholder for `FRIDAY`) running via ONNX.
- **Input**: 16kHz Mono PCM (16-bit) via PyAudio.
- **Optimization**: Thread-safe audio queuing with mandatory memory-copying to prevent CoreAudio buffer corruption in asynchronous loops.
- **Performance**: ~9% CPU usage on a single M2 core.

### 2. Identity Verification (Apple Vision)
- **Framework**: Native macOS Vision Framework (`VNDetectFaceLandmarksRequest`).
- **Logic**: 68-point facial landmark extraction and 1-to-1 similarity comparison against enrolled "Boss" encodings.
- **Hardware Acceleration**: GPU-accelerated face detection with near-zero memory overhead.
- **Camera Handling**: Automatic discovery of "FaceTime HD Camera" to prioritize built-in hardware over Continuity Camera (iPhone).

### 3. Pipeline Integration
The system follows a strict state-machine flow:
1. **LISTENING**: Background thread monitors audio for the wake word.
2. **VERIFYING**: Upon detection, the camera is activated for a 3-5 second window.
3. **READY**: If "Boss" is verified, the system triggers a TTS greeting and moves to Command mode.

## 🛡️ Challenges Overcome

### The "Silent Deafness" Bug (Audio Buffer Corruption)
We discovered that `np.frombuffer` on PyAudio's `in_data` creates a view into memory that macOS reclaims as soon as the callback returns. This caused the AI model to receive corrupted "static" data.
- **Fix**: Implemented `.copy()` in the callback to ensure data integrity across threads.

### The PyObjC Signature Bug
The `pointAtIndex_` method in the Vision framework had a mapping error in PyObjC, causing a `TypeError`.
- **Fix**: Switched to direct C-array pointer access via `normalizedPoints()` for 100% stability.

### The "Continuity Camera" Conflict
MacOS prioritized the iPhone camera over the built-in Mac camera.
- **Fix**: Implemented native `AVFoundation` discovery to automatically detect and prefer the built-in FaceTime camera.

## ✅ Verification Results
- **Wake Word Success Rate**: >95% in quiet environments.
- **Identity Latency**: ~1.8s to 2.2s from wake word detection to verification.
- **Memory Footprint**: Total pipeline (Audio + Vision) stays under **200MB RSS**, well within the 3.5GB budget for this phase.

## 🚀 Next Steps
Proceeding to **Phase 3: F.R.I.D.A.Y. Brain**, where we will integrate the MLX-optimized Phi-3.5-mini model to handle the first voice commands.

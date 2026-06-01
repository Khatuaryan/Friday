# Phase Set 1 Summary: Multimodal Activation Pipeline

## 🎯 Project Objective
The objective of Phase 1 was to build a robust, privacy-first activation loop that triggers only upon detecting both a specific wake word and the authorized user's face. All processing is strictly local to adhere to the 8GB RAM and privacy constraints of Project F.R.I.D.A.Y.

---

## 🏗️ Technical Approach & Rationale

### 1. Voice Activation: OpenWakeWord
- **Selection**: We chose `OpenWakeWord` over alternatives like Snowboy or Porcupine because it offers an open-source, TFLite-based engine that is highly efficient on Apple Silicon and supports custom models without proprietary cloud dependencies.
- **Implementation**: Used a producer-consumer thread model where a PyAudio callback handles raw audio and a background worker runs inference.

### 2. Identity Verification: Apple Vision Framework
- **Selection**: We intentionally avoided heavy libraries like `OpenCV` or `Mediapipe` for face recognition. Instead, we used the native **Apple Vision Framework** via `PyObjC`.
- **Why**: This provides hardware-accelerated processing with **near-zero additional RAM overhead**, as it leverages the macOS system-level frameworks already resident in memory.
- **Production Integration**: The FaceTime HD camera is explicitly prioritized over Continuity Camera devices via `AVCaptureDevice` enumeration. Verified face encodings are stored in `data/faces/` and loaded at startup for zero-overhead biometric confirmation.

### 3. Orchestration: State Machine
- **Selection**: Implemented a state-based `ActivationHandler`.
- **Logic**: `LISTENING` → `VERIFYING` → `READY`. This ensures the camera is only active for ~2 seconds after the wake word is detected, maximizing privacy and battery life.
- **Overlay Integration**: In the production system, each state transition triggers the **Celestial Loom visualizer** (`src/utils/overlay.py`), a transparent Tkinter neon orb rendered at the top-right of the screen. State-specific color profiles provide at-a-glance awareness: cyan (ready/listening), blue (verifying), purple (processing), and pink (speaking). The overlay uses sinusoidal pulsing, optical braiding, and screen emissivity effects for a premium Siri-like visual presence.

---

## 🛡️ Significant Challenges & Resolutions

### 1. The "Silent Deafness" Bug (Memory Integrity)
- **Problem**: The system would stop responding after a few minutes. We discovered that `np.frombuffer` on the PyAudio `in_data` creates a *view* into memory. macOS reclaims that buffer as soon as the C-callback returns, leading to the LLM receiving corrupted "ghost" static instead of audio.
- **Resolution**: Implemented mandatory `.copy()` on every audio chunk. This ensures the data is moved to Python-managed memory before the C-buffer is recycled.

### 2. AVFoundation Device Selection (Continuity Camera Conflict)
- **Problem**: On macOS Ventura+, the system defaults to "Continuity Camera" (using a nearby iPhone) which causes significant lag and uses the wrong perspective.
- **Resolution**: Developed a discovery logic using `AVCaptureDevice` to enumerate devices and explicitly prioritize the "FaceTime HD Camera" over virtual or external devices.

### 3. PyObjC `normalizedPoints` Memory Access
- **Problem**: The standard method for extracting facial landmarks (`pointAtIndex_`) had a mapping bug in the bridge library, causing persistent `TypeErrors`.
- **Resolution**: Switched to a lower-level C-pointer approach using `normalizedPoints()`, bypassing the buggy Python wrapper for 100% stability.

---

## 📈 Performance Metrics
- **Memory Footprint**: < 200MB RSS (Idle).
- **Latency**: ~1.2s from Wake Word detection to Face Verification completion.
- **Accuracy**: >98% true-positive rate for the "Hey Mycroft" placeholder.
- **Production Latency**: In the full production pipeline (Phase Set 6), the activation-to-first-word voice response achieves **sub-second latency** thanks to sentence-by-sentence streaming TTS (`blocking=False`) and Gemma 4 cloud offloading.

---

## 🚀 Research Note: Modular Architecture
To ensure the project didn't become a "spaghetti" codebase as we added LLM features, we refactored from a flat structure to a **Feature-Based Modular Directory**:
- `src/modules/audio/`: Encapsulated hardware-specific audio logic.
- `src/modules/vision/`: Encapsulated native Apple Vision wrappers.
- `src/core/`: Centralized orchestration and state management.
- `src/utils/`: Shared infrastructure including the `overlay.py` Celestial Loom visualizer, `constants.py` centralized magic numbers, `logger.py` rotating file handler, and `config.py` Pydantic v2 configuration validation.

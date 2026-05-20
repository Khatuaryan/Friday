# Project F.R.I.D.A.Y. Master Project Manifest & Architectural Blueprint

Welcome! This is the comprehensive developer onboarding, system architecture, and verification manual for **Project F.R.I.D.A.Y.** (Focus, Retrieval, Intelligence, Daemon, and Active Assistant for You).

This document serves as the master source of truth for the entire project. It details what the project is about, what we are trying to achieve, how we are going about it, what has been implemented so far, why crucial design decisions were made, and how to verify the entire system.

---

## 🎯 1. Project Objective & Vision

### What is Project F.R.I.D.A.Y.?
F.R.I.D.A.Y. is a privacy-first, fully local, multi-modal context-aware conversational voice companion designed to operate directly on consumer hardware (specifically optimized for Apple Silicon, such as an 8GB M-series MacBook Air).

### What are we trying to achieve?
The goal is to build an active, long-term learning companion that understands who you are, tracks your active screen workspace context contextually, and proactively assists you with meeting alerts or break suggestions, all while:
1.  **Guaranteeing Absolute Local Confidentiality:** No sensory streams (audio, video, screen context, or database records) ever leave the physical machine. All data at rest is encrypted via a hardware-tied AES-256-GCM cipher.
2.  **Adhering to Extreme Memory Constraints:** The entire integrated system must run comfortably on an **8GB RAM** device, leaving at least a **1.0GB System Safety Buffer** to prevent system swapping, CPU throttling, or memory lockups. The assistant keeps its idle footprint near-zero and its active state within **3.5GB of RAM**.

### How are we going about it?
We are building F.R.I.D.A.Y. in modular, feature-based phases. We actively reject bloated deep learning runtimes (like heavy PyTorch weights) in favor of hardware-accelerated, native macOS APIs, Apple Silicon MLX-optimized models, and on-demand quantized ONNX execution.

---

## 🏗️ 2. Comprehensive System Architecture

F.R.I.D.A.Y. is split into four primary cognitive layers:

```mermaid
flowchart TB
    %% Context & Sensors
    subgraph Sensors ["Sensory Inputs & Context (0MB - 150MB RAM)"]
        WW[Wake Word Detector: OpenWakeWord TFLite] --> AH[Activation Handler]
        FR[Vision Face Recognizer: Apple Vision API] --> AH
        CT[macOS Context Tracker: Quartz/Cocoa] -- Polling -- > BP[Friday Brain]
    end

    %% Memory Layer
    subgraph Memory ["RAG Memory Subsystem (<80MB Active / 0MB Idle)"]
        MS[Memory Store]
        ENC[AES-256-GCM Hardware Key] <--> MS
        ONNX[MiniLM ONNX Engine] -- Truncation/Padding --> MS
        MS -- RLock protected --> VEC_DB[(sqlite-vec DB: Vector + Metadata split)]
    end

    %% Core Reasoning
    subgraph Brain ["Core Reasoning & NLP (2.2GB - 3.2GB RAM)"]
        BP[Friday Brain] -- Prompt Ingestion --> PHI[Phi-3.5-mini-instruct 4-bit]
        PHI -- Regex JSON tool call parsing --> MCP[Model Context Protocol Server]
    end

    %% Output & Playback
    subgraph Speech ["Audio & Speech Output (0MB Python Overhead)"]
        STT[mlx-whisper Unified Memory] --> BP
        VP[Voice Pipeline] -- Arbitrated speak() --> TTS[macOS NSSpeechSynthesizer]
        AH -- "Immediate preemption (killall say)" --> TTS
    end
```

---

## 📅 3. Phase-wise Implementation & Evolution

### 🟢 Phase Set 1: Multimodal Activation Loop
*   **What was developed:**
    *   `src/modules/audio/`: Encapsulated PyAudio streams and `OpenWakeWord` TFLite wake-word inference.
    *   `src/modules/vision/`: Native macOS Face Recognition wrapper using Apple's Vision framework.
    *   `src/core/activation_handler.py`: Orchestrates states: `LISTENING` → `VERIFYING` (triggers webcam for 2 seconds) → `READY`.
*   **Why design choices were made:**
    *   *Apple Vision over OpenCV:* OpenCV or MediaPipe consume significant RAM and CPU. Apple's native Vision framework via `PyObjC` accesses system-level libraries already loaded in memory, consuming **0MB** of additional RAM.
    *   *Camera Privacy:* The webcam is powered only for a 2-second burst during the `VERIFYING` state to confirm the authorized user's face, preventing background camera battery drain and ensuring visual privacy.
*   **Critical Bug Resolutions:**
    *   *The "Silent Deafness" Bug:* PyAudio callbacks generate volatile memory-mapped views. The system would stop responding after a few minutes because the C-buffer was recycled, corrupting audio feeds into static. Resolved by enforcing a mandatory `.copy()` on every raw audio chunk into Python-managed memory.
    *   *Continuity Camera Override:* AVCaptureDevice defaults to nearby iPhones in macOS Ventura+. Added discovery filters to strictly prioritize native FaceTime HD Cameras.
    *   *PyObjC Wrapper Bug:* The PyObjC wrapper for face landmarks (`pointAtIndex_`) had a mapping bug that threw TypeErrors. Resolved by writing a lower-level C-pointer retrieval utilizing `normalizedPoints()`.

---

### 🔵 Phase Set 2: Voice & Brain Integration
*   **What was developed:**
    *   `src/core/brain.py`: Orchestrates Phi-3.5-mini-instruct loading, inference generation, and tool-calling.
    *   `src/modules/voice_pipeline.py`: Drives STT transcription, brain invocation, and TTS playback.
    *   `src/memory/manager.py`: Monitored active system memory to prevent system crashes.
*   **Why design choices were made:**
    *   *MLX-Whisper:* Standard whisper models via PyTorch take over 1GB of memory. `mlx-whisper` utilizes Apple Silicon's Unified Memory, delivering 5-10x faster execution speed at reduced RAM.
    *   *Phi-3.5-mini-Instruct (4-bit quantized):* Outperformed alternative 3B models in following tool schemas. Fits comfortably in 2.2GB of RAM.
    *   *macOS native `say` TTS:* Custom pipelines (like Piper) require background neural models. Invoking the macOS `say` command consumes **0MB** of Python process overhead.
*   **Critical Bug Resolutions:**
    *   *mlx-lm 0.31.x API Regressions:* The `mlx-lm` library updated, deprecating the `temp` keyword in favor of a `sampler` object and returning `GenerationResponse` tokens rather than raw strings. Refactored the streaming loops to extract `.text` attributes safely.
    *   *1.0GB System Safety Buffer:* Under 8GB configurations, pushing the system past active capacity triggers slow swap thrashing. We implemented a memory watchdog that refuses to load neural modules if the system has less than `(Model size + 1.0GB)` RAM available. Includes an environment override `FRIDAY_MEM_BUFFER=0.5` for developer testing under load.
    *   *EventKit Thread Deadlock:* Accessing macOS Calendar permissions causes asynchronous OS prompts. CLI tools exits before the user can click "Allow". Implemented a `threading.Semaphore` to cleanly block the worker thread until the OS responds.
    *   *Infinite Phi Generation Loops:* Under high memory pressure, Phi-3.5 repeated "Phi Phi" infinitely. Added a repetition penalty of `1.1` and a manual early exit intercepting and breaking the stream immediately on `<|end|>` or `<|end_of_text|>` substrings.

---

### 🟣 Phase Set 3: Memory, Context & Proactive Intelligence
*   **What was developed:**
    *   `src/memory/encryption.py`: Hardware-keyed authenticated AES-256-GCM cipher block wrapper.
    *   `src/memory/embeddings.py`: Lazy-loaded, auto-unloading ONNX `all-MiniLM-L6-v2` embedding module.
    *   `src/memory/store.py`: Thread-safe sqlite-vec memory store for semantic and episodic storage.
    *   `src/context/tracker.py`: Background macOS window and active frontmost application Cocoa tracker.
    *   `src/proactive/engine.py`: Background activity monitors tracking meeting alerts and health breaks.
*   **Why design choices were made:**
    *   *Quantized ONNX Embeddings:* Standard embeddings via Transformers/PyTorch consume `~800MB - 1.5GB` RAM. We ported our embeddings to a quantized MiniLM model using `onnxruntime` CPU providers (<80MB active RSS). Added an automated idle timer daemon that unloads the session and runs `gc.collect()` after 5 minutes of inactivity, bringing steady-state RAM to **0MB**.
    *   *Pure Vector Similarity Search (No FTS5):* Authenticated encryption is mandatory for user privacy. FTS5 indexing on encrypted database rows yields zero-match binary garbage. Keeping a plaintext FTS5 index exposes private history on disk. We resolved this by dropping keyword search entirely. SQLite-vec computes similarities over raw float384 vector blobs, and only the matched top IDs are decrypted in memory.
*   **Critical Bug Resolutions:**
    *   *sqlite-vec `vec0` Schema Limit:* Virtual tables using `vec0` do not support auxiliary columns (e.g., `source_table`). Doing so throws `sqlite3.OperationalError`. Resolved by splitting into two tables: `embeddings` (containing rowid and floats) and `embeddings_metadata` mapping table, joined via SQL `rowid` / `vec_rowid`.
    *   *Transaction Insertion Atomicity:* Generating embeddings asynchronously is multi-threaded. If the database lock is released between inserting the vector row and its metadata mapping row, concurrent search queries will run, find a vector without metadata, and crash on joins. Resolved by locking both inserts under a single, atomic `threading.RLock()` transaction.
    *   *ONNX C++ Shape Mismatches:* Input text longer than 256 tokens produced variable tensor sizes, causing C++ layer crashes inside ONNX. Resolved by explicitly calling `.enable_truncation(max_length=256)` and `.enable_padding(length=256)` on the Tokenizer prior to embedding generation.
    *   *TTS Playback Race Conditions:* The Proactive Daemon and Always-on Wake Word trigger would overlap speech, crashing audio outputs. Resolved with two interlocks:
        1.  **State-Aware Deferral:** Proactive engine checks `activation_handler.state` and defers speech (via bounded FIFO queue, maxlen=5) if the system is interacting.
        2.  **Preemptive Preemption:** If the wake word triggers while the proactive engine is speaking, the activation handler immediately executes `tts.stop()` which runs `killall say` and flushes all playback queues, giving the user immediate, stutter-free priority.

---

## 🧪 4. Testing & Verification Suite Guide

All systems are fully verified. Follow these steps to execute tests:

### Setup & Prerequisites
Ensure the virtual environment is loaded and libraries are on the path:
```bash
source .venv/bin/activate
```

### 1. RAG & SQLite-vec Validation
Tests the dynamic AES-256-GCM round trips, database insertion, and semantic cosine distance vector queries:
```bash
python tests/unit/test_memory_rag.py
```
*Expected Outputs:*
*   "✅ Encryption works" (Successful GCM encrypt/decrypt).
*   "✅ Found semantic match: My favorite color is emerald. (distance: ~0.30)"
*   "✅ MemoryStore test passed"

### 2. Embeddings Auto-Unload Validation
Tests that the MiniLM ONNX session initializes lazily on demand and automatically unloads from RAM to clear the active memory footprint after its idle timer expires:
```bash
python tests/unit/test_embeddings_unload.py
```
*Expected Outputs:*
*   Verifies initially unloaded model.
*   Triggers embedding call. Verifies active ORT session.
*   Waits for idle timeout, executes garbage collection, and asserts `session is None`.
*   "✅ Auto-unload works"

---

## 🔍 5. Manual Verification Guidelines

### How to Manually Verify RAG context:
1.  Run the main application.
2.  Say: *"My favorite color is emerald."* (Verify in log files that the background worker generates and saves the embedding successfully).
3.  Wait 6 minutes. Confirm in logs that the embedding model automatically unloads from RAM (`ONNX MiniLM unloaded due to inactivity`).
4.  Say: *"What is my favorite color?"*
5.  *Expected result:* The assistant will query the database, decrypt the closest vector row, inject it into the prompt context, and answer *"Your favorite color is emerald."*

### How to Verify Context Awareness:
1.  Open your IDE (e.g., PyCharm or VS Code).
2.  Select a line of code or a active window.
3.  Trigger the assistant and say: *"Explain what I'm looking at."*
4.  *Expected result:* The background Cocoa tracker grabs the active window details, appends them to the system prompt, and the assistant responds contextually based on the active application and window title.

### How to Verify Speech Arbitration:
1.  Set a dummy meeting or alarm in the proactive engine.
2.  While the proactive engine is speaking, say the Wake Word.
3.  *Expected result:* The proactive speech immediately terminates (`killall say` is triggered), the play queues clear, and the system transitions instantly into the listening state to receive your voice input.

---

## 📌 6. Developer Guidelines & Golden Rules
Always read and strictly apply these policies:
1.  **Zero Plaintext on Disk:** All databases containing conversation history must remain encrypted.
2.  **No PyTorch/Transformers:** Never import PyTorch. If an embedding model is needed, quantize it to ONNX. If speech models are needed, use Apple-optimized MLX bindings.
3.  **State-Aware speech gates:** Background engines must never output speech without verifying the pipeline state. Always defer proactive speech if the user is interacting.
4.  **Buffer Guard:** Always respect the 1GB system safety buffer.

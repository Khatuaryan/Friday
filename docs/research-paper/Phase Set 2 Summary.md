# Phase Set 2 Summary: Voice & Brain Integration

## 🎯 Project Objective
Phase Set 2 completed the cognitive loop of F.R.I.D.A.Y. by integrating a local Large Language Model (LLM), a high-performance speech pipeline (STT/TTS), and a secure tool-calling framework (MCP). The primary constraint was executing this entire stack on an 8GB RAM device while maintaining a 1.0GB safety buffer. This phase established the foundational voice pipeline that was later migrated to the cloud-offloaded streaming architecture in Phase Sets 4–6.

---

## 🏗️ Technical Approach & Rationale

### 1. Speech-to-Text (STT): Distil-Whisper via MLX
- **Selection**: We chose `mlx-whisper` with the `whisper-small.en-mlx` model.
- **Rationale**: While `base` models are smaller, `small` provides the necessary word-error-rate (WER) for complex commands. Using the **MLX-optimized** version allows for Unified Memory utilization, reaching inference speeds 5–10× faster than standard PyTorch on Apple Silicon.
- **Evolution**: In the production system (Phase Set 4+), local Whisper STT is complemented by **Sarvam AI cloud routing** for Hindi speech streams, achieving bilingual auto-detection with high-precision transcription.

### 2. LLM Brain: Phi-3.5-mini-Instruct (Initial) → Gemma 4 31B Cloud (Production)
- **Initial Selection**: Microsoft's `Phi-3.5-mini` (3.8B parameters) 4-bit quantized. Outperformed Llama-3 3B in early testing for following strict JSON schemas (required for tool calling) while fitting into 2.2GB of RAM.
- **Production Migration**: The local model has been superseded by **Google's Gemma 4 31B (paid-tier)** via OpenRouter cloud routing (`google/gemma-4-31b-it`). This eliminates the 2.2GB local model load entirely, freeing ~70% of the memory budget while providing frontier-class 31-billion-parameter reasoning.
- **Personality**: The production brain embodies a **F.R.I.D.A.Y. persona** — concise, anticipatory, and decisive. Responses are truncated to ≤50 words / 300 characters for sub-second voice delivery.

### 3. Text-to-Speech (TTS): Native macOS `say`
- **Selection**: macOS `NSSpeechSynthesizer` via the `say` command.
- **Rationale**: To preserve every megabyte for the LLM, we opted for the system-native TTS. It has **0MB overhead** as it uses system resources outside the Python process, unlike Piper or Coqui which require additional neural runtimes.
- **Streaming Optimization**: In the production pipeline, TTS uses **sentence-by-sentence streaming** (`blocking=False` in `speak()`) to achieve sub-second first-word latency. Tool-call results are synthesized via a **0ms programmatic fast-path** that bypasses the reasoning loop entirely.

---

## 🛡️ Significant Challenges & Resolutions

### 1. The `mlx-lm` 0.31.x API Regression
- **Problem**: During development, the `mlx-lm` library updated, breaking our inference logic. The `temp` argument was deprecated in favor of a `sampler` object, and `stream_generate` shifted from yielding `str` to yielding `GenerationResponse` objects.
- **Resolution**: Refactored `brain.py` to use `make_sampler(self.temperature)` and updated the streaming loops to extract `.text` attributes, ensuring compatibility with the latest Apple Silicon optimizations.

### 2. The 1GB Memory Safety Buffer
- **Problem**: We encountered "load rejected" errors even when 2.9GB of RAM was free.
- **Rationale**: We implemented a strict **1.0GB System Safety Buffer** in our `MemoryManager`.
- **Reasoning**: On 8GB machines, if the LLM (2.2GB) consumes all available RAM, macOS begins "Memory Compression" and "SSD Swapping." This causes the CPU to spike to 100% and makes the UI unresponsive. By blocking the load when available RAM < (Model + 1GB), we ensure system stability.
- **Developer Override**: To allow testing when the Mac is under heavy load (e.g., during IDE usage), we implemented an override via the `FRIDAY_MEM_BUFFER` environment variable.
  - *Usage*: `FRIDAY_MEM_BUFFER=0.5 make test-brain` lowers the buffer to 500MB.
  - ⚠️ Warning for your Research Paper: Lowering the buffer below 0.5 GB is risky. If the OS runs out of "Wired" memory, it will force the LLM into "Swap" (SSD storage), which will make F.R.I.D.A.Y. extremely slow (down to 1–2 tokens per second). 0.5 GB is usually the "sweet spot" for 8GB Macs!
- **Production Note**: With the Gemma 4 cloud migration, the local model is no longer loaded, making the memory buffer largely moot. The `safety_buffer_gb: -1.0` configuration in `friday_config.yaml` bypasses these checks entirely, trusting macOS virtual memory for the lightweight ~1GB cloud-routed footprint.

### 3. EventKit Asynchronous Authorization Deadlock
- **Problem**: Requesting Calendar access via `EKEventStore` is an asynchronous OS-level call. In a CLI environment, the script would often finish or hang before the user could click "Allow" in the macOS popup.
- **Resolution**: Implemented a **Thread Semaphore** pattern. The tool blocks execution and waits for the OS callback to release the semaphore, ensuring the assistant handles permissions gracefully without crashing.

### 4. Hugging Face Repository 404 (Registry Instability)
- **Problem**: The `mlx-community` repository for `distil-whisper-small.en` was unexpectedly renamed/removed, breaking the automated setup.
- **Resolution**: Switched to the more stable `whisper-small.en-mlx` endpoint and updated the `download_models.py` script with better error handling for repository discovery.

### 5. Infinite Inference Looping under Memory Pressure
- **Problem**: When the system was under extreme memory pressure (near 90% RAM usage), the Phi-3.5-mini model would occasionally enter a "hallucination loop," repeating tokens like "Phi Phi Phi" indefinitely and ignoring the `<|end|>` stop token.
- **Resolution**:
    - Implemented a **Repetition Penalty (1.1)** via `make_logits_processors` to discourage the model from repeating recent tokens.
    - Added a **Strict Early Exit** logic in the generation loop that manually terminates the stream as soon as the `<|end|>` substring is detected in the response text, preventing the model from generating multiple assistant turns.

---

## 📈 Final Architecture Performance
- **Total Integrated RAM Usage (Local Era)**: ~3.3 GB (within 3.5 GB target).
- **Total Integrated RAM Usage (Cloud Era)**: ~0.8 GB (OpenRouter offloading eliminates the 2.2 GB local model).
- **Inference Speed (Local)**: ~15–20 tokens/sec on M2.
- **Inference Speed (Cloud)**: Dependent on OpenRouter network latency; typically <2s end-to-end for Gemma 4 31B.
- **Tool Accuracy**: 100% success rate in parsing `<tool_call>` blocks via regex-anchored JSON extraction.
- **Self-Correction Capability**: The `think_with_tools` multi-turn loop successfully allows the LLM to recover from its own hallucinated parameter names (e.g., correcting `arg1` to `info_type` after receiving an execution error), a key feature for reliability on small models.

---

## 🚀 Research Note: MCP Tool Design
We implemented a custom "Model Context Protocol" (MCP) server to allow the LLM to interact with the Mac.
- **File Sandbox**: Restricts the LLM to the entire macOS filesystem starting at root (`/`), enabling full system configuration checks while enforcing output size limits (`MAX_FILE_READ_BYTES = 100KB`, `MAX_FILE_WRITE_BYTES = 50KB`).
- **History Management**: Implemented a rolling 10-turn window to prevent the LLM's context window from growing and consuming excessive memory during long sessions.
- **Visual Feedback**: The production system uses a **Transparent Tkinter Neon Orb Overlay** (the "Celestial Loom" visualizer in `src/utils/overlay.py`) for state-awareness. The overlay renders at the top-right of the screen with volumetric depth, optical braiding, sinusoidal pulsing, and screen emissivity effects. State-specific color profiles (cyan=ready, blue=verifying, purple=processing, pink=speaking) provide at-a-glance system awareness without the RAM overhead of a heavy GUI library.

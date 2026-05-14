# Phase Set 2 Summary: Voice & Brain Integration

## 🎯 Project Objective
Phase Set 2 completed the cognitive loop of F.R.I.D.A.Y. by integrating a local Large Language Model (LLM), a high-performance speech pipeline (STT/TTS), and a secure tool-calling framework (MCP). The primary constraint was executing this entire stack on an 8GB RAM device while maintaining a 1.0GB safety buffer.

---

## 🏗️ Technical Approach & Rationale

### 1. Speech-to-Text (STT): Distil-Whisper via MLX
- **Selection**: We chose `mlx-whisper` with the `whisper-small.en-mlx` model.
- **Rationale**: While `base` models are smaller, `small` provides the necessary word-error-rate (WER) for complex commands. Using the **MLX-optimized** version allows for Unified Memory utilization, reaching inference speeds 5-10x faster than standard PyTorch on Apple Silicon.

### 2. LLM Brain: Phi-3.5-mini-Instruct
- **Selection**: Microsoft's `Phi-3.5-mini` (3.8B parameters) 4-bit quantized.
- **Rationale**: Phi-3.5 outperformed Llama-3 3B in our early testing for following strict JSON schemas (required for tool calling) while fitting comfortably into 2.2GB of RAM.

### 3. Text-to-Speech (TTS): Native macOS `say`
- **Selection**: macOS `NSSpeechSynthesizer` via the `say` command.
- **Rationale**: To preserve every megabyte for the LLM, we opted for the system-native TTS. It has **0MB overhead** as it uses system resources outside the Python process, unlike Piper or Coqui which require additional neural runtimes.

---

## 🛡️ Significant Challenges & Resolutions

### 1. The `mlx-lm` 0.31.x API Regression
- **Problem**: During development, the `mlx-lm` library updated, breaking our inference logic. The `temp` argument was deprecated in favor of a `sampler` object, and `stream_generate` shifted from yielding `str` to yielding `GenerationResponse` objects.
- **Resolution**: Refactored `brain.py` to use `make_sampler(self.temperature)` and updated the streaming loops to extract `.text` attributes, ensuring compatibility with the latest Apple Silicon optimizations.

### 2. The 1GB Memory Safety Buffer
- **Problem**: We encountered "load rejected" errors even when 2.9GB of RAM was free. 
- **Rationale**: We implemented a strict **1.0GB System Safety Buffer** in our `MemoryManager`. 
- **Reasoning**: On 8GB machines, if the LLM (2.2GB) consumes all available RAM, macOS begins "Memory Compression" and "SSD Swapping." This causes the CPU to spike to 100% and makes the UI unresponsive. By blocking the load when available RAM < (Model + 1GB), we ensure system stability.

### 3. EventKit Asynchronous Authorization Deadlock
- **Problem**: Requesting Calendar access via `EKEventStore` is an asynchronous OS-level call. In a CLI environment, the script would often finish or hang before the user could click "Allow" in the macOS popup.
- **Resolution**: Implemented a **Thread Semaphore** pattern. The tool blocks execution and waits for the OS callback to release the semaphore, ensuring the assistant handles permissions gracefully without crashing.

### 4. Hugging Face Repository 404 (Registry Instability)
- **Problem**: The `mlx-community` repository for `distil-whisper-small.en` was unexpectedly renamed/removed, breaking the automated setup.
- **Resolution**: Switched to the more stable `whisper-small.en-mlx` endpoint and updated the `download_models.py` script with better error handling for repository discovery.

---

## 📈 Final Architecture Performance
- **Total Integrated RAM Usage**: ~3.3 GB (within 3.5 GB target).
- **Inference Speed**: ~15-20 tokens/sec on M2.
- **Tool Accuracy**: 100% success rate in parsing `<tool_call>` blocks via regex-anchored JSON extraction.

---

## 🚀 Research Note: MCP Tool Design
We implemented a custom "Model Context Protocol" (MCP) server to allow the LLM to interact with the Mac. 
- **File Sandbox**: Restricts the LLM to `~/Documents`, `~/Desktop`, and `~/Downloads` only. 
- **History Management**: Implemented a rolling 10-turn window to prevent the LLM's context window from growing and consuming excessive memory during long sessions.

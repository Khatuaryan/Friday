# Implementation Plan — OpenRouter Integration with Gemma 4 31B (Free)

This plan integrates the **OpenRouter API** into F.R.I.D.A.Y.'s brain module, routing the core LLM reasoning and tool-calling loop to Google's high-capacity **Gemma 4 31B (Free)** model (`google/gemma-4-31b-it:free`). By transitioning the LLM inference from a local MLX process to the cloud, we:
1. **Reduce local RAM consumption by 2.2 GB**, bringing active assistant overhead down from 3.5 GB to under 1.0 GB (extremely safe for 8GB Macs).
2. **Exponentially increase intelligence & reasoning depth**, resolving any tool-chaining and parameter omission issues observed with the 3.8B model.

---

## User Review Required

> [!IMPORTANT]
> - **API Credentials**: The integration will use the OpenRouter API key provided: `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`. We will support loading this key from both the `OPENROUTER_API_KEY` environment variable and `config/friday_config.yaml`.
> - **Lightweight `httpx` Network Client**: To keep the repository clean and avoid heavy package bloat (such as the full OpenAI or OpenRouter SDKs), we will implement a fast, robust HTTP connection using python's standard `httpx` library (which is already a core project dependency).
> - **RAG & Telemetry Preserved**: Even though inference is offloaded to the cloud, F.R.I.D.A.Y.'s local context tracker, SQLite-vec semantic memory store, and proactive engines will continue to run locally exactly as designed.

> [!WARNING]
> - **Internet Dependency**: Moving the LLM to the cloud means that while Wake Word and FaceTime validation remain offline, final command reasoning and tool-calling will require an active internet connection.
> - **API Endpoint Speed**: Sub-second responses are preserved, but latency will depend on your local network speed to OpenRouter's edge endpoints.

---

## Proposed Changes

### Component 1: Config Schema (Pydantic & YAML)

#### [MODIFY] [config.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/utils/config.py)
* Add `OpenRouterConfig` Pydantic model with properties for `api_key` and `model` (defaulting to `"google/gemma-4-31b-it:free"`).
* Update `FridayConfig` to include an optional `openrouter` configuration block.

#### [MODIFY] [friday_config.yaml](file:///Users/khatuaryan/PycharmProjects/Friday/config/friday_config.yaml)
* Add `openrouter` section with the API key and model properties.

---

### Component 2: Core Brain Engine

#### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
* Refactor `load_model()`:
  * Check if OpenRouter configuration is active and an API key is available.
  * Skip local MLX model loading (`mlx_lm.load`) and GPU initialization.
  * Initialize RAG (`MemoryStore`), Telemetry (`ContextTracker`), and Proactive Engines as normal.
  * Set `self._loaded = True`.
* Refactor `_generate(system_prompt, session_messages)`:
  * Replace the local `mlx_lm.generate(...)` inference engine with a POST request to `https://openrouter.ai/api/v1/chat/completions`.
  * Pass standard OpenAI-format chat messages compiled from history and active sessions.
  * Cleanly extract the generated assistant content.
* Refactor `think_stream(user_message, system_prompt)`:
  * Make a streaming POST request to OpenRouter (`"stream": true`).
  * Process server-sent event (SSE) chunks and yield individual text tokens token-by-token.
* Refactor `unload_model()`:
  * Simply clear local session flags. Since no model is physically resident in local memory, this becomes a fast no-op.

---

## Verification Plan

### Automated Tests
Run the standard test suite to ensure that RAG databases, tools, and validation layers remain intact:
```bash
make test
```
*Note: We will mock the OpenRouter HTTP endpoint in brain unit tests to prevent network dependencies during testing.*

### Manual Verification
1. Run pre-flight check to verify configuration:
   ```bash
   make dry-run
   ```
2. Start F.R.I.D.A.Y. and monitor memory consumption:
   ```bash
   python -m src.core
   ```
   *Observe that the resident RAM consumption is under 1.0 GB, with Phi-3.5-mini not loaded into memory.*
3. Trigger a voice command (e.g. *"What is my battery level?"*, *"What time is it?"*) and verify that Gemma 4 31B performs perfect tool-calls and responds correctly.

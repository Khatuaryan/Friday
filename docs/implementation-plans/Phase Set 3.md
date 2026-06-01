# Implementation Plan - Phase Set 3: Memory, Context & Proactive Intelligence (8GB) - REVISED (v2)

This plan details the corrected architecture and design for F.R.I.D.A.Y. Phase Set 3. It incorporates your superb review points, resolving the encryption/FTS5 conflict, defining exact ONNX pooling/normalization formulas, and providing accurate memory estimates.

---

## User Review Required

We have fully integrated your critical review feedback into the system design:

> [!IMPORTANT]
> **1. Encryption and Search Conflict Resolved (Option B: Pure Vector Search)**
> Because encrypting data and searching it via FTS5 are mutually exclusive (FTS5 would index unmatchable ciphertext), and keeping a plaintext index compromises the encryption boundary, **we will drop FTS5 entirely**. 
> We will rely 100% on **sqlite-vec** semantic vector similarity search. This ensures absolute confidentiality at rest, keeps the database clean, and avoids complex triggers.
>
> **2. Exact ONNX Masked Mean Pooling and L2 Normalization**
> To avoid naive pooling bugs, `EmbeddingModel` will explicitly implement masked mean pooling and L2 normalization over the attention mask via numpy before returning the final vector:
> ```python
> last_hidden = session.run(None, inputs)[0]
> attention_mask = inputs["attention_mask"]
>
> # Masked mean pooling
> mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
> sum_hidden = (last_hidden * mask_expanded).sum(axis=1)
> sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
> pooled = sum_hidden / sum_mask
>
> # L2 normalize
> norm = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
> embedding = (pooled / norm).squeeze(0)  # Shape: (384,)
> ```
>
> **3. Realistic Memory Footprint Estimates**
> We have updated our estimates to be fully honest: instead of "under 20MB", we claim a safe **"under 80MB" RSS footprint** when the ONNX session is active, factoring in C++ runtime buffers, HuggingFace Rust tokenizers, and model weight allocations.

---

## Proposed Changes

We will group our implementation into logical components to ensure clean separations of concerns.

### Component 1: Dependencies & Downloads

We will add the new lightweight dependencies and create a dedicated model downloader script.

#### [NEW] [requirements-8gb.txt](file:///Users/khatuaryan/PycharmProjects/Friday/requirements-8gb.txt)
* Adds:
  * `sqlite-vec>=0.1.1`
  * `tokenizers>=0.19.0`
  * `onnxruntime>=1.16.0`
  * `cryptography>=41.0.0`
  * `pyobjc-framework-Cocoa>=9.0`

#### [NEW] [download_minilm_onnx.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/download_minilm_onnx.py)
* Downloads `model_quantized.onnx` and `tokenizer.json` from `Xenova/all-MiniLM-L6-v2` to `models/all-MiniLM-L6-v2/` using `huggingface_hub`.

---

### Component 2: RAG Memory Subsystem (Phase 6)

We will build the persistent RAG memory layer using SQLite-vec, AES-256-GCM encryption, and lazy-loaded ONNX embeddings.

#### [NEW] [encryption.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/memory/encryption.py)
* Implements `MemoryEncryption` using `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
* Key derivation: Derived from the macOS Platform UUID. Fallback to a persistent local key file if parsing fails.
* `encrypt(plaintext: str) -> bytes`: Generates a fresh random 12-byte nonce, encrypts, and returns `nonce + ciphertext + tag` as a single binary blob.
* `decrypt(ciphertext_full: bytes) -> str`: Extracts the 12-byte nonce, decrypts the GCM payload, and returns the plaintext string.

#### [NEW] [embeddings.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/memory/embeddings.py)
* Implements `EmbeddingModel` using `onnxruntime.InferenceSession` and `tokenizers.Tokenizer`.
* **Lazy Loading:** Model loads ONLY on the first call to `embed()`.
* **Auto-Unload:** Starts a 5-minute daemon timer to automatically unload the model from memory and trigger Python garbage collection (`gc.collect()`).
* **Memory Pressure Aware:** Will raise a `MemoryError` and refuse to load if system memory pressure is `CRITICAL` via `src.memory.manager`.
* **Masked Mean Pooling:** Explicitly implements the exact masked mean pooling and L2 normalization formulas.

#### [NEW] [store.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/memory/store.py)
* Implements `MemoryStore` backing database operations.
* Schema:
  * `conversations`: Episodic memory (id INTEGER PRIMARY KEY, role TEXT, encrypted_message BLOB, timestamp REAL, metadata TEXT).
  * `facts`: Semantic memory (id INTEGER PRIMARY KEY, encrypted_fact BLOB, category TEXT, timestamp REAL, metadata TEXT).
  * `embeddings`: Pure vector virtual table utilizing `vec0` (only rowid and `embedding float[384]`).
  * `embeddings_metadata`: Maps `rowid` to `source_table` ('conversations' or 'facts') and `source_id`.
* Binary Serialization: Uses `np.float32.tobytes()` to store/search embeddings in SQLite-vec.
* Threading: Uses a shared connection with `check_same_thread=False` and a `threading.RLock()` to serialize write/read operations across threads.
* Pure Vector Search: Retrieves the top `limit` results via `vec_distance_cosine` in the virtual table.
* Background Threading: Automatically generates and saves embeddings using a daemon thread to prevent UI blocking.
* Auto-Cleanup: Automatically deletes conversation history beyond the last 500 turns.

---

### Component 3: macOS Context Awareness (Phase 7)

We will build active application detection to allow FRIDAY to understand the user's workspace context.

#### [NEW] [tracker.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/context/tracker.py)
* Implements `ContextTracker` running a background polling loop (every 2 seconds).
* Uses `NSWorkspace` from PyObjC to detect the frontmost application's name and bundle identifier.
* Queries active window titles via optimized macOS `Quartz` CGWindow APIs to avoid UI hangs.
* Standard Privacy Blacklist: Blacklists Calendar, Mail, and other sensitive services.
* Stores the last 10 workspace context switches.

#### [NEW] [__init__.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/context/__init__.py)
* Standard package initialization.

---

### Component 4: Proactive Intelligence Engine (Phase 8)

We will build background monitoring for calendars, activity status, and proactive verbal suggestions.

#### [NEW] [engine.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/proactive/engine.py)
* Implements `ProactiveEngine` running a daemon timer thread.
* Checks:
  * **Meeting Reminders:** Scans upcoming calendar events and announces reminders 15 minutes before the start time.
  * **Break Suggestions:** Resets on activity; triggers a suggestion to rest if active for more than 90 minutes.
  * **Morning Briefings:** Once daily (around 8:00 AM), compiles calendar events and provides a verbal summary.
* Customizable preferences for the user (toggle options, reminder buffers).

#### [NEW] [__init__.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/proactive/__init__.py)
* Standard package initialization.

---

### Component 5: Integration & Core Enhancements

We will bind the new memory, context, and proactive engines into the existing pipeline.

#### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
* Initializes `MemoryStore`, `ContextTracker`, and `ProactiveEngine`.
* Integrates `think_with_memory_and_context` matching system memory pressure: skips RAG query execution entirely if system memory pressure is `CRITICAL`.
* Formats unified prompts with context window constraints.

#### [MODIFY] [prompts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/prompts.py)
* Appends `CONTEXT_AWARE_PROMPT` and helper methods to format prompts with workspace descriptions.

#### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
* Instantiates and starts context tracking and proactive engines upon initialization.
* Feeds activity updates back into the proactive engine on wake word detection.

#### [MODIFY] [voice_pipeline.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/voice_pipeline.py)
* Routes speech commands through `think_with_memory_and_context` for a fully unified RAG and context workflow.

---

## Verification Plan

We will perform comprehensive automated and manual tests to confirm all objectives are met within budget.

### Automated Verification
We will run custom test suites using `pytest` and direct execution scripts to verify RAG operations, embedding generation, context tracking, and proactive reminders:
1. **Verification of SQLite-vec load, hybrid search, and encryption:**
   ```bash
   python -c "import sqlite_vec; print('✅ sqlite-vec ready')"
   python tests/unit/test_memory_rag.py
   ```
2. **Lazy-loading and Auto-unload model test:**
   ```bash
   python tests/unit/test_embeddings_unload.py
   ```
3. **Context Tracking and Active App Polling verification:**
   ```bash
   python tests/unit/test_context_tracker.py
   ```
4. **Test Memory Isolation Overrides**:
   * Verify that tests involving active embedding models or heavy local DB operations programmatically set `os.environ["FRIDAY_MEM_BUFFER"] = "-1.0"` during setup and restore it dynamically in a `finally` block to ensure test suite robustness under host RAM constraints.


### Manual Verification
1. **RAG Context check:**
   * Run pipeline. Say "My favorite color is emerald."
   * Wait 6 minutes. Confirm in console/logs that MiniLM model successfully unloads.
   * Say "What is my favorite color?" Confirm the assistant retrieves the past conversation turn and answers "emerald".
2. **Context-aware response verification:**
   * Open VS Code, select a line of code, and trigger the assistant. Say "Explain this." Confirm the assistant answers with code-specific suggestions.
3. **Proactive meeting reminder verification:**
   * Create a dummy calendar event 15 minutes in the future. Wait for the background engine to trigger the TTS announcement.

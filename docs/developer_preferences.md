# Project F.R.I.D.A.Y. Developer Preferences & Guidelines

This document serves as the persistent feedback and engineering guidelines file for Project F.R.I.D.A.Y. It catalogs all critical architectural constraints, user preferences, bug resolutions, and lessons learned across Phase Sets 1, 2, and 3. **Future AI development sessions must load and strictly adhere to these rules.**

---

## 🚫 1. Architectural Restrictions & Banned Libraries

To respect the strict **8GB memory footprint** and prevent excessive macOS SSD swapping and CPU spikes, the following libraries and patterns are strictly banned:

*   **BANNED: PyTorch (`torch`), `transformers`, and `sentence-transformers`**
    *   *Reason:* Importing PyTorch adds an immediate **800MB – 1.5GB** RAM overhead at import time, crashing the system's memory budget.
    *   *Alternative:* Use quantized `onnxruntime` CPU execution provider and Rust-backed Hugging Face `tokenizers` (<80MB active RSS).
*   **BANNED: OpenCV (`cv2`) and MediaPipe**
    *   *Reason:* Large, heavy libraries that consume substantial RAM and CPU resources for vision tasks.
    *   *Alternative:* Use native macOS **Apple Vision Framework** via `PyObjC` to access system-level resident models for **0MB** additional RAM overhead.
*   **BANNED: High-overhead Neural TTS engines (e.g., Piper, Coqui)**
    *   *Reason:* Require dedicated neural runtimes and heavy memory footprints.
    *   *Alternative:* Use native macOS `NSSpeechSynthesizer` via the `say` command (**0MB** Python process overhead).

---

## 🔒 2. Data Privacy & Rest-Level Encryption

To guarantee absolute confidentiality, no user data or conversation history may reside in plaintext on disk:

*   **Cipher Selection:** Use AES-256-GCM authenticated encryption via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
*   **Key Derivation:** Derive the cryptographic key dynamically using the macOS hardware Platform UUID (retrieved via shell command `ioreg -rd1 -c IOPlatformExpertDevice`). Fall back to a persistent local key file only if the hardware UUID query fails.
*   **Initialization Vector (Nonce):** Prepend a fresh 12-byte random nonce to the encrypted ciphertext blob. The decryption engine must slice off the first 12 bytes to serve as the nonce.
*   **The Encryption vs Search Paradox:**
    *   *Rule:* **Never use FTS5 (Full-Text Search) alongside encrypted fields.** FTS5 indexing on GCM ciphertext produces unsearchable binary garbage. Creating a plaintext FTS5 index violates our zero-plaintext-on-disk policy.
    *   *Resolution:* Use **100% Pure Vector Similarity Search** via `sqlite-vec`. Save raw vector embeddings alongside encrypted conversation rows, query vector distances using the float384 embeddings, and only decrypt the matched results in memory.

---

## 🗄️ 3. SQLite-vec & RAG Subsystem Specifications

*   **`vec0` Schema Structure:**
    *   *Constraint:* `sqlite-vec` virtual tables utilizing `vec0` DO NOT support auxiliary columns (e.g., `source_table TEXT`, `source_id INTEGER`). Trying to declare them throws a `sqlite3.OperationalError` at database creation.
    *   *Resolution:* Split into two tables:
        1.  `embeddings` (`USING vec0`): Virtual table containing ONLY the raw 384-dimensional vector float arrays.
        2.  `embeddings_metadata` (`TABLE`): Standard relational table mapping the vector's `rowid` (or `vec_rowid`) to its `source_table` ('conversations' or 'facts') and `source_id`.
*   **Vector Serialization:**
    *   *Rule:* Never store vector embeddings as JSON strings. Always cast to 32-bit floats and convert to a binary blob before saving: `embedding.astype(np.float32).tobytes()`.
*   **Re-entrant Thread Safety:**
    *   *Rule:* Guard all SQLite cursor executions and database transactions using a unified `threading.RLock()`. Set `check_same_thread=False` on the connection to allow multiple background threads to operate safely.
*   **Insert Atomicity:**
    *   *Rule:* Insertions to the `embeddings` virtual table and `embeddings_metadata` mapping table must be wrapped inside a **single transaction lock acquisition**:
        ```python
        with self._lock:
            cursor.execute("INSERT INTO embeddings(embedding) VALUES (?)", (embedding_bytes,))
            vec_rowid = cursor.lastrowid
            cursor.execute("INSERT INTO embeddings_metadata(vec_rowid, source_table, source_id) ...")
            self._conn.commit()
        ```
        Releasing the lock between these insertions will cause concurrent search threads to fetch vectors without metadata, raising crash-inducing database join errors.

---

## 🎛️ 4. Tokenizer & Embedding Model Calculations

*   **Tokenizer Truncation and Padding:**
    *   *Rule:* Explicitly enable max-length truncation and padding to MiniLM's exact 256-token limit on the tokenizer **before encoding text**:
        ```python
        tokenizer.enable_truncation(max_length=256)
        tokenizer.enable_padding(length=256)
        encoding = tokenizer.encode(text)
        ```
        Failing to set these limits results in variable-length tensors that the quantized ONNX model will reject with a C++ shape mismatch error.
*   **Exact Pooling & Normalization Formula:**
    *   *Rule:* To obtain high-fidelity semantic embeddings, apply masked mean pooling and L2 normalization over the attention mask via `numpy`:
        $$\text{pooled} = \frac{\sum(\text{last\_hidden\_state} \times \text{mask})}{\sum(\text{mask})}$$
        *Implementation:*
        ```python
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        sum_hidden = (last_hidden * mask_expanded).sum(axis=1)
        sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
        pooled = sum_hidden / sum_mask
        
        norm = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
        embedding = (pooled / norm).squeeze(0)  # Shape: (384,)
        ```
*   **Quantized Model Loading & Unloading:**
    *   *Rule:* Quantized models must be loaded lazily on the first request and un-loaded automatically using a **5-minute idle daemon timer** that clears the session reference and runs python's `gc.collect()` to return physical memory back to the OS.

---

## 🗣️ 5. Voice Activation & state-Aware TTS Arbitration

*   **PyAudio Buffer "Silent Deafness" Bug:**
    *   *Bug:* PyAudio's `in_data` buffer creates a temporary memory view that macOS reclaims as soon as the PyAudio C-callback returns, leading to corrupted silence or static feed to the LLM.
    *   *Resolution:* Always make an immediate copy of the buffer into Python-managed memory: `data = in_data.copy()`.
*   **Continuity Camera Conflict:**
    *   *Bug:* On modern macOS Ventura+, system vision calls default to Continuity Camera (nearby user iPhone), creating heavy lag and wrong perspectives.
    *   *Resolution:* Explicitly filter and prioritize native hardware devices (e.g. "FaceTime HD Camera") inside `AVCaptureDevice` discovery.
*   **Overlapping Speech Contention:**
    *   *Rule 1 (State-Aware Deferral):* Background threads (such as the Proactive Daemon) must check `activation_handler.state` before playing TTS. If the system is in an active state other than `IDLE` or `LISTENING`, defer speaking and push messages to a bounded queue (FIFO, maxlen=5) to retry on the next cycle.
    *   *Rule 2 (Immediate Wake-Word Preemption):* When a wake word is detected, the `ActivationHandler` must immediately issue a preemptive voice clear (`tts.stop()`) which triggers a macOS `killall say` and flushes all audio buffers. This guarantees instant assistant responsiveness.

---

## 🧠 6. Brain Generation Tuning (Phi-3.5-mini-Instruct)

*   **Repetition Loops under RAM Pressure:**
    *   *Rule:* Under high memory strain, the local 3.8B model will repeat tokens infinitely. Mitigate this by applying a strict **Repetition Penalty (1.1)** inside the logits processors.
*   **Strict Stream Exit:**
    *   *Rule:* Do not rely entirely on the model to emit stop tokens. Implement a manual early exit check on the generator text stream that immediately breaks generation when matching the `<|end|>` or `<|end_of_text|>` substrings.
*   **Rolling Context Constraint:**
    *   *Rule:* Enforce a strict rolling 10-turn conversation history constraint to keep contexts small, avoiding bloated RAM consumption.

---

## ⚡ 7. Developer Hints & Debugging Lessons

*   **Mac OS Dynamic Permissions Semaphores:**
    *   *Lesson:* Asynchronous macOS security popups (like calendar access via `EKEventStore`) crash or hang CLI tools. Wrap permission callbacks in a thread semaphore (`threading.Semaphore(0)`) to cleanly block execution until the user clicks "Allow" or "Deny".
*   **SQLite Extension Loader:**
    *   *Lesson:* Always call `conn.enable_load_extension(True)` before attempting to load compiled external libraries like `sqlite-vec`.
*   **System RAM Safety Buffer:**
    *   *Lesson:* Maintain a **1.0GB System Safety Buffer** in the memory manager. If available system RAM is less than (Model RAM + 1GB), refuse model loading.
    *   *Override:* For heavy development environments, support a dynamic override via `FRIDAY_MEM_BUFFER` environment variable down to **0.5GB** but no lower.

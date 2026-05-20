import logging
import threading
import time
import gc
from pathlib import Path
import numpy as np

logger = logging.getLogger("friday.memory_embeddings")

class EmbeddingModel:
    """
    Lightweight embedding generation using all-MiniLM-L6-v2 via ONNX.
    Memory footprint: <80MB (vs ~1.5GB for PyTorch).
    """

    IDLE_TIMEOUT = 300.0  # Unload after 5 minutes of inactivity

    def __init__(self, model_dir: str = "models/all-MiniLM-L6-v2") -> None:
        self.model_dir = Path(model_dir)
        self.onnx_path = self.model_dir / "onnx" / "model_quantized.onnx"
        self.tokenizer_path = self.model_dir / "tokenizer.json"
        
        self._session = None
        self._tokenizer = None
        
        self._lock = threading.Lock()
        self._last_used = 0.0
        self._timer = None

    def _load(self) -> None:
        """Loads ONNX session and Tokenizer into memory."""
        from src.memory.manager import memory_manager, PressureLevel

        status = memory_manager.get_status()
        if status.pressure_level == PressureLevel.CRITICAL:
            import os
            # Allow developer to override critical blocks for extreme RAM environments
            buffer_val = float(os.getenv("FRIDAY_MEM_BUFFER", 1.0))
            if buffer_val <= 0.5:
                logger.warning(
                    f"System memory is CRITICAL ({status.percent:.1f}% used), "
                    f"but proceeding with embedding load due to FRIDAY_MEM_BUFFER override."
                )
            else:
                raise MemoryError("System memory is CRITICAL. Refusing to load embedding model.")

        if not self.onnx_path.exists() or not self.tokenizer_path.exists():
            raise FileNotFoundError(f"Missing ONNX models at {self.model_dir}. Run download script.")

        import onnxruntime as ort
        from tokenizers import Tokenizer

        logger.info("Loading ONNX MiniLM session...")
        
        # Load Tokenizer
        self._tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        # Ensure truncation and padding to max 256
        self._tokenizer.enable_truncation(max_length=256)
        self._tokenizer.enable_padding(length=256)
        
        # Load ONNX Session
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self._session = ort.InferenceSession(str(self.onnx_path), sess_options, providers=["CPUExecutionProvider"])
        logger.info("ONNX MiniLM loaded successfully.")

    def _unload_check(self) -> None:
        """Called by timer to unload model if idle."""
        with self._lock:
            if time.time() - self._last_used >= self.IDLE_TIMEOUT:
                if self._session is not None:
                    self._session = None
                    self._tokenizer = None
                    gc.collect()
                    logger.info("ONNX MiniLM unloaded due to inactivity.")
            else:
                # Reschedule if still active
                self._schedule_unload()

    def _schedule_unload(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.IDLE_TIMEOUT, self._unload_check)
        self._timer.daemon = True
        self._timer.start()

    def embed(self, text: str) -> np.ndarray:
        """Generates a 384-dimensional embedding vector."""
        with self._lock:
            if self._session is None:
                self._load()
            
            self._last_used = time.time()
            self._schedule_unload()

            # Tokenize
            encoding = self._tokenizer.encode(text)
            
            inputs = {
                "input_ids": np.array([encoding.ids], dtype=np.int64),
                "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
                "token_type_ids": np.array([encoding.type_ids], dtype=np.int64),
            }
            
            # Forward pass
            last_hidden = self._session.run(None, inputs)[0]
            attention_mask = inputs["attention_mask"]

            # Masked mean pooling
            mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
            sum_hidden = (last_hidden * mask_expanded).sum(axis=1)
            sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
            pooled = sum_hidden / sum_mask

            # L2 normalize
            norm = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
            embedding = (pooled / norm).squeeze(0)  # Shape: (384,)

            return embedding

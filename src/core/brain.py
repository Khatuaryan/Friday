"""
FRIDAY Brain — Phi-3.5-mini-instruct via MLX.

Handles model loading, prompt formatting, streaming generation,
and context window management.

Memory: ~2.2 GB (4-bit quantized)
Latency: <500ms first token, <2s full response
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Generator

logger = logging.getLogger("friday.brain")


class FridayBrain:
    """
    LLM interface for Phi-3.5-mini-instruct (4-bit via MLX).

    Usage:
        brain = FridayBrain()
        brain.load_model()
        response = brain.think("What time is it?")
    """

    DEFAULT_MODEL_PATH = "models/phi-3.5-mini-4bit"

    def __init__(
        self,
        model_path: str | Path | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        context_window: int = 4096,
    ) -> None:
        self.model_path = str(model_path or self.DEFAULT_MODEL_PATH)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.context_window = context_window

        self._model = None
        self._tokenizer = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> float:
        """
        Load Phi-3.5-mini into memory.

        Returns:
            Load time in seconds.

        Raises:
            MemoryError: If insufficient RAM.
            FileNotFoundError: If model files missing.
        """
        from src.memory.manager import memory_manager

        # Pre-flight memory check
        if not memory_manager.check_can_load_model(2.2):
            raise MemoryError(
                "Insufficient memory to load Phi-3.5-mini (need 2.2 GB). "
                "Close heavy applications and try again."
            )

        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Model not found at {model_dir}. "
                f"Run: python scripts/download_models.py"
            )

        logger.info("Loading Phi-3.5-mini from %s ...", self.model_path)
        start = time.perf_counter()

        from mlx_lm import load
        self._model, self._tokenizer = load(self.model_path)

        load_time = time.perf_counter() - start
        self._loaded = True

        logger.info("Phi-3.5-mini loaded in %.1fs", load_time)
        memory_manager.log_usage()
        return load_time

    def think(self, user_message: str, system_prompt: str | None = None) -> str:
        """
        Generate a response to a user message.

        Args:
            user_message: The user's input text.
            system_prompt: Optional system prompt override.

        Returns:
            The model's response text.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        prompt = self._format_prompt(user_message, system_prompt)

        from mlx_lm import generate
        start = time.perf_counter()

        response = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            temp=self.temperature,
            verbose=False,
        )

        latency = time.perf_counter() - start
        logger.info("Response generated in %.2fs (%d chars)", latency, len(response))
        return response.strip()

    def think_stream(
        self, user_message: str, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        """
        Stream response tokens one at a time.

        Yields:
            Individual tokens as they are generated.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        prompt = self._format_prompt(user_message, system_prompt)

        from mlx_lm import stream_generate
        for token_text in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            temp=self.temperature,
        ):
            yield token_text

    def _format_prompt(self, user_message: str, system_prompt: str | None = None) -> str:
        """
        Format prompt for Phi-3.5-mini-instruct chat template.

        Phi-3.5 uses:
            <|system|>...<|end|>
            <|user|>...<|end|>
            <|assistant|>
        """
        from src.core.prompts import DEFAULT_SYSTEM_PROMPT

        sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        return (
            f"<|system|>\n{sys_prompt}<|end|>\n"
            f"<|user|>\n{user_message}<|end|>\n"
            f"<|assistant|>\n"
        )

    def unload_model(self) -> None:
        """Unload model from memory (emergency cleanup)."""
        if self._model is not None:
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            self._loaded = False

            try:
                import mlx.core as mx
                mx.metal.clear_cache()
            except Exception:
                pass

            logger.info("Phi-3.5-mini unloaded from memory")

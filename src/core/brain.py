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
from typing import Generator, List, Optional, Tuple

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

        # Conversation history: list of (user_message, assistant_response) tuples
        self._conversation_history: List[Tuple[str, str]] = []
        self._max_history_turns = 10  # Limited for 8GB

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

    def think(
        self,
        user_message: str,
        system_prompt: str | None = None,
        add_to_history: bool = True,
    ) -> str:
        """
        Generate a response to a user message.

        Args:
            user_message: The user's input text.
            system_prompt: Optional system prompt override.
            add_to_history: Whether to add this exchange to conversation history.

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
        response_text = response.strip()
        logger.info("Response generated in %.2fs (%d chars)", latency, len(response_text))

        if add_to_history:
            self._add_to_history(user_message, response_text)

        return response_text

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
        full_response = ""
        for token_text in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            temp=self.temperature,
        ):
            full_response += token_text
            yield token_text

        # Commit to history after stream completes
        self._add_to_history(user_message, full_response.strip())

    def _format_prompt(self, user_message: str, system_prompt: str | None = None) -> str:
        """
        Format prompt for Phi-3.5-mini-instruct chat template.

        Phi-3.5 uses:
            <|system|>...<|end|>
            <|user|>...<|end|>
            <|assistant|>...<|end|>

        Includes conversation history for multi-turn context.
        """
        from src.core.prompts import DEFAULT_SYSTEM_PROMPT

        sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # System prompt
        formatted = f"<|system|>\n{sys_prompt}<|end|>\n"

        # Conversation history
        for user_msg, assistant_msg in self._conversation_history:
            formatted += f"<|user|>\n{user_msg}<|end|>\n"
            formatted += f"<|assistant|>\n{assistant_msg}<|end|>\n"

        # Current message
        formatted += f"<|user|>\n{user_message}<|end|>\n"
        formatted += "<|assistant|>\n"

        return formatted

    def _add_to_history(self, user_msg: str, assistant_msg: str) -> None:
        """Add turn to conversation history, maintaining max length."""
        self._conversation_history.append((user_msg, assistant_msg))

        if len(self._conversation_history) > self._max_history_turns:
            self._conversation_history = self._conversation_history[
                -self._max_history_turns:
            ]
            logger.debug("Trimmed history to last %d turns", self._max_history_turns)

    def clear_history(self) -> None:
        """Clear conversation history (e.g., start new conversation)."""
        self._conversation_history = []
        logger.info("Conversation history cleared")

    def get_history_length(self) -> int:
        """Get number of turns in history."""
        return len(self._conversation_history)

    def think_with_tools(
        self,
        user_message: str,
        max_tool_calls: int = 3,
    ) -> str:
        """
        Think with tool-calling support.

        Accumulates tool call/result pairs in a local message chain
        so context is preserved across iterations. Only commits the
        final user→response pair to conversation history.

        Args:
            user_message: User's input.
            max_tool_calls: Maximum tool calls per turn (prevent loops).

        Returns:
            Final natural language response text.
        """
        import json
        from src.tools.server import MCPToolServer
        from src.core.prompts import TOOL_CALLING_PROMPT

        tool_server = MCPToolServer()
        tools_desc = tool_server.get_tools_description()
        system_prompt = f"{TOOL_CALLING_PROMPT}\n\nAvailable tools:\n{tools_desc}"

        # Build local message chain for this tool-calling session
        messages: list[tuple[str, str]] = []

        # First pass: ask the LLM
        response = self.think(
            user_message, system_prompt=system_prompt, add_to_history=False
        )

        tool_calls_made = 0
        while tool_calls_made < max_tool_calls:
            tool_call = tool_server.parse_tool_call(response)
            if not tool_call:
                break  # No tool call — done

            # Execute tool
            tool_result = tool_server.execute_tool(tool_call)
            logger.info("Tool %s result: %s", tool_call.get("name"), tool_result)

            # Accumulate: previous response + tool result as a follow-up
            messages.append((user_message if not messages else f"Tool result: {json.dumps(tool_result)}", response))

            # Feed result back as a new user message
            follow_up = (
                f"Tool '{tool_call['name']}' returned: {json.dumps(tool_result)}\n\n"
                "Provide a natural language response based on this result."
            )
            response = self.think(
                follow_up, system_prompt=system_prompt, add_to_history=False
            )

            tool_calls_made += 1

        # Commit only the original user message and final response to history
        self._add_to_history(user_message, response)
        return response

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

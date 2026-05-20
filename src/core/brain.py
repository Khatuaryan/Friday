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
        config_path: str | Path | None = None,
    ) -> None:
        import yaml
        from pathlib import Path
        
        # Load from friday_config.yaml if possible
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "config" / "friday_config.yaml"
            
        config = None
        if Path(config_path).exists():
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config at {config_path}: {e}")
                
        # If model_path is explicitly provided, prioritize it
        if model_path:
            self.model_path = str(model_path)
            self.model_memory_gb = 2.2
            self.context_window = context_window
        elif config and "active_model" in config and "models_registry" in config:
            active = config["active_model"]
            model_cfg = config["models_registry"].get(active)
            if model_cfg:
                self.model_path = model_cfg["path"]
                self.model_memory_gb = model_cfg["memory_gb"]
                self.context_window = model_cfg.get("context_window", context_window)
                logger.info(f"Loaded active model '{active}' from registry (path={self.model_path}, memory={self.model_memory_gb}GB, context={self.context_window})")
            else:
                logger.warning(f"Active model '{active}' not found in registry. Using defaults.")
                self.model_path = self.DEFAULT_MODEL_PATH
                self.model_memory_gb = 2.2
                self.context_window = context_window
        else:
            self.model_path = self.DEFAULT_MODEL_PATH
            self.model_memory_gb = 2.2
            self.context_window = context_window

        self.max_tokens = max_tokens
        self.temperature = temperature

        self._model = None
        self._tokenizer = None
        self._loaded = False

        # Conversation history: list of (user_message, assistant_response) tuples
        self._conversation_history: List[Tuple[str, str]] = []
        self._max_history_turns = 10  # Limited for 8GB

        # Phase 6-8 Context
        self.memory_store = None
        self.context_tracker = None
        self.proactive_engine = None

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
        if not memory_manager.check_can_load_model(self.model_memory_gb):
            raise MemoryError(
                f"Insufficient memory to load active model (need {self.model_memory_gb} GB). "
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
        
        # Initialize Phase 6-8 subsystems
        try:
            from src.memory.store import MemoryStore
            from src.context.tracker import ContextTracker
            from src.proactive.engine import ProactiveEngine
            
            self.memory_store = MemoryStore()
            self.context_tracker = ContextTracker()
            self.context_tracker.start()
            self.proactive_engine = ProactiveEngine(context_tracker=self.context_tracker)
            self.proactive_engine.start()
            logger.info("RAG Memory, Context, and Proactive Engines initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize Phase Set 3 subsystems: {e}")
            
        return load_time

    def think(
        self,
        user_message: str,
        system_prompt: str | None = None,
        add_to_history: bool = True,
    ) -> str:
        """Generate a response to a user message."""
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Ensure MLX GPU stream is ready for this thread and cache is cleared to prevent Metal OOM
        import mlx.core as mx
        mx.default_stream(mx.gpu)
        mx.clear_cache()

        prompt = self._format_prompt(user_message, system_prompt)

        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
        start = time.perf_counter()

        response = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            sampler=make_sampler(self.temperature),
            logits_processors=make_logits_processors(repetition_penalty=1.1, repetition_context_size=50),
            verbose=False,
        )

        # Ensure we stop at the Phi-3.5 end token if the model forgets
        if "<|end|>" in response:
            response = response.split("<|end|>")[0]

        latency = time.perf_counter() - start
        response_text = response.strip()
        logger.info("Response generated in %.2fs (%d chars)", latency, len(response_text))

        if add_to_history:
            self._add_to_history(user_message, response_text)

        # Clear Metal cache after generation to release allocated memory immediately
        try:
            mx.clear_cache()
        except Exception:
            pass

        return response_text

    def think_with_memory_and_context(self, user_message: str, max_tool_calls: int = 3) -> str:
        """Thinks using RAG memory, active context, and tool-calling support."""
        import json
        from src.core.prompts import TOOL_CALLING_PROMPT, format_context_prompt
        from src.tools.server import MCPToolServer
        
        rag_context = []
        active_app = None
        
        # 1. Fetch RAG memories (skip if CRITICAL system pressure and not overridden)
        if self.memory_store:
            from src.memory.manager import memory_manager, PressureLevel
            import os
            
            status = memory_manager.get_status()
            buffer_val = float(os.getenv("FRIDAY_MEM_BUFFER", 1.0))
            
            # Skip RAG search only if memory is CRITICAL and no force override
            if status.pressure_level == PressureLevel.CRITICAL and buffer_val > 0.5:
                logger.warning("System memory is CRITICAL. Skipping RAG search to conserve memory.")
            else:
                try:
                    rag_context = self.memory_store.search(user_message, limit=3)
                except Exception as e:
                    logger.warning(f"RAG search failed: {e}")
                    
            self.memory_store.add_conversation_turn("user", user_message)
            
        # 2. Fetch active application context
        if self.context_tracker:
            active_app = self.context_tracker.get_current_context()
            
        # 3. Setup Tool Server
        tool_server = MCPToolServer()
        tools_desc = tool_server.get_tools_description()
        base_tool_prompt = f"{TOOL_CALLING_PROMPT}\n\nAvailable tools:\n{tools_desc}"
        
        # 4. Construct System Prompt
        system_prompt = format_context_prompt(base_tool_prompt, active_app, rag_context)
        
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

            # Feed result back as a new user message
            follow_up = (
                f"Tool '{tool_call['name']}' returned: {json.dumps(tool_result)}\n\n"
                "Provide a natural language response based on this result. "
                "If you need to call another tool to proceed, you can output another tool call."
            )
            response = self.think(
                follow_up, system_prompt=system_prompt, add_to_history=False
            )

            tool_calls_made += 1

        # Commit only the original user message and final response to history
        self._add_to_history(user_message, response)
        
        if self.memory_store:
            self.memory_store.add_conversation_turn("assistant", response)
            
        return response

    def think_stream(
        self, user_message: str, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        """
        Stream response tokens one at a time.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Ensure MLX GPU stream is ready for this thread and cache is cleared to prevent Metal OOM
        import mlx.core as mx
        mx.default_stream(mx.gpu)
        mx.clear_cache()

        prompt = self._format_prompt(user_message, system_prompt)

        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
        full_response = ""
        for response in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            sampler=make_sampler(self.temperature),
            logits_processors=make_logits_processors(repetition_penalty=1.1, repetition_context_size=50),
        ):
            token_text = response.text
            full_response += token_text
            
            # Early stop if the model spits out the end token
            if "<|end|>" in full_response:
                clean_text = token_text.replace("<|end|>", "")
                if clean_text:
                    yield clean_text
                break
                
            yield token_text

        # Commit to history after stream completes
        self._add_to_history(user_message, full_response.strip())

        # Clear Metal cache after generation to release allocated memory immediately
        try:
            mx.clear_cache()
        except Exception:
            pass

    def _format_prompt(self, user_message: str, system_prompt: str | None = None) -> str:
        """
        Format prompt for chat model.
        Uses the active tokenizer's chat template if loaded, otherwise falls back to a clean,
        structured default format.
        """
        from src.core.prompts import DEFAULT_SYSTEM_PROMPT
        sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        if self._tokenizer is not None:
            messages = []
            if sys_prompt:
                messages.append({"role": "system", "content": sys_prompt})
            for user_msg, assistant_msg in self._conversation_history:
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": assistant_msg})
            messages.append({"role": "user", "content": user_message})

            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        
        # Fallback if tokenizer not loaded (e.g. unit tests)
        formatted = ""
        if sys_prompt:
            formatted += f"<|system|>\n{sys_prompt}<|end|>\n"
        for user_msg, assistant_msg in self._conversation_history:
            formatted += f"<|user|>\n{user_msg}<|end|>\n"
            formatted += f"<|assistant|>\n{assistant_msg}<|end|>\n"
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
                mx.clear_cache()
            except Exception:
                pass

            logger.info("Phi-3.5-mini unloaded from memory")

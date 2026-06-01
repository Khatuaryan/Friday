"""
FRIDAY Brain — Phi-3.5-mini-instruct via MLX.

Handles model loading, prompt formatting, streaming generation,
and context window management.

Memory: ~2.2 GB (4-bit quantized)
Latency: <500ms first token, <2s full response
"""

from __future__ import annotations

from src.utils.logger import get_logger
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = get_logger("friday.brain")


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
        import os
        from src.utils.config import get_config

        # Try loading centralized config first
        config = None
        self.active_model = "phi-3.5-mini"
        self.openrouter_config = None
        
        try:
            from src.utils.config import load_config
            if config_path:
                import src.utils.config as cfg_mod
                cfg_mod._config = None # Reset singleton cache for test isolation
                config = load_config(config_path)
            else:
                config = get_config()
            self.active_model = config.active_model
            self.openrouter_config = config.openrouter
        except Exception as e:
            logger.warning(f"Failed to load centralized config: {e}")

        # If model_path is explicitly provided, prioritize it
        if model_path:
            self.model_path = str(model_path)
            self.model_memory_gb = 2.2
            self.context_window = context_window
            self.active_model = "phi-3.5-mini"  # Treat as local model launch
        elif self.active_model == "openrouter":
            self.model_path = "openrouter"
            self.model_memory_gb = 0.0
            self.context_window = 8192
            if self.openrouter_config:
                self.openrouter_api_key = self.openrouter_config.api_key or os.getenv("OPENROUTER_API_KEY", "")
                self.openrouter_model = self.openrouter_config.model
            else:
                self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
                self.openrouter_model = "google/gemma-4-31b-it:free"
            logger.info(f"Using OpenRouter Brain Engine: model={self.openrouter_model}")
        elif config and hasattr(config, "models_registry") and self.active_model in config.models_registry:
            model_cfg = config.models_registry[self.active_model]
            self.model_path = model_cfg.path
            self.model_memory_gb = model_cfg.memory_gb
            self.context_window = model_cfg.context_window
            logger.info(f"Loaded active model '{self.active_model}' from registry (path={self.model_path}, memory={self.model_memory_gb}GB, context={self.context_window})")
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
        
        # Phase 5C Confirmation payload cache
        self.pending_confirmation = None


    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> float:
        """
        Load active model. For local models, loads files; for OpenRouter, validates API key.

        Returns:
            Load time in seconds.
        """
        start = time.perf_counter()

        if self.active_model == "openrouter":
            import os
            # Ensure API key is configured
            self.openrouter_api_key = self.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
            if not self.openrouter_api_key:
                raise ValueError("OpenRouter API key is missing. Set OPENROUTER_API_KEY in .env or config.")
            
            logger.info("Initializing F.R.I.D.A.Y. via OpenRouter Cloud API (Gemma 4 31B:free)")
            self._loaded = True
            load_time = time.perf_counter() - start
        else:
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

            from mlx_lm import load
            loaded = load(self.model_path)
            self._model, self._tokenizer = loaded[0], loaded[1]

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

    def think_full(
        self,
        user_message: str,
        max_tool_calls: int = 2,
        detected_language: str = "en",
    ) -> str:
        """
        Unified reasoning cycle:
        1. Inject dynamic context (datetime, locale, active app)
        2. Retrieve RAG memories
        3. Build system prompt
        4. Run tool-calling loop (max_tool_calls ceiling)
        5. Return concise final response
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        MAX_INPUT_CHARS = 500
        if len(user_message) > MAX_INPUT_CHARS:
            logger.warning(
                "Input truncated: %d → %d chars", len(user_message), MAX_INPUT_CHARS
            )
            user_message = user_message[:MAX_INPUT_CHARS]


        import json
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            ist = ZoneInfo("Asia/Kolkata")
            now_ist = datetime.now(ist)
        except Exception:
            from datetime import timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(ist)
        
        datetime_str = now_ist.strftime("%A, %d %B %Y, %I:%M %p IST")

        # 1. Fetch RAG memories (skip if CRITICAL system pressure and not overridden)
        rag_memories = []
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
                    rag_memories = self.memory_store.search(user_message, limit=3)
                except Exception as e:
                    logger.warning(f"RAG search failed: {e}")
                    
            try:
                self.memory_store.add_conversation_turn("user", user_message)
            except Exception as e:
                logger.warning(f"Failed to save user turn to RAG store: {e}")

        # 2. Fetch active application context
        active_app = None
        if self.context_tracker:
            active_app = self.context_tracker.get_current_context()

        # 3. Setup Tool Server & build dynamic system prompt
        from src.tools.server import MCPToolServer
        from src.core.prompts import build_full_system_prompt
        
        tool_server = MCPToolServer()
        registered_tools = tool_server.get_tool_names()
        tools_desc = tool_server.get_tools_description()
        
        system_prompt = build_full_system_prompt(
            datetime_str=datetime_str,
            active_app=active_app,
            rag_memories=rag_memories,
            registered_tools=registered_tools,
            tools_description=tools_desc,
            user_language=detected_language,
        )


        # 4. Tool-calling loop
        session_messages = [{"role": "user", "content": user_message}]
        final_response = ""
        tool_calls_made = 0

        while tool_calls_made <= max_tool_calls:
            raw_response = self._generate(system_prompt, session_messages)
            tool_call = tool_server.parse_tool_call(raw_response)

            if not tool_call or tool_calls_made == max_tool_calls:
                # No tool call, or ceiling reached — this is the final response
                final_response = raw_response
                # Strip any residual tool_call tags if ceiling was hit mid-loop
                if "<tool_call>" in final_response:
                    final_response = "I was unable to retrieve that information right now."
                break

            # Execute tool and accumulate context
            tool_result = tool_server.execute_tool(tool_call)
            logger.info("Tool '%s' result: %s", tool_call.get("name"), str(tool_result)[:200])

            # Check if execution requires verbal confirmation (destructive actions)
            if isinstance(tool_result, dict) and tool_result.get("requires_confirmation"):
                self.pending_confirmation = tool_result
                action_desc = tool_result.get("action_description", "perform a restricted action")
                final_response = f"I'm about to {action_desc}. Please say confirm to proceed, or cancel."
                break

            # Accumulate this exchange in session messages
            session_messages.append({"role": "assistant", "content": raw_response})
            session_messages.append({
                "role": "user",
                "content": (
                    f"Tool '{tool_call['name']}' returned: {json.dumps(tool_result)}\n\n"
                    "The tool has executed. You now have all the information you need. "
                    "DO NOT call any more tools. Provide your final answer in under 50 words, "
                    "spoken aloud to the user. No lists, no markdown."
                )
            })
            tool_calls_made += 1

        # 5. Post-process response constraints
        final_response = self._enforce_response_constraints(final_response)

        # 6. Commit single clean turn to history
        self._add_to_history(user_message, final_response)
        
        if self.memory_store:
            try:
                self.memory_store.add_conversation_turn("assistant", final_response)
            except Exception as e:
                logger.warning(f"Failed to save assistant turn to RAG store: {e}")

        return final_response

    def execute_pending_tool(self) -> Dict[str, Any]:
        """
        Execute the cached pending tool action in self.pending_confirmation.

        Returns:
            The execution result.
        """
        if not self.pending_confirmation:
            return {"error": "No pending confirmation found"}

        pending_action = self.pending_confirmation.get("pending_action")
        if not pending_action:
            self.pending_confirmation = None
            return {"error": "Invalid pending confirmation format"}

        self.pending_confirmation = None
        from src.tools.server import MCPToolServer
        tool_server = MCPToolServer()
        return tool_server.execute_tool(pending_action)

    def _lazy_load_local_fallback(self) -> None:
        """Lazy-loads the local Phi-3.5-mini fallback model into memory."""
        if self._model is not None:
            return  # Already loaded
            
        logger.warning("F.R.I.D.A.Y. is offline or OpenRouter is down. Lazy-loading local Phi-3.5-mini fallback...")
        from pathlib import Path
        local_path = "models/phi-3.5-mini-4bit"
        model_dir = Path(local_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Local fallback model not found at {local_path}. Run 'make download-model' to enable offline fallback.")
            
        from mlx_lm import load
        loaded = load(str(model_dir))
        self._model, self._tokenizer = loaded[0], loaded[1]
        logger.info("Local Phi-3.5-mini fallback model loaded successfully.")

    def _generate_local(
        self,
        system_prompt: str,
        session_messages: List[Dict[str, str]],
    ) -> str:
        """Local MLX inference generation."""
        import mlx.core as mx
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors

        mx.default_stream(mx.gpu)
        mx.clear_cache()

        # Build full message list for chat template
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
            
        # Add conversation history
        for user_msg, assistant_msg in self._conversation_history:
            chat_messages.append({"role": "user", "content": user_msg})
            chat_messages.append({"role": "assistant", "content": assistant_msg})
            
        # Add current session messages
        chat_messages.extend(session_messages)

        if self._tokenizer is not None:
            prompt = self._tokenizer.apply_chat_template(
                chat_messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # Fallback if tokenizer not loaded (e.g. unit tests)
            prompt = ""
            if system_prompt:
                prompt += f"<|system|>\n{system_prompt}<|end|>\n"
            for msg in chat_messages:
                if msg["role"] == "system":
                    continue
                prompt += f"<|{msg['role']}|>\n{msg['content']}<|end|>\n"
            prompt += "<|assistant|>\n"

        response = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            sampler=make_sampler(self.temperature),
            logits_processors=make_logits_processors(
                repetition_penalty=1.1,
                repetition_context_size=50
            ),
            verbose=False,
        )

        if "<|end|>" in response:
            response = response.split("<|end|>")[0]

        # Early stop if the model emits other stop tokens
        for token in ["<|end_of_text|>", "<start_of_turn>", "<end_of_turn>"]:
            if token in response:
                response = response.split(token)[0]

        try:
            mx.clear_cache()
        except Exception:
            pass

        return response.strip()

    def _generate(
        self,
        system_prompt: str,
        session_messages: List[Dict[str, str]],
    ) -> str:
        """
        Single LLM inference pass.
        If OpenRouter, sends POST request via httpx. Falls back to local Phi-3.5-mini if network fails.
        If local, uses MLX.
        """
        if self.active_model == "openrouter":
            import httpx
            import json
            
            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            
            # Add conversation history
            for user_msg, assistant_msg in self._conversation_history:
                chat_messages.append({"role": "user", "content": user_msg})
                chat_messages.append({"role": "assistant", "content": assistant_msg})
                
            # Add current session messages
            chat_messages.extend(session_messages)
            
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/aryan/friday",
                "X-Title": "FRIDAY Voice Assistant",
            }
            
            payload = {
                "model": self.openrouter_model,
                "messages": chat_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            start = time.perf_counter()
            try:
                response = httpx.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"].strip()
                latency = time.perf_counter() - start
                logger.info(f"OpenRouter Gemma 4 generated response in {latency:.2f}s")
                return content
            except Exception as e:
                logger.warning(f"OpenRouter API call failed ({e}). Falling back to local Phi-3.5-mini...")
                try:
                    self._lazy_load_local_fallback()
                    return self._generate_local(system_prompt, session_messages)
                except Exception as fallback_err:
                    logger.critical(f"Local fallback generation failed: {fallback_err}")
                    return "I apologize, but I encountered a connection issue and my local fallback model is unavailable."
        else:
            return self._generate_local(system_prompt, session_messages)

    def _enforce_response_constraints(self, text: str) -> str:
        """
        Enforce 50-word / 300-character ceiling for TTS.
        Find last complete sentence within limit. Hard cut if no sentence found.
        """
        if len(text) <= 300:
            return text

        # Try to find last sentence boundary within 350 chars (grace window)
        candidate = text[:350]
        for punct in ['. ', '! ', '? ']:
            last_idx = candidate.rfind(punct)
            if last_idx > 100:  # Must be at least 100 chars in
                return candidate[:last_idx + 1].strip()

        # No clean boundary found — hard cut at 300
        return text[:300].strip() + "..."

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

    def _think_stream_local(
        self, user_message: str, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        """Stream response tokens using the local Phi-3.5-mini model without committing to history."""
        import mlx.core as mx
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors

        mx.default_stream(mx.gpu)
        mx.clear_cache()

        prompt = self._format_prompt(user_message, system_prompt)
        full_response = ""
        
        try:
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
        finally:
            # Clear Metal cache after generation to release allocated memory immediately
            try:
                mx.clear_cache()
            except Exception:
                pass

    def think_stream(
        self, user_message: str, system_prompt: str | None = None
    ) -> Generator[str, None, None]:
        """
        Stream response tokens one at a time.
        If OpenRouter is active, streams from Gemma cloud API, falling back to local Phi-3.5-mini if network fails.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if self.active_model == "openrouter":
            import httpx
            import json
            
            chat_messages = []
            from src.core.prompts import DEFAULT_SYSTEM_PROMPT
            sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
            if sys_prompt:
                chat_messages.append({"role": "system", "content": sys_prompt})
            for user_msg, assistant_msg in self._conversation_history:
                chat_messages.append({"role": "user", "content": user_msg})
                chat_messages.append({"role": "assistant", "content": assistant_msg})
            chat_messages.append({"role": "user", "content": user_message})
            
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/aryan/friday",
                "X-Title": "FRIDAY Voice Assistant",
            }
            
            payload = {
                "model": self.openrouter_model,
                "messages": chat_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            
            full_response = ""
            yielded_any = False
            try:
                with httpx.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10.0,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data_json = json.loads(data_str)
                                token_text = data_json["choices"][0]["delta"].get("content", "")
                                if token_text:
                                    full_response += token_text
                                    yielded_any = True
                                    yield token_text
                            except Exception:
                                pass
                self._add_to_history(user_message, full_response.strip())
            except Exception as e:
                logger.warning(f"OpenRouter streaming call failed ({e}). Falling back to local Phi-3.5-mini...")
                try:
                    self._lazy_load_local_fallback()
                    if yielded_any:
                        yield "\n[Cloud stream interrupted. Falling back to local brain...]\n"
                    
                    fallback_response = ""
                    for token in self._think_stream_local(user_message, system_prompt):
                        fallback_response += token
                        yield token
                    
                    combined_response = (full_response + "\n" + fallback_response).strip()
                    self._add_to_history(user_message, combined_response)
                except Exception as fallback_err:
                    logger.critical(f"Local streaming fallback failed: {fallback_err}")
                    err_msg = " I apologize, but I encountered a connection issue and my local fallback model is unavailable."
                    yield err_msg
                    self._add_to_history(user_message, (full_response + err_msg).strip())
        else:
            full_response = ""
            for token in self._think_stream_local(user_message, system_prompt):
                full_response += token
                yield token
            self._add_to_history(user_message, full_response.strip())

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

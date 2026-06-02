"""
Voice Pipeline — Coordinates STT → Brain → TTS.

Orchestrates the full voice interaction flow after identity verification.

Flow:
    1. Listen for speech (STT with VAD auto-stop)
    2. Process with Brain (Phase 4 — placeholder for now)
    3. Speak response (TTS)
"""

from __future__ import annotations

from src.utils.logger import get_logger
from typing import Optional

from src.modules.audio.stt import SpeechToText
from src.modules.audio.tts import TextToSpeech

logger = get_logger("friday.voice_pipeline")


class VoicePipeline:
    """
    End-to-end voice interaction pipeline.

    Usage:
        stt = SpeechToText()
        tts = TextToSpeech()
        pipeline = VoicePipeline(stt=stt, tts=tts)
        response = pipeline.process_voice_command(timeout=10)
    """

    def __init__(
        self,
        stt: SpeechToText,
        tts: TextToSpeech,
        brain=None,
    ) -> None:
        """
        Args:
            stt: SpeechToText instance.
            tts: TextToSpeech instance.
            brain: FridayBrain instance (optional — added in Phase 4).
        """
        self.stt = stt
        self.tts = tts
        self.brain = brain
        self.ipc_bridge = None
        self.activation_handler = None

        if not brain:
            logger.warning("Brain not provided — using placeholder responses")

    def process_voice_command(
        self,
        timeout: float = 10.0,
        return_tuple: bool = False,
        pre_transcribed_command: Optional[str] = None,
    ) -> Optional[str] | tuple[Optional[str], Optional[str]]:
        """
        Full voice interaction loop.

        Args:
            timeout: Max listening time in seconds.
            return_tuple: If True, returns (command_text, response_text).
            pre_transcribed_command: Optional pre-transcribed text to bypass listening.

        Returns:
            Response text, or tuple of (command, response), or None if no speech detected.
        """
        logger.info("Listening for command...")

        # 1. Listen and transcribe or use pre-transcribed
        if pre_transcribed_command:
            command_text = pre_transcribed_command
            # Basic detection if there are non-ASCII characters (e.g. Devanagari)
            detected_lang = "hi" if any(ord(c) > 127 for c in command_text) else "en"
        else:
            listen_result = self.stt.listen(timeout=timeout)

            if isinstance(listen_result, tuple):
                command_text, detected_lang = listen_result
            else:
                command_text, detected_lang = listen_result, "en"

        if not command_text:
            logger.info("No speech detected")
            if getattr(self, "ipc_bridge", None):
                self.ipc_bridge.update_text(last_command="", last_response="")
            return (None, None) if return_tuple else None

        logger.info("Command [lang=%s]: %s", detected_lang, command_text)

        # Instantly update IPC with user transcription
        if getattr(self, "ipc_bridge", None):
            self.ipc_bridge.update_text(last_command=command_text, last_response="")
            # Force write status to notify Swift UI we got a command
            self.ipc_bridge.write_status("processing")

        response_text = ""

        # 2. Process with brain (if available)
        if self.brain:
            try:
                # Check if it is a pure conversational query (no tool keywords) to enable streaming
                tool_keywords = ["weather", "battery", "storage", "remind", "calendar", "event", "open", "close", "run", "music", "spotify", "clipboard", "shell", "delete", "write", "search", "google", "mail", "message"]
                is_conversational = not any(kw in command_text.lower() for kw in tool_keywords)
                
                if is_conversational and hasattr(self.brain, "think_stream") and getattr(self.brain, "active_model", None) == "openrouter":
                    logger.info("Pure conversational query detected. Using ultra-low-latency streaming pass...")
                    from src.core.prompts import LOCAL_SYNTHESIS_SYSTEM_PROMPT
                    
                    sentence_buffer = ""
                    first_speak = True
                    
                    # Accumulate and stream-speak sentences incrementally
                    for token in self.brain.think_stream(command_text, system_prompt=LOCAL_SYNTHESIS_SYSTEM_PROMPT):
                        response_text += token
                        sentence_buffer += token
                        
                        # Trigger speaking immediately upon sentence boundaries
                        if any(sentence_buffer.endswith(punct) for punct in (".", "?", "!", "\n", "।")):
                            clean_sentence = sentence_buffer.strip()
                            if len(clean_sentence) > 3:
                                logger.debug("Incremental speak chunk: %s", clean_sentence)
                                if first_speak:
                                    # Set to speaking and push partial response text to bubble
                                    if getattr(self, "ipc_bridge", None):
                                        self.ipc_bridge.update_text(last_response=response_text)
                                    if getattr(self, "activation_handler", None):
                                        self.activation_handler._set_state("speaking")
                                    first_speak = False
                                self.tts.speak(clean_sentence, blocking=False)
                            sentence_buffer = ""
                    
                    # Speak remaining tokens
                    clean_sentence = sentence_buffer.strip()
                    if len(clean_sentence) > 0:
                        if first_speak:
                            if getattr(self, "ipc_bridge", None):
                                self.ipc_bridge.update_text(last_response=response_text)
                            if getattr(self, "activation_handler", None):
                                self.activation_handler._set_state("speaking")
                        self.tts.speak(clean_sentence, blocking=True)
                    
                    # Ensure full final response is updated in the bubble
                    if getattr(self, "ipc_bridge", None):
                        self.ipc_bridge.update_text(last_response=response_text)
                        
                    return (command_text, response_text) if return_tuple else response_text

                # Use unified thinking path if available
                if hasattr(self.brain, "think_full"):
                    response_text = self.brain.think_full(command_text, detected_language=detected_lang)
                elif hasattr(self.brain, "think_with_memory_and_context"):
                    response_text = self.brain.think_with_memory_and_context(command_text)
                # Fallback to tool-calling path
                elif hasattr(self.brain, "think_with_tools"):
                    response_text = self.brain.think_with_tools(command_text)
                else:
                    response_text = self.brain.think(command_text)

                # Check for pending confirmation right after thinking cycle
                if hasattr(self.brain, "pending_confirmation") and self.brain.pending_confirmation:
                    # Update IPC with pending question
                    if getattr(self, "ipc_bridge", None):
                        self.ipc_bridge.update_text(last_response=response_text)
                    if getattr(self, "activation_handler", None):
                        self.activation_handler._set_state("speaking")

                    # 1. Speak the prompt verbally
                    self.tts.speak(response_text, blocking=True)

                    # 2. Call self.stt.listen(timeout=8) for verbal confirmation
                    if getattr(self, "activation_handler", None):
                        self.activation_handler._set_state("processing")
                    confirm_result = self.stt.listen(timeout=8.0)
                    if isinstance(confirm_result, tuple):
                        confirm_text, _ = confirm_result
                    else:
                        confirm_text = confirm_result

                    confirm_text = (confirm_text or "").strip().lower()

                    # 3. Check for positive verbal affirmation
                    is_confirmed = False
                    for word in ["confirm", "yes", "proceed", "haan", "karo"]:
                        if word in confirm_text:
                            is_confirmed = True
                            break

                    if is_confirmed:
                        # Execute the pending tool call
                        result = self.brain.execute_pending_tool()
                        confirm_msg = result.get("confirmation_message") or result.get("status") or "Action executed successfully."
                        if getattr(self, "ipc_bridge", None):
                            self.ipc_bridge.update_text(last_response=confirm_msg)
                        if getattr(self, "activation_handler", None):
                            self.activation_handler._set_state("speaking")
                        self.tts.speak(confirm_msg, blocking=True)
                        response_text = confirm_msg
                    else:
                        # 4. Reset pending confirmation and abort
                        self.brain.pending_confirmation = None
                        cancel_msg = "Okay, cancelled." if detected_lang != "hi" else "ठीक है, रद्द कर दिया गया।"
                        if getattr(self, "ipc_bridge", None):
                            self.ipc_bridge.update_text(last_response=cancel_msg)
                        if getattr(self, "activation_handler", None):
                            self.activation_handler._set_state("speaking")
                        self.tts.speak(cancel_msg, blocking=True)
                        response_text = cancel_msg
                    return (command_text, response_text) if return_tuple else response_text

            except Exception as e:
                logger.error("Brain error: %s", e)
                if detected_lang == "hi":
                    response_text = "अभी कुछ समस्या है।"
                else:
                    response_text = "I'm having trouble processing that right now."
        else:
            if detected_lang == "hi":
                response_text = f"मैंने सुना: {command_text}। मस्तिष्क कनेक्टेड नहीं है।"
            else:
                response_text = (
                    f"I heard you say: {command_text}. "
                    "Brain not connected."
                )

        logger.info("Response: %s", response_text)

        # Update IPC right before vocalizing
        if getattr(self, "ipc_bridge", None):
            self.ipc_bridge.update_text(last_response=response_text)

        # 3. Speak response
        if getattr(self, "activation_handler", None):
            self.activation_handler._set_state("speaking")
        self.tts.speak(response_text, blocking=True)

        return (command_text, response_text) if return_tuple else response_text

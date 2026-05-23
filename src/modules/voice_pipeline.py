"""
Voice Pipeline — Coordinates STT → Brain → TTS.

Orchestrates the full voice interaction flow after identity verification.

Flow:
    1. Listen for speech (STT with VAD auto-stop)
    2. Process with Brain (Phase 4 — placeholder for now)
    3. Speak response (TTS)
"""

from __future__ import annotations

import logging
from typing import Optional

from src.modules.audio.stt import SpeechToText
from src.modules.audio.tts import TextToSpeech

logger = logging.getLogger("friday.voice_pipeline")


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

        if not brain:
            logger.warning("Brain not provided — using placeholder responses")

    def process_voice_command(self, timeout: float = 10.0) -> Optional[str]:
        """
        Full voice interaction loop.

        Args:
            timeout: Max listening time in seconds.

        Returns:
            Response text, or None if no speech detected.
        """
        logger.info("Listening for command...")

        # 1. Listen and transcribe
        listen_result = self.stt.listen(timeout=timeout)

        if isinstance(listen_result, tuple):
            command_text, detected_lang = listen_result
        else:
            command_text, detected_lang = listen_result, "en"

        if not command_text:
            logger.info("No speech detected")
            return None

        logger.info("Command [lang=%s]: %s", detected_lang, command_text)

        # 2. Process with brain (if available)
        if self.brain:
            try:
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

        # 3. Speak response
        self.tts.speak(response_text, blocking=True)

        return response_text

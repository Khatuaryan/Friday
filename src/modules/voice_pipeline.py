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
        command_text = self.stt.listen(timeout=timeout)

        if not command_text:
            logger.info("No speech detected")
            return None

        logger.info("Command: %s", command_text)

        # 2. Process with brain (if available)
        if self.brain:
            try:
                # Use tool-calling path if available
                if hasattr(self.brain, "think_with_tools"):
                    response_text = self.brain.think_with_tools(command_text)
                else:
                    response_text = self.brain.think(command_text)
            except Exception as e:
                logger.error("Brain error: %s", e)
                response_text = "I'm having trouble processing that right now."
        else:
            response_text = (
                f"I heard you say: {command_text}. "
                "Brain not connected."
            )

        logger.info("Response: %s", response_text)

        # 3. Speak response
        self.tts.speak(response_text, blocking=True)

        return response_text

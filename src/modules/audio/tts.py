"""
Text-to-Speech — Piper TTS.

Placeholder for Phase 3 implementation.
Will use piper-tts with en_US-lessac-medium voice.
Fallback: macOS `say` command (0 MB).

Memory: ~150 MB
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("friday.tts")


class TextToSpeech:
    """
    TTS with Piper (Phase 3) and macOS `say` fallback.

    The fallback is available now for testing.
    """

    def __init__(self) -> None:
        logger.info("TTS module initialized (macOS `say` fallback active)")

    def speak(self, text: str) -> None:
        """Speak text using available engine."""
        self._speak_macos_say(text)

    @staticmethod
    def _speak_macos_say(text: str) -> None:
        """Fallback: use macOS built-in `say` command (0 MB overhead)."""
        try:
            subprocess.run(
                ["say", "-r", "180", text],
                check=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            logger.warning("macOS `say` timed out")
        except Exception:
            logger.exception("macOS `say` failed")

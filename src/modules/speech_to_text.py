"""
Speech-to-Text — Distil-Whisper via MLX.

Placeholder for Phase 3 implementation.
Will use mlx-whisper with distil-whisper-small.en model.

Memory: ~600 MB
"""

from __future__ import annotations

import logging

logger = logging.getLogger("friday.stt")


class SpeechToText:
    """Placeholder — will be implemented in Phase 3."""

    def __init__(self) -> None:
        logger.info("STT module initialized (stub — Phase 3)")

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text."""
        raise NotImplementedError("STT implementation coming in Phase 3")

    def transcribe_stream(self):
        """Transcribe live microphone input."""
        raise NotImplementedError("STT streaming coming in Phase 3")

"""
Voice Pipeline — End-to-end voice interaction.

Placeholder for Phase 3 integration.
Will coordinate: STT → Brain → TTS with streaming.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("friday.voice_pipeline")


class VoicePipeline:
    """Placeholder — will be implemented in Phase 3."""

    def __init__(self) -> None:
        logger.info("Voice pipeline initialized (stub — Phase 3)")

    def process_voice_command(self) -> str:
        """Listen, transcribe, think, speak."""
        raise NotImplementedError("Voice pipeline coming in Phase 3")

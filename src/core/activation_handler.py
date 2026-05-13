"""
Activation Handler — Coordinates wake word → face verification → voice interaction.

This is the main orchestrator for the activation pipeline:
    1. Wake word detected ("Hey Mycroft" / future "FRIDAY")
    2. Camera activates → Apple Vision verifies Boss identity
    3. TTS greets Boss → STT listens for voice command
    4. Voice pipeline processes the command (Brain in Phase 4)

State machine:
    IDLE → LISTENING (wake word) → VERIFYING (face) → READY (command) → IDLE
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("friday.activation")


class ActivationState(str, Enum):
    """Activation pipeline states."""
    IDLE = "idle"
    LISTENING = "listening"        # Wake word active
    VERIFYING = "verifying"        # Face check in progress
    READY = "ready"                # Boss verified, awaiting command
    PROCESSING = "processing"      # Voice pipeline active
    SPEAKING = "speaking"          # TTS playing


class ActivationHandler:
    """
    Coordinates the activation flow:
        Wake word → Face verification → Voice interaction

    Usage:
        handler = ActivationHandler(
            boss_encodings_path="data/faces/boss_vision.pkl",
            on_boss_verified=my_callback,
        )
        handler.start()
    """

    def __init__(
        self,
        boss_encodings_path: str,
        on_boss_verified: Callable[[], None],
        on_stranger: Optional[Callable[[], None]] = None,
        on_no_face: Optional[Callable[[], None]] = None,
        camera_index: Optional[int] = None,
    ) -> None:
        self.boss_encodings_path = boss_encodings_path
        self.on_boss_verified = on_boss_verified
        self.on_stranger = on_stranger
        self.on_no_face = on_no_face
        self.camera_index = camera_index

        self._state = ActivationState.IDLE
        self._lock = threading.Lock()

        # Components (lazy-initialized in start())
        self._wake_word = None
        self._face_recognizer = None
        self._stt = None
        self._tts = None
        self._voice_pipeline = None

    @property
    def state(self) -> ActivationState:
        return self._state

    def start(self) -> None:
        """Start the activation pipeline (wake word listening)."""
        from src.memory.manager import memory_manager
        memory_manager.log_usage()

        # Initialize wake word detector
        from src.modules.audio.wake_word import WakeWordDetector
        self._wake_word = WakeWordDetector(
            callback=self._on_wake_word,
        )

        # Initialize face recognizer (0 MB overhead — native Vision)
        from src.modules.vision.face_recognizer import VisionFaceRecognizer
        self._face_recognizer = VisionFaceRecognizer(
            boss_encodings_path=self.boss_encodings_path,
            camera_index=self.camera_index,
        )

        # Initialize voice pipeline (lazy — STT model loads on first use)
        from src.modules.audio.stt import SpeechToText
        from src.modules.audio.tts import TextToSpeech
        from src.modules.voice_pipeline import VoicePipeline

        self._stt = SpeechToText()
        self._tts = TextToSpeech()

        # Initialize brain (optional — graceful degradation if model missing)
        brain = None
        try:
            from src.core.brain import FridayBrain
            brain = FridayBrain()
            brain.load_model()
            logger.info("Brain loaded — full voice interaction ready")
        except (FileNotFoundError, MemoryError) as e:
            logger.warning("Brain not available (%s) — running without LLM", e)
        except Exception:
            logger.exception("Unexpected error loading brain")

        self._voice_pipeline = VoicePipeline(
            stt=self._stt,
            tts=self._tts,
            brain=brain,
        )

        self._wake_word.start()
        self._set_state(ActivationState.LISTENING)
        logger.info("Activation handler started — listening for wake word")

    def stop(self) -> None:
        """Stop all activation components."""
        if self._wake_word:
            self._wake_word.stop()
        if self._tts:
            self._tts.stop()
        self._set_state(ActivationState.IDLE)
        logger.info("Activation handler stopped")

    def _on_wake_word(self) -> None:
        """Callback when wake word is detected — triggers face verification."""
        with self._lock:
            if self._state != ActivationState.LISTENING:
                logger.debug("Wake word ignored (state=%s)", self._state)
                return
            self._set_state(ActivationState.VERIFYING)

        logger.info("🎤 Wake word detected! Verifying identity...")
        start = time.perf_counter()

        try:
            identity, name = self._face_recognizer.verify_identity(
                camera_index=self.camera_index
            )
            latency = time.perf_counter() - start

            if identity == "boss":
                logger.info("✅ Boss verified in %.2fs", latency)
                self._set_state(ActivationState.READY)

                # Fire user callback
                threading.Thread(
                    target=self.on_boss_verified, daemon=True
                ).start()

                # Start voice interaction
                self._handle_voice_interaction()

            elif identity == "stranger":
                logger.warning("⛔ Stranger detected (%.2fs)", latency)
                if self.on_stranger:
                    self.on_stranger()
                self._set_state(ActivationState.LISTENING)

            else:  # no_face
                logger.info("❌ No face detected (%.2fs)", latency)
                if self.on_no_face:
                    self.on_no_face()
                self._set_state(ActivationState.LISTENING)

        except Exception:
            logger.exception("Face verification failed")
            self._set_state(ActivationState.LISTENING)

    def _handle_voice_interaction(self) -> None:
        """Run the voice pipeline after boss verification."""
        if not self._voice_pipeline:
            self._set_state(ActivationState.LISTENING)
            return

        try:
            self._set_state(ActivationState.SPEAKING)
            self._tts.speak("How can I help you?", blocking=True)

            self._set_state(ActivationState.PROCESSING)
            response = self._voice_pipeline.process_voice_command(timeout=10)

            if response:
                logger.info("Voice command completed successfully")
            else:
                self._tts.speak("I didn't hear anything. Try again.", blocking=True)

        except Exception:
            logger.exception("Voice interaction failed")

        # Return to listening
        self._set_state(ActivationState.LISTENING)

    def _set_state(self, new_state: ActivationState) -> None:
        """Update state with logging."""
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.debug("State: %s → %s", old.value, new_state.value)


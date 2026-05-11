"""
Wake Word Detector using OpenWakeWord.

Always-on, low-power wake word detection running on a background thread.
Uses "hey_mycroft" as placeholder until custom "FRIDAY" model is trained.

Memory:  ~50 MB
CPU:     <1% idle
Latency: <200 ms from word end to callback
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger("friday.wake_word")

# Audio constants
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280       # 80ms @ 16kHz — OpenWakeWord's expected frame size
CHANNELS = 1
DTYPE = np.int16


class WakeWordDetector:
    """
    Continuous wake word detection using OpenWakeWord.

    Architecture:
        - Main thread: Controls start/stop
        - Audio thread: PyAudio callback (fast — just enqueues raw bytes)
        - Processing thread: Runs OpenWakeWord CNN inference (~10–20 ms)

    Thread safety is ensured via queue.Queue.
    """

    def __init__(
        self,
        model_name: str = "hey_mycroft",
        sensitivity: float = 0.5,
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Args:
            model_name: OpenWakeWord model name (e.g. "hey_mycroft").
            sensitivity: Detection threshold 0.0–1.0 (lower = more sensitive).
            callback: Function called when wake word detected.
        """
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(f"Sensitivity must be 0.0–1.0, got {sensitivity}")

        self.model_name = model_name
        self.sensitivity = sensitivity
        self.callback = callback

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
        self._running = False
        self._pa = None
        self._stream = None
        self._process_thread: Optional[threading.Thread] = None
        self._model = None

        # Cooldown: prevent rapid re-triggers
        self._last_detection_time = 0.0
        self._cooldown_seconds = 2.0

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for wake word in background threads."""
        if self._running:
            logger.warning("Detector already running")
            return

        # Memory check
        from src.core.memory_manager import memory_manager, PressureLevel
        status = memory_manager.get_status()
        if status.pressure_level == PressureLevel.CRITICAL:
            raise MemoryError(
                f"Cannot start wake word: critical memory pressure "
                f"({status.percent:.1f}% used)"
            )

        # Load OpenWakeWord model
        from openwakeword.model import Model as OWWModel
        self._model = OWWModel(
            wakeword_models=[self.model_name],
            inference_framework="onnx",
        )
        logger.info("OpenWakeWord model loaded: %s", self.model_name)

        # Open PyAudio stream
        import pyaudio
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            stream_callback=self._audio_callback,
        )

        # Start processing thread
        self._running = True
        self._process_thread = threading.Thread(
            target=self._process_loop,
            name="friday-wakeword",
            daemon=True,
        )
        self._process_thread.start()

        self._stream.start_stream()
        logger.info(
            "Wake word detector started (model=%s, sensitivity=%.2f)",
            self.model_name, self.sensitivity,
        )

    def stop(self) -> None:
        """Stop listening gracefully."""
        self._running = False

        # Stop audio stream
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        # Wait for processing thread
        if self._process_thread:
            self._process_thread.join(timeout=2.0)
            self._process_thread = None

        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Wake word detector stopped")

    def set_sensitivity(self, sensitivity: float) -> None:
        """Update detection threshold."""
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(f"Sensitivity must be 0.0–1.0, got {sensitivity}")
        self.sensitivity = sensitivity
        logger.info("Sensitivity updated to %.2f", sensitivity)

    # ── Private ─────────────────────────────────────────────

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio stream callback — runs in audio thread.

        MUST be fast: just converts bytes → numpy and enqueues.
        """
        import pyaudio

        try:
            audio_chunk = np.frombuffer(in_data, dtype=DTYPE)
            self._audio_queue.put_nowait(audio_chunk)
        except queue.Full:
            pass  # Drop frames under heavy load

        return (None, pyaudio.paContinue)

    def _process_loop(self) -> None:
        """
        Processing thread — runs OpenWakeWord inference on each audio chunk.
        """
        while self._running:
            try:
                audio_chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                # Convert to float32 for OpenWakeWord
                audio_f32 = audio_chunk.astype(np.float32) / 32768.0

                # Run prediction
                prediction = self._model.predict(audio_f32)

                # Check confidence for our wake word
                confidence = prediction.get(self.model_name, 0.0)

                if confidence > self.sensitivity:
                    now = time.time()
                    # Cooldown check — prevent rapid re-triggers
                    if now - self._last_detection_time > self._cooldown_seconds:
                        self._last_detection_time = now
                        logger.info(
                            "🎤 Wake word detected! (confidence=%.3f)",
                            confidence,
                        )
                        if self.callback:
                            # Fire callback in separate thread
                            threading.Thread(
                                target=self.callback, daemon=True
                            ).start()

            except Exception:
                logger.exception("Wake word inference error")

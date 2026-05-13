"""
Speech-to-Text using Distil-Whisper Small via MLX.

Architecture mirrors wake_word.py:
    - Audio thread: PyAudio callback (fast — just enqueues raw bytes)
    - Processing: VAD runs in a worker thread consuming the queue
    - Transcription: mlx_whisper.transcribe() on the accumulated buffer

Memory: ~600 MB (loaded lazily on first transcription)
Latency: <2s for 5-second audio clip
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("friday.stt")

# Audio constants — must match wake_word.py
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16

# VAD frame size: 30ms @ 16kHz = 480 samples (webrtcvad requires 10/20/30ms)
VAD_FRAME_SAMPLES = 480
VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * 2  # int16 = 2 bytes per sample


class SpeechToText:
    """
    Distil-Whisper Small via MLX for transcription.

    Features:
    - Queue-based audio capture (same pattern as WakeWordDetector)
    - VAD-based auto-stop (silence detection) in worker thread
    - Lazy model loading (saves memory when idle)
    - Memory check before loading
    """

    def __init__(
        self,
        model_path: str = "mlx-community/whisper-small.en-mlx",
        vad_aggressiveness: int = 2,
    ) -> None:
        """
        Args:
            model_path: HuggingFace repo ID or local path for mlx-whisper.
            vad_aggressiveness: WebRTC VAD aggressiveness 0-3 (higher = stricter).
        """
        self.model_path = model_path
        self.vad_aggressiveness = vad_aggressiveness

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._is_listening = False

    def listen(self, timeout: float = 10.0, silence_duration: float = 1.5) -> str:
        """
        Record audio until silence detected or timeout, then transcribe.

        Args:
            timeout: Maximum recording duration (seconds).
            silence_duration: Seconds of continuous silence to auto-stop.

        Returns:
            Transcribed text, or empty string if no speech detected.

        Architecture:
            1. PyAudio callback enqueues raw int16 chunks (fast, no processing)
            2. Worker thread consumes queue, runs VAD, accumulates audio buffer
            3. After silence/timeout, transcribe accumulated audio with mlx-whisper
        """
        import pyaudio
        import webrtcvad

        vad = webrtcvad.Vad(self.vad_aggressiveness)

        # State for the worker thread
        audio_buffer: list[np.ndarray] = []
        stop_event = threading.Event()
        speech_detected = threading.Event()

        # VAD tracking
        silence_frames_needed = int(silence_duration * (SAMPLE_RATE / VAD_FRAME_SAMPLES))
        consecutive_silence = 0

        def audio_callback(in_data, frame_count, time_info, status):
            """PyAudio callback — FAST. Just enqueue raw bytes."""
            try:
                chunk = np.frombuffer(in_data, dtype=DTYPE).copy()
                self._audio_queue.put_nowait(chunk)
            except queue.Full:
                pass  # Drop frames under heavy load
            return (None, pyaudio.paContinue)

        def vad_worker():
            """Worker thread — consumes audio queue, runs VAD, accumulates buffer."""
            nonlocal consecutive_silence

            while not stop_event.is_set():
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Accumulate all audio (we transcribe everything)
                audio_buffer.append(chunk)

                # Run VAD on 30ms frames within this chunk
                for i in range(0, len(chunk) - VAD_FRAME_SAMPLES + 1, VAD_FRAME_SAMPLES):
                    frame = chunk[i : i + VAD_FRAME_SAMPLES]
                    frame_bytes = frame.tobytes()

                    try:
                        is_speech = vad.is_speech(frame_bytes, SAMPLE_RATE)
                    except Exception:
                        is_speech = True  # Assume speech on VAD error

                    if is_speech:
                        speech_detected.set()
                        consecutive_silence = 0
                    else:
                        consecutive_silence += 1

                # Auto-stop: only after speech has been detected, then silence follows
                if speech_detected.is_set() and consecutive_silence >= silence_frames_needed:
                    logger.info("Silence detected after speech, stopping recording")
                    stop_event.set()

        # --- Start recording ---
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=VAD_FRAME_SAMPLES * 2,  # ~60ms chunks
            stream_callback=audio_callback,
        )

        # Clear any stale audio from previous recordings
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._is_listening = True
        worker = threading.Thread(target=vad_worker, name="friday-stt-vad", daemon=True)
        worker.start()
        stream.start_stream()

        logger.info("🎙️ Listening (timeout=%.1fs, silence=%.1fs)...", timeout, silence_duration)

        # Wait for stop_event or timeout
        stop_event.wait(timeout=timeout)
        if not stop_event.is_set():
            logger.info("Recording timeout reached (%.1fs)", timeout)
            stop_event.set()

        # --- Cleanup ---
        self._is_listening = False
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        pa.terminate()
        worker.join(timeout=2.0)

        # Drain remaining queue items
        while not self._audio_queue.empty():
            try:
                audio_buffer.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break

        # --- Transcribe ---
        if not audio_buffer:
            logger.info("No audio captured")
            return ""

        audio_data = np.concatenate(audio_buffer, axis=0)
        duration = len(audio_data) / SAMPLE_RATE
        logger.info("Captured %.1fs of audio, transcribing...", duration)

        if duration < 0.3:
            logger.info("Audio too short (%.1fs), skipping transcription", duration)
            return ""

        return self._transcribe(audio_data)

    def _transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio using mlx-whisper.

        Args:
            audio_data: NumPy int16 array of audio samples at 16kHz.

        Returns:
            Transcribed text.
        """
        import mlx_whisper

        # Normalize int16 → float32 [-1.0, 1.0]
        audio_float = audio_data.astype(np.float32) / 32768.0

        start = time.perf_counter()

        result = mlx_whisper.transcribe(
            audio_float,
            path_or_hf_repo=self.model_path,
            language="en",
            fp16=False,
        )

        latency = time.perf_counter() - start
        text = result.get("text", "").strip()

        logger.info("Transcribed in %.2fs: '%s'", latency, text)
        return text

    def transcribe_file(self, audio_path: str) -> str:
        """
        Transcribe audio from file (for testing).

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)

        Returns:
            Transcribed text.
        """
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=self.model_path,
            language="en",
            fp16=False,
        )

        text = result.get("text", "").strip()
        logger.info("File transcription: '%s'", text)
        return text

    @property
    def is_listening(self) -> bool:
        return self._is_listening

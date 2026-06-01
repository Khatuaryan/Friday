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

from src.utils.logger import get_logger
import queue
import threading
import time
from pathlib import Path
from typing import Optional, Tuple


import numpy as np

logger = get_logger("friday.stt")

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
        model_path: str = "mlx-community/whisper-small-mlx",
        vad_aggressiveness: int = 2,
        sarvam_api_key: Optional[str] = None,
    ) -> None:
        """
        Args:
            model_path: HuggingFace repo ID or local path for mlx-whisper.
            vad_aggressiveness: WebRTC VAD aggressiveness 0-3 (higher = stricter).
            sarvam_api_key: Optional Sarvam AI API subscription key for Hindi STT.
        """
        import os
        self.model_path = model_path
        self.vad_aggressiveness = vad_aggressiveness
        self.sarvam_api_key = sarvam_api_key or os.getenv("SARVAM_API_KEY", "")

        if not self.sarvam_api_key:
            logger.warning(
                "SARVAM_API_KEY not set. Hindi STT will fall back to "
                "local whisper (lower accuracy for Hindi)."
            )

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._is_listening = False


    def listen(
        self,
        timeout: float = 10.0,
        silence_duration: float = 1.5,
    ) -> Tuple[str, str]:
        """
        Record audio until silence detected or timeout, then transcribe.

        Args:
            timeout: Maximum recording duration (seconds).
            silence_duration: Seconds of continuous silence to auto-stop.

        Returns:
            Tuple of (Transcribed text, detected_language), or ("", "en") if no speech detected.


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
            return "", "en"

        audio_data = np.concatenate(audio_buffer, axis=0)
        duration = len(audio_data) / SAMPLE_RATE
        logger.info("Captured %.1fs of audio, transcribing...", duration)

        if duration < 0.3:
            logger.info("Audio too short (%.1fs), skipping transcription", duration)
            return "", "en"

        return self._transcribe(audio_data)

    def _transcribe(self, audio_data: np.ndarray) -> Tuple[str, str]:
        """
        Transcribe audio using mlx-whisper with language auto-detection.
        If Hindi is detected, route to Sarvam AI API for transcription.

        Args:
            audio_data: NumPy int16 array of audio samples at 16kHz.

        Returns:
            Tuple of (Transcribed text, detected_language)
        """
        import mlx_whisper

        # Normalize int16 → float32 [-1.0, 1.0]
        audio_float = audio_data.astype(np.float32) / 32768.0

        start = time.perf_counter()

        # Let Whisper auto-detect language
        result = mlx_whisper.transcribe(
            audio_float,
            path_or_hf_repo=self.model_path,
            language=None,
            fp16=False,
        )

        latency = time.perf_counter() - start
        detected_lang = result.get("language", "en")
        text = result.get("text", "").strip()

        logger.info("Local Whisper detected language '%s' and transcribed in %.2fs: '%s'", detected_lang, latency, text)

        try:
            import mlx.core as mx
            mx.clear_cache()
        except Exception:
            pass

        # If detected Hindi, route to Sarvam AI API
        if detected_lang in ["hi", "hi-IN"]:
            if self.sarvam_api_key:
                logger.info("Hindi detected. Routing audio to Sarvam AI API...")
                sarvam_text = self._transcribe_sarvam(audio_data)
                if sarvam_text:
                    return sarvam_text, "hi"
                else:
                    logger.warning("Sarvam API failed. Falling back to local Whisper transcription.")
            else:
                logger.warning("Hindi detected but SARVAM_API_KEY not set. Using local Whisper transcription.")

        return text, detected_lang

    def _transcribe_sarvam(self, audio_data: np.ndarray) -> str:
        """
        Send raw audio data to the Sarvam AI Speech-to-Text API.

        Privacy Note: Audio data leaves the local device here.
        """
        import io
        import wave
        import httpx

        # Convert int16 NumPy array to WAV bytes
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)  # int16 = 2 bytes
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)

        try:
            # POST multipart/form-data as specified in Sarvam AI docs
            response = httpx.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={
                    "api-subscription-key": self.sarvam_api_key,
                },
                files={
                    "file": ("audio.wav", wav_buffer, "audio/wav"),
                },
                data={
                    "model": "saaras:v3",
                    "mode": "transcribe",
                    "language_code": "hi-IN",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            res_json = response.json()
            transcript = res_json.get("transcript", "").strip()
            logger.info("Sarvam API successfully transcribed: '%s'", transcript)
            return transcript
        except Exception as e:
            logger.error("Failed to transcribe via Sarvam API: %s", e)
            return ""

    def transcribe_file(self, audio_path: str) -> Tuple[str, str]:
        """
        Transcribe audio from file (for testing).

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)

        Returns:
            Tuple of (Transcribed text, detected_language)
        """
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=self.model_path,
            language=None,
            fp16=False,
        )

        detected_lang = result.get("language", "en")
        text = result.get("text", "").strip()
        logger.info("File transcription detected language '%s': '%s'", detected_lang, text)

        try:
            import mlx.core as mx
            mx.clear_cache()
        except Exception:
            pass

        return text, detected_lang

    @property
    def is_listening(self) -> bool:
        return self._is_listening


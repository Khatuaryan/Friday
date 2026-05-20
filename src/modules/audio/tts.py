"""
Text-to-Speech — macOS `say` command.

Phase 3 implementation: uses macOS native `say` as primary TTS engine.
Zero additional memory overhead. Queue-based to prevent overlapping speech.
Thread-safe via Lock.

Piper TTS can be added later as an upgrade (separate PR).
"""

from __future__ import annotations

import logging
import queue
import subprocess
import threading

logger = logging.getLogger("friday.tts")


class TextToSpeech:
    """
    TTS using macOS `say` command.

    Features:
    - Queue-based: only one utterance at a time
    - Thread-safe: Lock protects worker spawning
    - Zero memory overhead
    - Configurable voice and rate
    """

    def __init__(
        self,
        voice: str = "Samantha",
        rate: int = 180,
    ) -> None:
        """
        Args:
            voice: macOS voice name (e.g. "Samantha", "Alex", "Daniel").
            rate: Words per minute (default: 180).
        """
        self.voice = voice
        self.rate = rate

        self._queue: queue.Queue[str] = queue.Queue()
        self._speaking = False
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._preempted = False

    def reset_preempt(self) -> None:
        """Reset preemption flag to allow new speech."""
        self._preempted = False

    def preempt(self) -> None:
        """Set preemption flag and stop speech."""
        self._preempted = True
        self.stop()

    def speak(self, text: str, blocking: bool = True) -> None:
        """
        Speak text aloud.

        Args:
            text: Text to speak.
            blocking: If True, wait for speech to finish.
        """
        if self._preempted:
            logger.warning("Speech blocked due to active preemption: '%s'", text[:50] + "..." if len(text) > 50 else text)
            return

        if not text or not text.strip():
            return

        self._queue.put(text.strip())

        with self._lock:
            if not self._speaking:
                self._speaking = True
                worker = threading.Thread(
                    target=self._speech_worker,
                    name="friday-tts",
                    daemon=True,
                )
                worker.start()

        if blocking:
            self._queue.join()

    def _speech_worker(self) -> None:
        """Worker thread — processes speech queue sequentially."""
        while True:
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                break

            if self._stop_flag.is_set():
                self._queue.task_done()
                continue

            try:
                self._speak_macos(text)
            except Exception:
                logger.exception("TTS speech error")
            finally:
                self._queue.task_done()

        with self._lock:
            self._speaking = False

    def _speak_macos(self, text: str) -> None:
        """Speak using macOS built-in `say` command."""
        # Prevent speaking massive hallucinations
        if len(text) > 1000:
            logger.warning("TTS text too long (%d chars), truncating to 1000", len(text))
            text = text[:1000] + "... and so on."

        # Sanitize text for shell safety (say accepts stdin too)
        cmd = ["say", "-v", self.voice, "-r", str(self.rate)]

        try:
            subprocess.run(
                cmd,
                input=text,
                text=True,
                check=True,
                timeout=300, # Increased from 60 to 300
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            logger.warning("macOS `say` timed out after 300s")
        except subprocess.CalledProcessError as e:
            logger.error("macOS `say` failed: %s", e.stderr)
        except FileNotFoundError:
            logger.error("macOS `say` command not found — is this macOS?")

    def stop(self) -> None:
        """Stop current speech and clear queue."""
        self._stop_flag.set()
        self._preempted = True

        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        # Kill any running say process
        try:
            subprocess.run(["killall", "say"], capture_output=True, timeout=2)
        except Exception:
            pass

        self._stop_flag.clear()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

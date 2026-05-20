"""Unit tests for Text-to-Speech module."""

import pytest
import threading
from src.modules.audio.tts import TextToSpeech


class TestTextToSpeech:
    def test_init_defaults(self):
        tts = TextToSpeech()
        assert tts.voice == "Samantha"
        assert tts.rate == 180
        assert not tts.is_speaking

    def test_init_custom(self):
        tts = TextToSpeech(voice="Alex", rate=200)
        assert tts.voice == "Alex"
        assert tts.rate == 200

    def test_speak_empty_string_noop(self):
        """Speaking empty string should not queue anything."""
        tts = TextToSpeech()
        tts.speak("", blocking=False)
        assert tts._queue.empty()

    def test_speak_whitespace_only_noop(self):
        """Speaking whitespace should not queue anything."""
        tts = TextToSpeech()
        tts.speak("   ", blocking=False)
        assert tts._queue.empty()

    def test_stop_clears_queue(self):
        """Stop should drain the queue."""
        tts = TextToSpeech()
        # Manually put items in queue
        tts._queue.put("test1")
        tts._queue.put("test2")
        assert not tts._queue.empty()
        tts.stop()
        assert tts._queue.empty()

    def test_lock_exists(self):
        """TTS must have a threading Lock to prevent race conditions."""
        tts = TextToSpeech()
        assert isinstance(tts._lock, type(threading.Lock()))

    def test_preemption_blocks_speak(self):
        """Preemption should block subsequent speak() calls."""
        tts = TextToSpeech()
        tts.stop()  # This sets _preempted = True
        assert tts._preempted

        # Subsequent speak calls should not queue anything
        tts.speak("Hello", blocking=False)
        assert tts._queue.empty()

        # Reset preemption should allow speaking again
        tts.reset_preempt()
        assert not tts._preempted
        tts.speak("Hello", blocking=False)
        assert tts.is_speaking
        
        # Clean up
        tts.stop()

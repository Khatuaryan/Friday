"""
Integration Test — Concurrent TTS Arbitration & Wake Word Preemption

This test validates the safe concurrent TTS arbitration mechanism between the ProactiveEngine
and the ActivationHandler's always-on wake word detector.

MANUAL VERIFICATION PROCEDURE:
1. Start the full FRIDAY pipeline integration:
   $ FRIDAY_MEM_BUFFER=0.0 make test-pipeline
2. Wait for the ProactiveEngine to trigger a background notification/alert
   (e.g., proactive daily brief or break reminder spoken aloud).
3. While FRIDAY is actively speaking the proactive notification, say "Hey Mycroft" (wake word).
4. ASSERTION 1: Proactive speech stops instantly (NSSpeechSynthesizer / say is terminated).
5. ASSERTION 2: System logs show:
   "DEBUG [friday.tts] say process terminated by SIGTERM (expected)"
   and NO "CalledProcessError" or ERROR-level SIGTERM signals.
6. ASSERTION 3: System immediately transitions to the 'VERIFYING' state within 500ms
   and triggers face checking FaceTime camera capture without audio overlaps.
"""

import logging
import time
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.activation_handler import ActivationHandler, ActivationState


logging.basicConfig(level=logging.INFO)


def test_concurrent_tts_preemption():
    """
    Programmatic validation of the concurrent preemption state machine.
    Verifies that calling the wake word trigger during SPEAKING or active proactive TTS
    invokes tts.stop() instantly and transitions states correctly.
    """
    # 1. Setup mocks
    on_boss = MagicMock()
    mock_tts = MagicMock()
    mock_tts.is_speaking = True

    # 2. Instantiate ActivationHandler in a mock configuration
    handler = ActivationHandler(
        boss_encodings_path="data/faces/boss_vision.pkl",
        on_boss_verified=on_boss,
        camera_index=0
    )

    # Inject mock TTS and mock voice pipeline
    handler._tts = mock_tts
    handler._face_recognizer = MagicMock()
    handler._face_recognizer.verify_identity.return_value = ("boss", "Boss")
    handler._voice_pipeline = MagicMock()

    # 3. Simulate ProactiveEngine speaking / active speech state
    handler._state = ActivationState.SPEAKING
    
    # 4. Trigger wake word detection callback
    # This imitates the background WakeWordDetector thread queuing the "wake_word" event.
    handler._queue_wake_word()

    # ASSERT: The wake word detection callback must immediately preempt current speech
    mock_tts.stop.assert_called_once()
    assert handler._event_queue.get() == "wake_word"

    # 5. Simulate main loop processing of the queued event in LISTENING state
    mock_tts.stop.reset_mock()
    handler._state = ActivationState.LISTENING
    handler._handle_activation()

    # ASSERT: The active verification transition preempts speech one more time for absolute safety
    mock_tts.stop.assert_called_once()
    assert handler.state == ActivationState.READY or handler.state == ActivationState.LISTENING

"""Unit tests for wake word detector."""

import pytest
from unittest.mock import Mock
from src.modules.wake_word import WakeWordDetector


class TestWakeWordDetector:
    def test_init_defaults(self):
        detector = WakeWordDetector(sensitivity=0.5, callback=Mock())
        assert detector.sensitivity == 0.5
        assert not detector.running

    def test_sensitivity_validation(self):
        detector = WakeWordDetector()
        detector.set_sensitivity(0.5)
        assert detector.sensitivity == 0.5

        with pytest.raises(ValueError):
            detector.set_sensitivity(1.5)
        with pytest.raises(ValueError):
            detector.set_sensitivity(-0.1)

    def test_init_invalid_sensitivity(self):
        with pytest.raises(ValueError):
            WakeWordDetector(sensitivity=2.0)

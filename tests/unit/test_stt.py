"""Unit tests for Speech-to-Text module."""

import pytest
from src.modules.audio.stt import SpeechToText, SAMPLE_RATE, VAD_FRAME_SAMPLES


class TestSpeechToText:
    def test_init_defaults(self):
        stt = SpeechToText()
        assert stt.model_path == "mlx-community/whisper-small.en-mlx"
        assert stt.vad_aggressiveness == 2
        assert not stt.is_listening

    def test_init_custom_model_path(self):
        stt = SpeechToText(model_path="models/custom-whisper")
        assert stt.model_path == "models/custom-whisper"

    def test_init_vad_aggressiveness(self):
        stt = SpeechToText(vad_aggressiveness=3)
        assert stt.vad_aggressiveness == 3

    def test_audio_constants(self):
        """Verify audio constants are correct for webrtcvad."""
        assert SAMPLE_RATE == 16000
        # 30ms @ 16kHz = 480 samples
        assert VAD_FRAME_SAMPLES == 480
        # int16 = 2 bytes per sample
        assert VAD_FRAME_SAMPLES * 2 == 960  # VAD_FRAME_BYTES

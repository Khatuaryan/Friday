#!/usr/bin/env python3
"""
Integration test: Voice Pipeline (Phase 3).

Tests the STT → (placeholder Brain) → TTS loop standalone,
WITHOUT wake word or face recognition.

Usage:
    python tests/integration/pipeline_v2_voice.py
    make test-voice-pipeline
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test.pipeline_v2")

from src.modules.audio.stt import SpeechToText
from src.modules.audio.tts import TextToSpeech
from src.modules.voice_pipeline import VoicePipeline


def test_voice_pipeline():
    """Test the STT → (placeholder) → TTS loop."""
    print("=" * 60)
    print("F.R.I.D.A.Y. — Voice Pipeline Integration Test (v2)")
    print("=" * 60)
    print()

    # Initialize components
    stt = SpeechToText()
    tts = TextToSpeech()
    pipeline = VoicePipeline(stt=stt, tts=tts, brain=None)

    # Run 3 interaction cycles
    for cycle in range(1, 4):
        print(f"\n--- Cycle {cycle}/3 ---")

        tts.speak(f"Cycle {cycle}. Please say something.", blocking=True)
        time.sleep(0.3)

        start = time.perf_counter()
        response = pipeline.process_voice_command(timeout=8)
        elapsed = time.perf_counter() - start

        if response:
            print(f"✅ Round-trip completed in {elapsed:.2f}s")
            print(f"   Response: \"{response}\"")
        else:
            print(f"⚠️ No speech detected in cycle {cycle} ({elapsed:.2f}s)")

        time.sleep(1)

    print()
    print("=" * 60)
    print("Voice pipeline integration test complete.")
    print("=" * 60)


def test_memory_impact():
    """Check memory impact of STT + TTS."""
    print("\n--- Memory Impact ---")

    from src.memory.manager import memory_manager

    status = memory_manager.get_status()
    print(f"System: {status.used_gb:.2f}/{status.total_gb:.1f} GB "
          f"({status.percent:.1f}%)")
    print(f"FRIDAY RSS: {status.friday_rss_gb:.2f} GB")
    print(f"Pressure: {status.pressure_level.value}")


if __name__ == "__main__":
    test_voice_pipeline()
    test_memory_impact()

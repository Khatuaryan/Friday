#!/usr/bin/env python3
"""
Manual test: Speech-to-Text standalone.

Records 5 seconds of audio, transcribes with Distil-Whisper via MLX.
First run will download the model (~500 MB).

Usage:
    python tests/unit/manual_test_stt.py
    make test-stt
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from src.modules.audio.stt import SpeechToText


def main():
    print("=" * 60)
    print("F.R.I.D.A.Y. — Manual STT Test")
    print("=" * 60)
    print()

    stt = SpeechToText()

    print("🎙️ Say something clearly (5 second timeout, 1.5s silence auto-stop)...")
    print("   Speak after the 'Listening' message appears.")
    print()
    time.sleep(1)

    start = time.perf_counter()
    listen_result = stt.listen(timeout=5, silence_duration=1.5)
    if isinstance(listen_result, tuple):
        text, lang = listen_result
    else:
        text, lang = listen_result, "en"
    elapsed = time.perf_counter() - start

    print()
    if text:
        print(f"✅ Transcribed in {elapsed:.2f}s [lang={lang}]:")
        print(f"   \"{text}\"")
    else:
        print(f"❌ No speech detected ({elapsed:.2f}s elapsed)")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()

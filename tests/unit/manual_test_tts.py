#!/usr/bin/env python3
"""
Manual test: Text-to-Speech standalone.

Tests macOS `say` command with different phrases.

Usage:
    python tests/unit/manual_test_tts.py
    make test-tts
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from src.modules.audio.tts import TextToSpeech


def main():
    print("=" * 60)
    print("F.R.I.D.A.Y. — Manual TTS Test")
    print("=" * 60)
    print()

    tts = TextToSpeech()

    tests = [
        ("Short phrase", "Hello Boss."),
        ("Medium sentence", "I am FRIDAY, your personal AI assistant running locally on this Mac."),
        ("Numbers and punctuation", "Your battery is at 72%. You have 3 meetings today at 9 AM, 1 PM, and 4:30 PM."),
        ("Long response", "Based on your calendar, you have a busy morning. "
            "Your first meeting starts in 30 minutes. "
            "Would you like me to prepare a summary?"),
    ]

    for i, (label, text) in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {label}")
        print(f"   Text: \"{text}\"")

        start = time.perf_counter()
        tts.speak(text, blocking=True)
        elapsed = time.perf_counter() - start

        print(f"   ✅ Spoken in {elapsed:.2f}s")
        print()
        time.sleep(0.5)

    print("=" * 60)
    print("All TTS tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()

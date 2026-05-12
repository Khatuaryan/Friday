#!/usr/bin/env python3
"""
Manual test for wake word detection.

Tests:
    1. Normal speech from 1m
    2. Quiet speech
    3. With background music
    4. Similar words (should NOT trigger)
    5. Rapid repetition

Usage:
    python scripts/test_wake_word.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.wake_word import WakeWordDetector


def on_detected():
    print(f"\n🎤 WAKE WORD DETECTED at {time.strftime('%H:%M:%S')}")


def main():
    # Set wake_word module logger to DEBUG to show near-misses
    import logging
    logging.getLogger("friday.wake_word").setLevel(logging.DEBUG)

    print("\n" + "=" * 50)
    print("Wake Word Detection Test")
    print("=" * 50)
    print("\nUsing placeholder: 'Hey Mycroft'")
    print("(Custom 'FRIDAY' model training is optional)")
    print("\nTests to perform:")
    print("  1. Say 'Hey Mycroft' at normal volume")
    print("  2. Whisper 'Hey Mycroft'")
    print("  3. Say with TV/music in background")
    print("  4. Say similar words: 'Friday', 'Buddy', 'Hey Siri'")
    print("  5. Say wake word 5 times rapidly")
    print("\nPress Ctrl+C to stop\n")

    detector = WakeWordDetector(callback=on_detected, sensitivity=0.5)
    detector.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        detector.stop()
        print("Done.")


if __name__ == "__main__":
    main()

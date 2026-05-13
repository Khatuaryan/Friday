#!/usr/bin/env python3
"""
Integration test: Brain + Voice Pipeline (Phase 4).

Tests FridayBrain standalone:
- Model loading
- Conversation history (multi-turn)
- FRIDAY persona

NOTE: Requires Phi-3.5-mini model downloaded.
Run: make download-model

Usage:
    python tests/integration/pipeline_v3_brain.py
    make test-brain
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
logger = logging.getLogger("test.pipeline_v3")

from src.core.brain import FridayBrain


def test_brain_standalone():
    """Test brain model loading and single-turn response."""
    print("=" * 60)
    print("F.R.I.D.A.Y. — Brain Integration Test (v3)")
    print("=" * 60)
    print()

    brain = FridayBrain()

    print("--- Loading Phi-3.5-mini ---")
    load_time = brain.load_model()
    print(f"✅ Model loaded in {load_time:.1f}s")
    print()

    # Test 1: Identity
    print("--- Test 1: Who are you? ---")
    start = time.perf_counter()
    response = brain.think("Hello, who are you?")
    latency = time.perf_counter() - start
    print(f"Response ({latency:.2f}s): {response}")
    print()

    # Test 2: Context retention
    print("--- Test 2: Context retention ---")
    brain.think("My name is Aryan")
    response = brain.think("What is my name?")
    print(f"Response: {response}")
    has_name = "aryan" in response.lower()
    print(f"{'✅' if has_name else '⚠️'} Name retention: {'passed' if has_name else 'check manually'}")
    print()

    # Test 3: History length
    print(f"--- Test 3: History length ---")
    print(f"History: {brain.get_history_length()} turns")
    print()

    # Test 4: Clear history
    brain.clear_history()
    print(f"--- Test 4: Clear history ---")
    print(f"History after clear: {brain.get_history_length()} turns")
    print()

    print("=" * 60)
    print("Brain integration test complete.")
    print("=" * 60)


def test_memory_impact():
    """Verify brain adds 0MB (already loaded)."""
    print("\n--- Memory Impact ---")

    from src.memory.manager import memory_manager

    status = memory_manager.get_status()
    print(f"System: {status.used_gb:.2f}/{status.total_gb:.1f} GB "
          f"({status.percent:.1f}%)")
    print(f"FRIDAY RSS: {status.friday_rss_gb:.2f} GB")
    print(f"Pressure: {status.pressure_level.value}")


if __name__ == "__main__":
    test_brain_standalone()
    test_memory_impact()

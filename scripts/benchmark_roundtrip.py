#!/usr/bin/env python3
"""
F.R.I.D.A.Y. End-to-End Latency Benchmark

Programmatically profiles key components of the voice pipeline round-trip:
1. Speech-to-Text (STT) transcription speed over a standard audio sample.
2. FridayBrain inference latency (with and without calendar tool execution).

Also details manual stopwatch checkpoints for full pipeline steps.
"""

import os
import sys
import time
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force memory buffer override to guarantee model loading
os.environ["FRIDAY_MEM_BUFFER"] = "0.0"

SAMPLE_RATE = 16000


def benchmark_stt():
    """Benchmark STT transcription latency on synthetic silent wave buffer."""
    print("\n--- Benchmarking STT transcription speed ---")
    from src.modules.audio.stt import SpeechToText
    
    stt = SpeechToText()
    
    # 5 seconds of synthetic audio
    audio = np.zeros(SAMPLE_RATE * 5, dtype=np.int16)
    
    # Warmup
    print("Performing transcription warmup...")
    _ = stt._transcribe(audio)
    
    # Run
    print("Measuring 3 runs...")
    latencies = []
    for i in range(3):
        start = time.perf_counter()
        _ = stt._transcribe(audio)
        latencies.append(time.perf_counter() - start)
        print(f"  Run {i+1}: {latencies[-1]:.3f}s")
        
    avg = sum(latencies) / len(latencies)
    print(f"👉 Average STT Latency (5s clip): {avg:.3f}s (Real-Time Factor: {5.0 / avg:.2f}x)")
    return avg


def benchmark_brain():
    """Benchmark brain response latencies with and without tool calling."""
    print("\n--- Benchmarking FridayBrain inference speed ---")
    from src.core.brain import FridayBrain
    
    brain = FridayBrain()
    brain.load_model()
    
    # Test 1: Simple conversational turn (No tool calling)
    print("Measuring conversational response (No tool call)...")
    start = time.perf_counter()
    _ = brain.think_full("Hello! How are you doing today?")
    no_tool_lat = time.perf_counter() - start
    print(f"👉 Latency (No tool): {no_tool_lat:.3f}s")
    
    # Test 2: Calendar query (Requires 1 tool call)
    print("Measuring tool response (Requires Calendar check)...")
    start = time.perf_counter()
    _ = brain.think_full("What meetings do I have today?")
    tool_lat = time.perf_counter() - start
    print(f"👉 Latency (With tool): {tool_lat:.3f}s")
    
    return no_tool_lat, tool_lat


if __name__ == "__main__":
    print("============================================================")
    print("F.R.I.D.A.Y. Voice Pipeline Latency Profiler")
    print("============================================================")
    
    stt_latency = benchmark_stt()
    no_tool_latency, tool_latency = benchmark_brain()
    
    print("\n" + "="*60)
    print("LATENCY SUMMARY REPORT")
    print("="*60)
    print(f"1. Speech-to-Text (5s Audio):  {stt_latency:.2f}s")
    print(f"2. Brain turn (No tool call):   {no_tool_latency:.2f}s")
    print(f"3. Brain turn (With Calendar):  {tool_latency:.2f}s")
    print("\nMANUAL MEASUREMENTS REQUIRED (Use live make test-pipeline):")
    print("4. Face Verification:          _____ ms (Stopwatch from camera start to verification)")
    print("5. TTS Playback Start Latency: _____ ms (Stopwatch from brain reply to NSSpeech speaker)")
    print("="*60)

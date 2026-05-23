#!/usr/bin/env python3
"""
F.R.I.D.A.Y. Soak Test — Memory Leak Profiler

Simulates a light operational load and records Resident Set Size (RSS) memory every 30 seconds.
Detects memory creep > 50MB from baseline.

Usage:
    python scripts/soak_test.py --duration 4 --interval 300
    python scripts/soak_test.py --duration 0.05 --interval 10  # quick 3-minute validation run
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_soak(duration_hours: float, event_interval: int):
    process = psutil.Process(os.getpid())
    results = []

    # Import FRIDAY subsystems to monitor
    from src.memory.manager import memory_manager
    from src.memory.store import MemoryStore
    from src.tools.server import MCPToolServer

    store = MemoryStore()
    tool_server = MCPToolServer()

    baseline_rss = process.memory_info().rss / (1024 ** 2)
    print(f"Baseline RSS: {baseline_rss:.1f} MB")
    print(f"Running soak test for {duration_hours}h ({event_interval}s event intervals)...")
    print("Close the IDE before running for clean measurements.\n")

    start = time.time()
    end = start + (duration_hours * 3600)
    last_event = 0

    while time.time() < end:
        rss_mb = process.memory_info().rss / (1024 ** 2)
        drift = rss_mb - baseline_rss
        timestamp = datetime.now().strftime("%H:%M:%S")

        results.append({
            "timestamp": timestamp,
            "rss_mb": rss_mb,
            "drift_mb": drift,
        })

        print(
            f"[{timestamp}] RSS: {rss_mb:.1f} MB | Drift: {drift:+.1f} MB" +
            (" ⚠️ LEAK SUSPECTED" if drift > 50 else "")
        )

        # Simulate periodic work (tool call + memory search)
        now = time.time()
        if now - last_event >= event_interval:
            try:
                store.add_conversation_turn("user", "soak test message")
                store.search("soak test query", limit=1)
                tool_server.execute_tool({
                    "name": "get_system_info",
                    "arguments": {"info_type": "memory"},
                })
            except Exception as e:
                print(f"  [EVENT ERROR] {e}")
            last_event = now

        time.sleep(30)  # Record every 30 seconds

    # Summary calculations
    max_rss = max(r["rss_mb"] for r in results)
    max_drift = max(r["drift_mb"] for r in results)
    final_drift = results[-1]["drift_mb"]

    print(f"\n{'='*50}")
    print(f"SOAK TEST COMPLETE ({duration_hours}h)")
    print(f"Baseline RSS:   {baseline_rss:.1f} MB")
    print(f"Peak RSS:       {max_rss:.1f} MB")
    print(f"Max drift:      {max_drift:+.1f} MB")
    print(f"Final drift:    {final_drift:+.1f} MB")
    print(f"Status: {'✅ STABLE (<50MB drift)' if max_drift < 50 else '❌ POSSIBLE LEAK (>50MB drift)'}")

    # Write results to research documentation directory
    output = PROJECT_ROOT / "docs" / "research-paper" / "benchmarks" / "soak-test.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, "w") as f:
        f.write(f"FRIDAY Soak Test — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Duration: {duration_hours}h | Interval: {event_interval}s\n")
        f.write(f"Baseline RSS: {baseline_rss:.1f} MB\n")
        f.write(f"Peak RSS: {max_rss:.1f} MB\n")
        f.write(f"Max Drift: {max_drift:+.1f} MB\n")
        f.write(f"Final Drift: {final_drift:+.1f} MB\n")
        f.write(f"Status: {'STABLE' if max_drift < 50 else 'POSSIBLE LEAK'}\n\n")
        f.write("timestamp,rss_mb,drift_mb\n")
        for r in results:
            f.write(f"{r['timestamp']},{r['rss_mb']:.1f},{r['drift_mb']:+.1f}\n")

    print(f"Results successfully written to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()
    run_soak(args.duration, args.interval)

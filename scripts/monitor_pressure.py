#!/usr/bin/env python3
"""
Real-time memory pressure monitor for 8GB system.

Continuously displays FRIDAY's RAM usage and system pressure.
Alerts when approaching memory limits.

Usage:
    python scripts/monitor_pressure.py
    python scripts/monitor_pressure.py --interval 5  # Check every 5s
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def monitor(interval: float = 10.0):
    """Continuously monitor memory pressure."""
    from src.memory.manager import memory_manager

    print("\n" + "=" * 60)
    print("F.R.I.D.A.Y. Memory Pressure Monitor")
    print("=" * 60)
    print(f"Check interval: {interval}s")
    print("Press Ctrl+C to stop\n")

    BARS = 30  # Width of progress bar

    try:
        while True:
            status = memory_manager.get_status()

            # Build visual bar
            filled = int(BARS * status.percent / 100)
            bar = "█" * filled + "░" * (BARS - filled)

            # Color indicator
            if status.pressure_level.value == "critical":
                icon = "🔴"
            elif status.pressure_level.value == "warning":
                icon = "🟡"
            else:
                icon = "🟢"

            print(
                f"\r{icon} [{bar}] {status.percent:.1f}% | "
                f"FRIDAY: {status.friday_rss_gb:.2f}GB | "
                f"Avail: {status.available_gb:.1f}GB | "
                f"{status.pressure_level.value.upper():<8}",
                end="", flush=True,
            )

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")


def main():
    parser = argparse.ArgumentParser(description="Memory pressure monitor")
    parser.add_argument(
        "--interval", type=float, default=10.0,
        help="Check interval in seconds (default: 10)",
    )
    args = parser.parse_args()
    monitor(args.interval)


if __name__ == "__main__":
    main()

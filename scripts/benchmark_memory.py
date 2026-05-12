#!/usr/bin/env python3
"""
Benchmark memory usage for 8GB system.

Tests each component individually and reports:
    1. Baseline (Python only)
    2. + Memory manager
    3. + Phi-3.5-mini loaded
    4. Final total vs budget

Usage:
    python scripts/benchmark_memory.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_memory_mb() -> float:
    """Current process memory (RSS) in MB."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 ** 2)


def get_system_info() -> dict:
    """Get system memory info."""
    vm = psutil.virtual_memory()
    return {
        "total_gb": vm.total / (1024 ** 3),
        "available_gb": vm.available / (1024 ** 3),
        "used_percent": vm.percent,
    }


def benchmark():
    """Run full memory benchmark."""
    print("\n" + "=" * 60)
    print("F.R.I.D.A.Y. Memory Benchmark (8GB System)")
    print("=" * 60)

    sys_info = get_system_info()
    print(f"\nSystem: {sys_info['total_gb']:.1f} GB total, "
          f"{sys_info['available_gb']:.1f} GB available "
          f"({sys_info['used_percent']:.1f}% used)")

    results = []

    # ── 1. Baseline ──
    baseline = get_memory_mb()
    results.append(("Baseline (Python)", baseline))
    print(f"\n1. Baseline:        {baseline:>8.1f} MB")

    # ── 2. Memory Manager ──
    from src.memory.manager import memory_manager
    status = memory_manager.get_status()
    after_mm = get_memory_mb()
    results.append(("+ Memory Manager", after_mm))
    print(f"2. + MemoryManager: {after_mm:>8.1f} MB  (Δ {after_mm - baseline:.1f})")
    print(f"   Pressure: {status.pressure_level.value}")

    # ── 3. Phi-3.5-mini ──
    model_path = PROJECT_ROOT / "models" / "phi-3.5-mini-4bit"
    if model_path.exists():
        print("\n3. Loading Phi-3.5-mini (this takes ~5s)...")
        start = time.time()
        from mlx_lm import load
        model, tokenizer = load(str(model_path))
        load_time = time.time() - start

        after_llm = get_memory_mb()
        results.append(("+ Phi-3.5-mini", after_llm))
        print(f"   + Phi-3.5-mini:  {after_llm:>8.1f} MB  "
              f"(Δ {after_llm - after_mm:.1f}, loaded in {load_time:.1f}s)")

        # Clean up
        del model, tokenizer
    else:
        print("\n3. ⏭️  Phi-3.5-mini not downloaded yet — skipping")
        after_llm = after_mm

    # ── Summary ──
    friday_total = after_llm
    budget = 3500  # 3.5 GB in MB

    print("\n" + "─" * 60)
    print("SUMMARY")
    print("─" * 60)
    print(f"{'Component':<25} {'RAM (MB)':>10} {'Cumulative':>12}")
    print("─" * 60)
    for name, val in results:
        print(f"{name:<25} {val:>10.1f} {'':>12}")
    print("─" * 60)
    print(f"{'FRIDAY Total':<25} {friday_total:>10.1f} MB")
    print(f"{'Budget':<25} {budget:>10.1f} MB")
    print(f"{'Remaining':<25} {budget - friday_total:>10.1f} MB")
    print("─" * 60)

    if friday_total < budget:
        print(f"\n✅ Within budget ({friday_total:.0f} / {budget} MB)")
    else:
        print(f"\n❌ OVER BUDGET by {friday_total - budget:.0f} MB!")

    # System state after
    sys_after = get_system_info()
    print(f"\nSystem after: {sys_after['available_gb']:.1f} GB available "
          f"({sys_after['used_percent']:.1f}% used)")

    status_after = memory_manager.get_status()
    print(f"Pressure: {status_after.pressure_level.value.upper()}")

    # ── Save results ──
    results_dir = PROJECT_ROOT / "docs" / "research-paper" / "benchmarks"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / "phase0-memory-8gb.txt"

    with open(results_file, "w") as f:
        f.write(f"FRIDAY Memory Benchmark — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"System: {sys_info['total_gb']:.1f} GB RAM\n")
        f.write(f"FRIDAY Total: {friday_total:.1f} MB\n")
        f.write(f"Budget: {budget} MB\n")
        f.write(f"Status: {'PASS' if friday_total < budget else 'FAIL'}\n")
        f.write(f"Pressure: {status_after.pressure_level.value}\n")

    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    benchmark()

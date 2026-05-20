"""
Memory Manager for 8GB Systems.

Monitors total system RAM usage, tracks FRIDAY's RAM consumption,
detects memory pressure levels, triggers cleanup when needed,
and prevents the system from swapping to disk.

Thresholds:
    Normal:   <75% system RAM used (< 6.0 GB / 8.0 GB)
    Warning:  75–85% system RAM used (6.0–6.8 GB / 8.0 GB)
    Critical: >85% system RAM used (> 6.8 GB / 8.0 GB)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

import psutil
import yaml

logger = logging.getLogger("friday.memory_manager")


class PressureLevel(str, Enum):
    """System memory pressure levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MemoryStatus:
    """Snapshot of current memory state."""
    total_gb: float
    available_gb: float
    used_gb: float
    percent: float
    friday_rss_gb: float
    pressure_level: PressureLevel
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return (
            f"System: {self.used_gb:.2f}/{self.total_gb:.1f} GB ({self.percent:.1f}%) | "
            f"FRIDAY: {self.friday_rss_gb:.2f} GB | "
            f"Pressure: {self.pressure_level.value.upper()}"
        )


class MemoryManager:
    """
    Monitors and enforces memory limits for an 8 GB system.

    Usage:
        from src.memory.manager import memory_manager

        status = memory_manager.get_status()
        if status.pressure_level == PressureLevel.CRITICAL:
            # take corrective action
            ...
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        friday_budget_gb: float = 3.5,
        warning_threshold: float = 0.75,
        critical_threshold: float = 0.85,
        check_interval: float = 30.0,
    ) -> None:
        # Load from YAML config if provided
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            hw = cfg.get("hardware", {})
            friday_budget_gb = hw.get("friday_budget_gb", friday_budget_gb)
            warning_threshold = hw.get("warning_threshold", warning_threshold)
            critical_threshold = hw.get("critical_threshold", critical_threshold)
            mem_cfg = cfg.get("memory", {})
            check_interval = mem_cfg.get("check_interval_seconds", check_interval)

        self.friday_budget_gb = friday_budget_gb
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.check_interval = check_interval

        self._process = psutil.Process(os.getpid())
        self._running = False
        self._thread: threading.Thread | None = None
        self._callbacks: list[Callable[[MemoryStatus], None]] = []
        self._last_status: MemoryStatus | None = None

    # ── Public API ──────────────────────────────────────────

    def get_status(self) -> MemoryStatus:
        """Get current memory state as a snapshot."""
        vm = psutil.virtual_memory()
        friday_rss = self._process.memory_info().rss / (1024 ** 3)

        percent = vm.percent
        if percent >= self.critical_threshold * 100:
            pressure = PressureLevel.CRITICAL
        elif percent >= self.warning_threshold * 100:
            pressure = PressureLevel.WARNING
        else:
            pressure = PressureLevel.NORMAL

        status = MemoryStatus(
            total_gb=vm.total / (1024 ** 3),
            available_gb=vm.available / (1024 ** 3),
            used_gb=vm.used / (1024 ** 3),
            percent=percent,
            friday_rss_gb=friday_rss,
            pressure_level=pressure,
        )
        self._last_status = status
        return status

    def check_can_load_model(self, model_size_gb: float) -> bool:
        """
        Check if it is safe to load a model of the given size.
        
        Leaves a configurable buffer for safety (default 1.0 GB).
        If FRIDAY_MEM_BUFFER < 0, bypasses all checks completely.
        """
        # Allow overriding buffer for constrained 8GB systems
        import os
        buffer_gb = float(os.getenv("FRIDAY_MEM_BUFFER", 1.0))
        
        if buffer_gb < 0:
            logger.warning("FRIDAY_MEM_BUFFER is negative. Bypassing all memory checks for model load.")
            return True
            
        status = self.get_status()
        projected = status.friday_rss_gb + model_size_gb
        budget_ok = projected <= self.friday_budget_gb
        system_ok = (status.available_gb - model_size_gb) >= buffer_gb

        if not budget_ok:
            logger.warning(
                "Model load rejected: FRIDAY %.2f GB + model %.2f GB = %.2f GB "
                "(budget: %.1f GB)",
                status.friday_rss_gb, model_size_gb, projected, self.friday_budget_gb,
            )
        if not system_ok:
            logger.warning(
                "Model load rejected: only %.2f GB available, need %.2f GB + %.1f GB buffer",
                status.available_gb, model_size_gb, buffer_gb
            )
        return budget_ok and system_ok

    def handle_memory_pressure(self) -> dict:
        """
        Respond to current memory pressure level.

        Returns dict of actions taken.
        """
        status = self.get_status()
        actions: dict[str, bool] = {}

        if status.pressure_level == PressureLevel.WARNING:
            actions["clear_mlx_cache"] = self._clear_mlx_cache()
            actions["reduce_context"] = True
            logger.warning("Memory WARNING: %s", status)

        elif status.pressure_level == PressureLevel.CRITICAL:
            actions["clear_mlx_cache"] = self._clear_mlx_cache()
            actions["emergency_cleanup"] = True
            actions["reduce_max_tokens"] = True
            actions["warn_user"] = True
            logger.critical("Memory CRITICAL: %s", status)

        return actions

    def log_usage(self) -> None:
        """Log current memory usage."""
        status = self.get_status()
        logger.info(str(status))

    # ── Background Monitor ──────────────────────────────────

    def start_monitoring(self) -> None:
        """Start background memory monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, name="friday-mem-monitor", daemon=True
        )
        self._thread.start()
        logger.info(
            "Memory monitor started (interval=%ds, budget=%.1f GB)",
            self.check_interval, self.friday_budget_gb,
        )

    def stop_monitoring(self) -> None:
        """Stop background monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.check_interval + 2)
            self._thread = None
        logger.info("Memory monitor stopped")

    def on_pressure_change(self, callback: Callable[[MemoryStatus], None]) -> None:
        """Register a callback for pressure level changes."""
        self._callbacks.append(callback)

    # ── Private ─────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Background loop that checks memory at regular intervals."""
        prev_level = PressureLevel.NORMAL
        while self._running:
            try:
                status = self.get_status()

                # Log at appropriate level
                if status.pressure_level == PressureLevel.CRITICAL:
                    logger.critical(str(status))
                    self.handle_memory_pressure()
                elif status.pressure_level == PressureLevel.WARNING:
                    logger.warning(str(status))
                    self.handle_memory_pressure()
                else:
                    logger.debug(str(status))

                # Fire callbacks on level change
                if status.pressure_level != prev_level:
                    for cb in self._callbacks:
                        try:
                            cb(status)
                        except Exception:
                            logger.exception("Pressure callback error")
                    prev_level = status.pressure_level

            except Exception:
                logger.exception("Memory monitor error")

            time.sleep(self.check_interval)

    @staticmethod
    def _clear_mlx_cache() -> bool:
        """Attempt to clear MLX Metal cache."""
        try:
            import mlx.core as mx
            mx.metal.clear_cache()
            logger.info("Cleared MLX Metal cache")
            return True
        except Exception:
            logger.debug("MLX cache clear skipped (MLX not loaded)")
            return False


# ── Global singleton ────────────────────────────────────────
_config_path = Path(__file__).parent.parent.parent / "config" / "friday_config_8gb.yaml"
memory_manager = MemoryManager(config_path=_config_path if _config_path.exists() else None)

"""Unit tests for memory manager."""

import pytest
from src.memory.manager import MemoryManager, PressureLevel, MemoryStatus


class TestMemoryManager:
    def test_get_status_returns_memory_status(self):
        mm = MemoryManager()
        status = mm.get_status()
        assert isinstance(status, MemoryStatus)
        assert status.total_gb > 0
        assert status.friday_rss_gb > 0
        assert isinstance(status.pressure_level, PressureLevel)

    def test_pressure_levels(self):
        mm = MemoryManager()
        status = mm.get_status()
        assert status.pressure_level in (
            PressureLevel.NORMAL,
            PressureLevel.WARNING,
            PressureLevel.CRITICAL,
        )

    def test_check_can_load_small_model(self):
        mm = MemoryManager(friday_budget_gb=10.0)
        assert mm.check_can_load_model(0.01) is True

    def test_check_rejects_huge_model(self):
        mm = MemoryManager(friday_budget_gb=3.5)
        assert mm.check_can_load_model(100.0) is False

    def test_status_string(self):
        mm = MemoryManager()
        status = mm.get_status()
        s = str(status)
        assert "System:" in s
        assert "FRIDAY:" in s
        assert "Pressure:" in s

    def test_handle_memory_pressure_normal(self):
        mm = MemoryManager(warning_threshold=0.99, critical_threshold=0.999)
        actions = mm.handle_memory_pressure()
        assert actions == {}

    def test_start_stop_monitoring(self):
        mm = MemoryManager(check_interval=1.0)
        mm.start_monitoring()
        assert mm._running
        mm.stop_monitoring()
        assert not mm._running

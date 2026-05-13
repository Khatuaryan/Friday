"""
System Tool — Get system information.

Provides: battery, storage, memory, network status via psutil.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import psutil

from .base import Tool

logger = logging.getLogger("friday.tools.system")


class SystemTool(Tool):
    """Get system information (battery, storage, memory, network)."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return "Get system information: battery, storage, memory, or network status"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["battery", "storage", "memory", "network", "all"],
                    "description": "Type of information to retrieve",
                },
            },
            "required": ["info_type"],
        }

    def execute(self, info_type: str = "all") -> Dict[str, Any]:
        """Get system info by type."""
        handlers = {
            "battery": self._get_battery,
            "storage": self._get_storage,
            "memory": self._get_memory,
            "network": self._get_network,
        }

        if info_type == "all":
            return {k: fn() for k, fn in handlers.items()}

        if info_type in handlers:
            return {info_type: handlers[info_type]()}

        return {"error": f"Unknown info type: {info_type}"}

    @staticmethod
    def _get_battery() -> Dict[str, Any]:
        """Get battery status."""
        battery = psutil.sensors_battery()
        if battery is None:
            return {"available": False, "note": "No battery detected (desktop Mac)"}

        result: Dict[str, Any] = {
            "available": True,
            "percent": battery.percent,
            "plugged_in": battery.power_plugged,
        }
        if battery.secsleft > 0:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            result["time_remaining"] = f"{hours}h {minutes}m"

        return result

    @staticmethod
    def _get_storage() -> Dict[str, Any]:
        """Get disk storage."""
        usage = psutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent_used": usage.percent,
        }

    @staticmethod
    def _get_memory() -> Dict[str, Any]:
        """Get RAM info."""
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent_used": mem.percent,
        }

    @staticmethod
    def _get_network() -> Dict[str, Any]:
        """Get network status."""
        interfaces = psutil.net_if_addrs()
        # Filter out loopback
        active = [name for name in interfaces if name != "lo0"]
        return {
            "interfaces": len(active),
            "connected": len(active) > 0,
            "interface_names": active[:5],  # Limit to 5 for readability
        }

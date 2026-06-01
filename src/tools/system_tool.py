"""
System Tool — Get system information.

Provides: battery, storage, memory, network status via psutil.
"""

from __future__ import annotations

from src.utils.logger import get_logger
from typing import Any, Dict

import psutil

from .base import Tool

logger = get_logger("friday.tools.system")


class SystemTool(Tool):
    """Get system information and control basic system actions (battery, storage, memory, network, screenshot, volume)."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return "Get system information (battery, storage, memory, or network) or perform system actions (screenshot, set_volume)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["battery", "storage", "memory", "network", "all", "screenshot", "set_volume"],
                    "description": "Type of information to retrieve or system action to perform",
                },
                "volume": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Volume level (0-100), required only when info_type is 'set_volume'",
                },
            },
            "required": ["info_type"],
        }

    def execute(self, info_type: str = "all", volume: int | None = None) -> Dict[str, Any]:
        """Get system info or perform system action."""
        handlers = {
            "battery": self._get_battery,
            "storage": self._get_storage,
            "memory": self._get_memory,
            "network": self._get_network,
            "screenshot": self._take_screenshot,
            "set_volume": lambda: self._set_volume(volume),
        }

        if info_type == "all":
            # Exclude actions from the 'all' option
            info_keys = ["battery", "storage", "memory", "network"]
            return {k: handlers[k]() for k in info_keys}

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

    @staticmethod
    def _take_screenshot() -> Dict[str, Any]:
        """Take a screenshot and save to Desktop."""
        import time
        import subprocess
        from pathlib import Path

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = Path.home() / "Desktop" / f"friday_screenshot_{timestamp}.png"

        try:
            # -x suppresses camera shutter sound
            subprocess.run(["screencapture", "-x", str(save_path)], check=True, capture_output=True)
            return {"path": str(save_path), "status": "saved"}
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
            return {"error": f"Failed to capture screenshot: {e}"}

    @staticmethod
    def _set_volume(level: int | None) -> Dict[str, Any]:
        """Set system output volume."""
        if level is None:
            return {"error": "volume parameter is required when info_type is 'set_volume'"}
        import subprocess
        try:
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True, capture_output=True)
            return {"status": "set", "volume": level}
        except Exception as e:
            logger.error("Failed to set volume to %s: %s", level, e)
            return {"error": f"Failed to set volume: {e}"}


"""
App Control Tool — Manage macOS applications via open and AppleScript.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.app")


class AppControlTool(Tool):
    """Control and inspect running macOS applications."""

    APP_NAME_MAP = {
        "safari": "Safari",
        "chrome": "Google Chrome",
        "vscode": "Visual Studio Code",
        "vs code": "Visual Studio Code",
        "terminal": "Terminal",
        "finder": "Finder",
        "spotify": "Spotify",
        "messages": "Messages",
        "mail": "Mail",
        "calendar": "Calendar",
        "notes": "Notes",
        "pycharm": "PyCharm",
        "antigravity": "Antigravity",
    }

    @property
    def name(self) -> str:
        return "control_application"

    @property
    def description(self) -> str:
        return "Open, close, list running, or get the frontmost macOS application"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "close", "list_running", "get_frontmost"],
                    "description": "Action to perform on the application(s)",
                },
                "app_name": {
                    "type": "string",
                    "description": "The name of the target application (required for open and close)",
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, app_name: str | None = None) -> Dict[str, Any]:
        if action == "open":
            if not app_name:
                return {"error": "app_name is required for open action"}
            return self._open_app(app_name)
        elif action == "close":
            if not app_name:
                return {"error": "app_name is required for close action"}
            return self._close_app(app_name)
        elif action == "list_running":
            return self._list_running_apps()
        elif action == "get_frontmost":
            return self._get_frontmost_app()
        else:
            return {"error": f"Invalid action: {action}"}

    def _normalize_app_name(self, app_name: str) -> str:
        """Map common synonyms to their exact macOS Application name."""
        cleaned = app_name.lower().strip()
        return self.APP_NAME_MAP.get(cleaned, app_name)

    def _open_app(self, app_name: str) -> Dict[str, Any]:
        exact_name = self._normalize_app_name(app_name)
        try:
            # Use macOS 'open -a' to launch
            subprocess.run(["open", "-a", exact_name], check=True, capture_output=True)
            return {"status": "opened", "app": exact_name}
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode().strip() if e.stderr else str(e)
            logger.error("Failed to open application '%s': %s", exact_name, err_msg)
            return {"error": f"Application not found: {exact_name}. Details: {err_msg}"}
        except Exception as e:
            logger.error("Error opening application '%s': %s", exact_name, e)
            return {"error": str(e)}

    def _close_app(self, app_name: str) -> Dict[str, Any]:
        exact_name = self._normalize_app_name(app_name)
        # Use AppleScript to quit cleanly
        script = f'tell application "{exact_name}" to quit'
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return {"status": "closed", "app": exact_name}
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode().strip() if e.stderr else str(e)
            logger.error("Failed to close application '%s': %s", exact_name, err_msg)
            return {"error": f"Failed to close {exact_name}. Application may not be running. Details: {err_msg}"}
        except Exception as e:
            logger.error("Error closing application '%s': %s", exact_name, e)
            return {"error": str(e)}

    def _list_running_apps(self) -> Dict[str, Any]:
        try:
            from AppKit import NSWorkspace
        except ImportError:
            logger.warning("AppKit is missing. Unable to fetch running apps.")
            return {"apps": []}

        try:
            workspace = NSWorkspace.sharedWorkspace()
            running = workspace.runningApplications()
            apps = []
            for app in running:
                if app.activationPolicy() == 0:  # NSApplicationActivationPolicyRegular
                    name = app.localizedName()
                    if name and name not in apps:
                        apps.append(str(name))
            
            apps.sort()
            return {"apps": apps[:15]}
        except Exception as e:
            logger.error("Failed to list running applications: %s", e)
            return {"error": str(e)}

    def _get_frontmost_app(self) -> Dict[str, Any]:
        try:
            from AppKit import NSWorkspace
        except ImportError:
            logger.warning("AppKit is missing. Unable to get frontmost app.")
            return {"app": "Unknown", "bundle_id": ""}

        try:
            workspace = NSWorkspace.sharedWorkspace()
            front = workspace.frontmostApplication()
            if front:
                return {
                    "app": str(front.localizedName() or ""),
                    "bundle_id": str(front.bundleIdentifier() or ""),
                }
            return {"error": "Could not determine frontmost application"}
        except Exception as e:
            logger.error("Failed to get frontmost application: %s", e)
            return {"error": str(e)}

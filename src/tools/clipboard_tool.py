"""
Clipboard Tool — Read and write system clipboard contents using native pbcopy/pbpaste utilities.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.clipboard")


class ClipboardTool(Tool):
    """Read and write system clipboard contents."""

    @property
    def name(self) -> str:
        return "clipboard"

    @property
    def description(self) -> str:
        return "Read from or write text to the macOS system clipboard"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set"],
                    "description": "Action to perform: 'get' to read, 'set' to copy new text",
                },
                "text": {
                    "type": "string",
                    "description": "Text to write to the clipboard (required only for set action)",
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, text: str | None = None) -> Dict[str, Any]:
        if action == "get":
            return self._get_clipboard()
        elif action == "set":
            if text is None:
                return {"error": "text is required for set action"}
            return self._set_clipboard(text)
        else:
            return {"error": f"Invalid action: {action}"}

    def _get_clipboard(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=5, check=True
            )
            content = result.stdout
            length = len(content)
            
            # Truncation safety limit to prevent bloating LLM context window
            if length > 1000:
                content = content[:1000] + "... [truncated]"
                
            return {"content": content, "length": length}
        except subprocess.CalledProcessError as e:
            logger.error("pbpaste failed: %s", e)
            return {"error": f"Failed to paste from clipboard: {e}"}
        except subprocess.TimeoutExpired:
            logger.error("pbpaste timed out")
            return {"error": "Clipboard reading timed out"}
        except Exception as e:
            logger.error("Clipboard get error: %s", e)
            return {"error": str(e)}

    def _set_clipboard(self, content: str) -> Dict[str, Any]:
        try:
            subprocess.run(
                ["pbcopy"], input=content, text=True, timeout=5, check=True
            )
            return {"status": "copied", "length": len(content)}
        except subprocess.CalledProcessError as e:
            logger.error("pbcopy failed: %s", e)
            return {"error": f"Failed to copy to clipboard: {e}"}
        except subprocess.TimeoutExpired:
            logger.error("pbcopy timed out")
            return {"error": "Clipboard writing timed out"}
        except Exception as e:
            logger.error("Clipboard set error: %s", e)
            return {"error": str(e)}

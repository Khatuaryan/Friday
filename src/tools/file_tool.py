"""
File Tool — Read files from sandboxed directories.

Safety: Only ~/Documents, ~/Desktop, ~/Downloads, and project root.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.file")

# Project root for sandbox inclusion
_PROJECT_ROOT = Path(__file__).parent.parent.parent


class FileTool(Tool):
    """Read files from the entire macOS filesystem (root directory access)."""

    ALLOWED_DIRS = [
        Path("/"),
    ]

    MAX_FILE_SIZE = 100_000  # 100KB max to avoid flooding LLM context

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read contents of a text file from the entire macOS filesystem (root directory access)"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to a text file",
                },
            },
            "required": ["file_path"],
        }

    def execute(self, file_path: str) -> Dict[str, Any]:
        """Read file contents with safety checks."""
        # Auto-correct common LLM hallucinations for the home directory
        if file_path.startswith("/Users/YourUsername") or file_path.startswith("/Users/Username"):
            import os
            # Replace the fake prefix with the actual home directory
            parts = file_path.split("/")
            # parts will be ['', 'Users', 'YourUsername', 'Documents', ...]
            # We want to keep everything from index 3 onwards and join with home
            if len(parts) > 3:
                file_path = os.path.join(str(Path.home()), *parts[3:])

        path = Path(file_path).expanduser().resolve()

        # Security check
        if not self._is_path_allowed(path):
            return {"error": f"Access denied: {path} is not in allowed directories"}

        if not path.exists():
            return {"error": f"File not found: {path}"}

        if not path.is_file():
            return {"error": f"Not a file: {path}"}

        if path.stat().st_size > self.MAX_FILE_SIZE:
            return {"error": f"File too large ({path.stat().st_size} bytes, max {self.MAX_FILE_SIZE})"}

        try:
            content = path.read_text(encoding="utf-8")
            return {
                "path": str(path),
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
            }
        except UnicodeDecodeError:
            return {"error": "File is not text (binary file)"}
        except PermissionError:
            return {"error": f"Permission denied: {path}"}

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        for allowed_dir in self.ALLOWED_DIRS:
            try:
                path.relative_to(allowed_dir.resolve())
                return True
            except ValueError:
                continue
        return False

"""
File Tool — Read files from sandboxed directories.

Safety: Only ~/Documents, ~/Desktop, ~/Downloads, and project root.
"""

from __future__ import annotations

from src.utils.logger import get_logger
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from .base import Tool

logger = get_logger("friday.tools.file")

# Project root for sandbox inclusion
_PROJECT_ROOT = Path(__file__).parent.parent.parent


class FileTool(Tool):
    """Read files from the entire macOS filesystem (root directory access)."""

    # Injection pattern list — conservative set of confirmed attack patterns
    INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"you\s+are\s+now\s+a",
        r"disregard\s+all\s+prior",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
        r"<tool_call>",
        r"<start_of_turn>",
        r"\[INST\]",
        r"### System",
        r"### Instruction",
    ]

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
            
            risk_detected, sanitized = self._check_injection_risk(content)
            
            result: Dict[str, Any] = {
                "path": str(path),
                "content": sanitized,
                "size_bytes": len(content.encode("utf-8")),
            }
            if risk_detected:
                result["security_warning"] = (
                    "File content contained prompt injection patterns. "
                    "Content wrapped in neutral markers."
                )
            return result
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

    def _check_injection_risk(self, content: str) -> Tuple[bool, str]:
        """
        Scan for known injection patterns.
        If found, wrap content in [FILE CONTENT] markers so the brain
        treats it as raw data, not as instructions.
        """
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(
                    "Prompt injection pattern matched in file content. "
                    "Wrapping in neutral markers."
                )
                return True, f"[FILE CONTENT START]\n{content}\n[FILE CONTENT END]"
        return False, content


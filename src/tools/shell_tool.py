"""
Shell Tool — Secure sandboxed shell command execution with forced verbal confirmation.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.shell")


class ShellTool(Tool):
    """Execute standard shell commands safely on the local system."""

    # Safe whitelist of allowed core commands/executables
    SAFE_WHITELIST = {
        "ls", "pwd", "echo", "cat", "git", "pytest", "make",
        "grep", "find", "mkdir", "rm", "cp", "mv", "touch",
        "python", "python3", "pip", "uv", "uname", "df",
        "free", "uptime", "whoami", "curl", "ping", "poetry"
    }

    @property
    def name(self) -> str:
        return "execute_shell"

    @property
    def description(self) -> str:
        return "Execute shell commands on the local macOS system (requires verbal confirmation)"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "_confirmed": {
                    "type": "boolean",
                    "description": "Internal flag verifying verbal user confirmation",
                    "default": False,
                },
            },
            "required": ["command"],
        }

    def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        command_clean = command.strip()
        if not command_clean:
            return {"error": "Command string is empty"}

        # 1. Block sudo completely
        if "sudo" in command_clean.lower().split() or "sudo" in command_clean.lower():
            return {"error": "Access denied: sudo operations are strictly blocked"}

        # 2. Whitelist validation: Split by shell separators and verify each command start
        segments = self._split_command_segments(command_clean)
        for segment in segments:
            if not segment:
                continue
            first_token = segment[0]
            if first_token not in self.SAFE_WHITELIST:
                return {"error": f"Access denied: '{first_token}' is not in the safe command whitelist"}

        # 3. Always force verbal confirmation
        if not kwargs.get("_confirmed", False):
            return {
                "requires_confirmation": True,
                "action_description": f"execute the shell command '{command_clean}'",
                "pending_action": {
                    "name": "execute_shell",
                    "arguments": {"command": command_clean, "_confirmed": True},
                },
            }

        return self._run_command(command_clean)

    def _split_command_segments(self, command: str) -> list[list[str]]:
        """Split a command line by shell operators like ;, &&, ||, | to check each segment."""
        # Simple token split first to identify operator indices
        try:
            tokens = shlex.split(command)
        except ValueError:
            # Fallback to simple split if shlex parsing fails
            tokens = command.split()

        operators = {";", "&&", "||", "|"}
        segments = []
        current_segment = []

        for token in tokens:
            if token in operators:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                current_segment.append(token)

        if current_segment:
            segments.append(current_segment)

        return segments

    def _run_command(self, command: str) -> Dict[str, Any]:
        logger.info("Executing shell command: %s", command)
        try:
            # Run in shell with a strict 30-second timeout
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30.0
            )

            return {
                "status": "success",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "confirmation_message": f"Successfully executed command. Exit code: {res.returncode}.",
            }
        except subprocess.TimeoutExpired:
            logger.error("Shell command timed out: %s", command)
            return {"error": "Command execution timed out after 30 seconds"}
        except Exception as e:
            logger.error("Failed to run shell command %s: %s", command, e)
            return {"error": str(e)}

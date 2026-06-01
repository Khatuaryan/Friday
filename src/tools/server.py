"""
MCP Tool Server — Manages tool registration, parsing, and execution.

Parses <tool_call> blocks from LLM responses and routes to the correct tool.
"""

from __future__ import annotations

import json
from src.utils.logger import get_logger
import re
import time
from typing import Any, Dict, List, Optional

from .base import Tool
from .calendar_tool import CalendarTool
from .file_tool import FileTool
from .system_tool import SystemTool
from .app_tool import AppControlTool
from .media_tool import MediaControlTool
from .clipboard_tool import ClipboardTool
from .calendar_write_tool import CalendarWriteTool
from .reminder_tool import ReminderTool
from .file_write_tool import FileWriteTool
from .shell_tool import ShellTool
from .message_tool import MessageTool
from .email_tool import EmailTool
from .web_tool import WebSearchTool, WeatherTool

logger = get_logger("friday.tools.server")


class MCPToolServer:
    """
    MCP tool server for FRIDAY.

    Manages tool registration, <tool_call> parsing, and execution routing.
    """

    RATE_LIMIT_CALLS = 5
    RATE_LIMIT_WINDOW = 60.0

    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}
        self._call_timestamps: List[float] = []
        self._register_default_tools()


    def _register_default_tools(self) -> None:
        """Register built-in tools."""
        tool_classes = [
            CalendarTool,
            FileTool,
            SystemTool,
            AppControlTool,
            MediaControlTool,
            ClipboardTool,
            CalendarWriteTool,
            ReminderTool,
            FileWriteTool,
            ShellTool,
            MessageTool,
            EmailTool,
            WebSearchTool,
            WeatherTool,
        ]
        for tool_class in tool_classes:
            tool = tool_class()
            self.register_tool(tool)

    def register_tool(self, tool: Tool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get_tools_description(self) -> str:
        """Get formatted description of all tools for the LLM system prompt."""
        lines = []
        for tool in self.tools.values():
            params = tool.parameters.get("properties", {})
            param_str = ", ".join(
                f"{k}: {v.get('type', 'any')}" for k, v in params.items()
            )
            lines.append(f"- {tool.name}({param_str}): {tool.description}")
        return "\n".join(lines)

    def parse_tool_call(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse <tool_call> block from LLM response.
        
        More robust parsing that handles slightly malformed tags, missing closing tags,
        or completely missing tags if the model just outputs JSON. Supports balanced-brace
        scanning to find and isolate individual JSON objects out of text.
        """
        # 1. Look for <tool_call> and then any JSON-like structure following it
        match = re.search(
            r"<tool_call>(.*?)(?:</tool_call>|$)",
            response_text,
            re.DOTALL | re.IGNORECASE,
        )

        if match:
            content = match.group(1).strip()
            # If tags found, let's extract the JSON candidate from it
            if "{" in content:
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if end_idx > start_idx:
                    content_candidate = content[start_idx:end_idx+1]
                else:
                    content_candidate = content[start_idx:]
            else:
                content_candidate = content
            
            return self._parse_json_with_repair(content_candidate)

        # 2. Fallback: Scan response_text for any balanced JSON-like objects containing "name" and "arguments"
        candidates = []
        start = 0
        while True:
            pos = response_text.find("{", start)
            if pos == -1:
                break
            
            brace_count = 0
            in_string = False
            escape = False
            end = -1
            
            for i in range(pos, len(response_text)):
                char = response_text[i]
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i
                            break
            
            if end != -1:
                candidate = response_text[pos:end+1]
                candidates.append(candidate)
                start = pos + 1
            else:
                # If we couldn't find a matching closing brace, we might have an incomplete JSON
                # Let's take the rest of the string starting from pos and try to repair it later
                candidate = response_text[pos:]
                candidates.append(candidate)
                break

        # Check candidates for a valid tool call
        for candidate in candidates:
            # Must look like a tool call JSON with name and arguments
            if '"name"' in candidate and '"arguments"' in candidate:
                parsed = self._parse_json_with_repair(candidate)
                if parsed and "name" in parsed:
                    return parsed

        return None

    def _parse_json_with_repair(self, content_candidate: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse the candidate string as JSON with auto-repair capability."""
        if not content_candidate:
            return None

        # Clean up any potential markdown code fence markers around or inside
        content_candidate = content_candidate.strip()
        if content_candidate.startswith("```json"):
            content_candidate = content_candidate[7:].strip()
        elif content_candidate.startswith("```"):
            content_candidate = content_candidate[3:].strip()
        if content_candidate.endswith("```"):
            content_candidate = content_candidate[:-3].strip()

        try:
            tool_call = json.loads(content_candidate)
            return tool_call
        except json.JSONDecodeError as e:
            # Attempt auto-repair by adding a closing brace
            try:
                repaired = content_candidate + "}"
                tool_call = json.loads(repaired)
                logger.info("Auto-repaired missing JSON brace in tool call")
                return tool_call
            except json.JSONDecodeError:
                # If it still fails, try adding two closing braces just in case
                try:
                    repaired = content_candidate + "}}"
                    tool_call = json.loads(repaired)
                    logger.info("Auto-repaired missing JSON braces in tool call")
                    return tool_call
                except json.JSONDecodeError:
                    logger.error("Failed to parse tool call JSON: %s. Content: %s", e, content_candidate)
                    return None

    def execute_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call with sliding-window rate limiting.

        Args:
            tool_call: {"name": "...", "arguments": {...}}

        Returns:
            Tool execution result dict or error.
        """
        now = time.time()

        # Prune timestamps outside the window
        self._call_timestamps = [
            t for t in self._call_timestamps
            if now - t < self.RATE_LIMIT_WINDOW
        ]

        if len(self._call_timestamps) >= self.RATE_LIMIT_CALLS:
            logger.warning(
                "Tool rate limit exceeded: %d calls in %.0fs window",
                self.RATE_LIMIT_CALLS,
                self.RATE_LIMIT_WINDOW,
            )
            return {
                "error": (
                    "Tool rate limit exceeded. "
                    "Please wait before making additional tool calls."
                )
            }

        self._call_timestamps.append(now)

        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        tool = self.tools[tool_name]
        logger.info("Executing tool: %s with %s", tool_name, arguments)

        return tool.safe_execute(**arguments)


    def get_tool_names(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self.tools.keys())

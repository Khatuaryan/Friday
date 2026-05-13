"""
MCP Tool Server — Manages tool registration, parsing, and execution.

Parses <tool_call> blocks from LLM responses and routes to the correct tool.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import Tool
from .calendar_tool import CalendarTool
from .file_tool import FileTool
from .system_tool import SystemTool

logger = logging.getLogger("friday.tools.server")


class MCPToolServer:
    """
    MCP tool server for FRIDAY.

    Manages tool registration, <tool_call> parsing, and execution routing.
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in tools."""
        for tool_class in [CalendarTool, FileTool, SystemTool]:
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

        Format:
            <tool_call>
            {"name": "tool_name", "arguments": {"arg1": "value1"}}
            </tool_call>

        Returns:
            Parsed tool call dict, or None if no tool call found.
        """
        match = re.search(
            r"<tool_call>(.*?)</tool_call>",
            response_text,
            re.DOTALL,
        )

        if not match:
            return None

        try:
            tool_call = json.loads(match.group(1).strip())
            if "name" not in tool_call:
                logger.error("Tool call missing 'name' field")
                return None
            return tool_call
        except json.JSONDecodeError as e:
            logger.error("Failed to parse tool call JSON: %s", e)
            return None

    def execute_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call.

        Args:
            tool_call: {"name": "...", "arguments": {...}}

        Returns:
            Tool execution result dict.
        """
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

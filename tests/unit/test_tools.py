"""Unit tests for MCP tools and tool server."""

import pytest
from pathlib import Path

from src.tools.base import Tool
from src.tools.system_tool import SystemTool
from src.tools.file_tool import FileTool
from src.tools.server import MCPToolServer


class TestSystemTool:
    def test_name(self):
        tool = SystemTool()
        assert tool.name == "get_system_info"

    def test_memory_info(self):
        tool = SystemTool()
        result = tool.execute(info_type="memory")
        assert "memory" in result
        assert "total_gb" in result["memory"]
        assert result["memory"]["total_gb"] > 0

    def test_storage_info(self):
        tool = SystemTool()
        result = tool.execute(info_type="storage")
        assert "storage" in result
        assert result["storage"]["total_gb"] > 0

    def test_all_info(self):
        tool = SystemTool()
        result = tool.execute(info_type="all")
        assert "memory" in result
        assert "storage" in result
        assert "network" in result

    def test_unknown_type(self):
        tool = SystemTool()
        result = tool.execute(info_type="invalid")
        assert "error" in result


class TestFileTool:
    def test_name(self):
        tool = FileTool()
        assert tool.name == "read_file"

    def test_restricted_path_denied(self):
        # Now root filesystem is allowed, so /etc/passwd should be readable or not raise "Access denied"
        tool = FileTool()
        result = tool.execute(file_path="/etc/passwd")
        assert "error" not in result
        assert "content" in result

    def test_nonexistent_file(self):
        tool = FileTool()
        result = tool.execute(file_path=str(Path.home() / "Documents" / "nonexistent_file_xyz.txt"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_path_traversal_blocked(self):
        # /../../etc/shadow is resolved to /etc/shadow, which should be allowed but not exist or be unreadable
        tool = FileTool()
        result = tool.execute(file_path="/../../etc/shadow")
        assert "error" in result
        assert "not found" in result["error"].lower() or "permission denied" in result["error"].lower()


class TestMCPToolServer:
    def test_default_tools_registered(self):
        server = MCPToolServer()
        names = server.get_tool_names()
        assert "get_system_info" in names
        assert "read_file" in names
        assert "get_calendar_events" in names

    def test_tools_description(self):
        server = MCPToolServer()
        desc = server.get_tools_description()
        assert "get_system_info" in desc
        assert "read_file" in desc

    def test_parse_tool_call_valid(self):
        server = MCPToolServer()
        text = 'Sure! <tool_call>{"name": "get_system_info", "arguments": {"info_type": "battery"}}</tool_call>'
        result = server.parse_tool_call(text)
        assert result is not None
        assert result["name"] == "get_system_info"
        assert result["arguments"]["info_type"] == "battery"

    def test_parse_tool_call_no_match(self):
        server = MCPToolServer()
        result = server.parse_tool_call("No tool call here.")
        assert result is None

    def test_parse_tool_call_invalid_json(self):
        server = MCPToolServer()
        result = server.parse_tool_call("<tool_call>not json</tool_call>")
        assert result is None

    def test_execute_system_tool(self):
        server = MCPToolServer()
        result = server.execute_tool({
            "name": "get_system_info",
            "arguments": {"info_type": "memory"},
        })
        assert "memory" in result

    def test_execute_unknown_tool(self):
        server = MCPToolServer()
        result = server.execute_tool({
            "name": "nonexistent_tool",
            "arguments": {},
        })
        assert "error" in result

    def test_parse_tool_call_markdown_and_multiple(self):
        server = MCPToolServer()
        markdown_text = (
            "Please check calendar and memory:\n"
            "```json\n"
            '{"name": "get_calendar_events", "arguments": {"date": "2026-05-20"}}\n'
            "```\n"
            "And to assess your available memory:\n"
            "```json\n"
            '{"name": "get_system_info", "arguments": {"info_type": "memory"}}\n'
            "```"
        )
        result = server.parse_tool_call(markdown_text)
        assert result is not None
        assert result["name"] == "get_calendar_events"
        assert result["arguments"]["date"] == "2026-05-20"

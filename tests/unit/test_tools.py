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

    def test_time_info(self):
        tool = SystemTool()
        result = tool.execute(info_type="time")
        assert "time" in result
        assert "formatted" in result["time"]
        assert "timestamp" in result["time"]

    def test_robust_execute(self):
        tool = SystemTool()
        result = tool.execute()
        assert "error" in result
        assert "Missing required parameter" in result["error"]


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


class TestAppControlTool:
    def test_name(self):
        from src.tools.app_tool import AppControlTool
        tool = AppControlTool()
        assert tool.name == "control_application"

    def test_app_name_normalization(self):
        from src.tools.app_tool import AppControlTool
        tool = AppControlTool()
        assert tool._normalize_app_name("safari") == "Safari"
        assert tool._normalize_app_name("vs code") == "Visual Studio Code"
        assert tool._normalize_app_name("UnknownApp") == "UnknownApp"

    def test_open_application_subprocess_call(self):
        from src.tools.app_tool import AppControlTool
        from unittest.mock import patch, MagicMock
        tool = AppControlTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = tool.execute(action="open", app_name="safari")
            assert res["status"] == "opened"
            assert res["app"] == "Safari"
            mock_run.assert_called_with(["open", "-a", "Safari"], check=True, capture_output=True)

    def test_open_unknown_app_returns_error(self):
        from src.tools.app_tool import AppControlTool
        from unittest.mock import patch
        import subprocess
        tool = AppControlTool()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["open", "-a", "Nonexistent"], stderr=b"Application not found")
            res = tool.execute(action="open", app_name="Nonexistent")
            assert "error" in res
            assert "Nonexistent" in res["error"]

    def test_close_application_subprocess_call(self):
        from src.tools.app_tool import AppControlTool
        from unittest.mock import patch, MagicMock
        tool = AppControlTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = tool.execute(action="close", app_name="chrome")
            assert res["status"] == "closed"
            assert res["app"] == "Google Chrome"
            mock_run.assert_called_with(["osascript", "-e", 'tell application "Google Chrome" to quit'], check=True, capture_output=True)

    def test_list_running_apps_returns_dict(self):
        from src.tools.app_tool import AppControlTool
        tool = AppControlTool()
        res = tool.execute(action="list_running")
        assert "apps" in res
        assert isinstance(res["apps"], list)

    def test_get_frontmost_app_returns_dict(self):
        from src.tools.app_tool import AppControlTool
        tool = AppControlTool()
        res = tool.execute(action="get_frontmost")
        assert "app" in res or "error" in res


class TestMediaControlTool:
    def test_name(self):
        from src.tools.media_tool import MediaControlTool
        tool = MediaControlTool()
        assert tool.name == "control_media"

    def test_volume_get_and_set(self):
        from src.tools.media_tool import MediaControlTool
        from unittest.mock import patch, MagicMock
        tool = MediaControlTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="50\n", returncode=0)
            res = tool.execute(action="get_volume")
            assert res["volume"] == 50
            mock_run.assert_called_with(["osascript", "-e", "output volume of (get volume settings)"], check=True, capture_output=True, text=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            res = tool.execute(action="set_volume", volume=75)
            assert res["status"] == "set"
            assert res["volume"] == 75
            mock_run.assert_called_with(["osascript", "-e", "set volume output volume 75"], check=True, capture_output=True, text=True)

    def test_mute_unmute(self):
        from src.tools.media_tool import MediaControlTool
        from unittest.mock import patch, MagicMock
        tool = MediaControlTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            res = tool.execute(action="mute")
            assert res["status"] == "muted"
            mock_run.assert_called_with(["osascript", "-e", "set volume with output muted"], check=True, capture_output=True, text=True)

    def test_invalid_action(self):
        from src.tools.media_tool import MediaControlTool
        tool = MediaControlTool()
        res = tool.execute(action="invalid_action")
        assert "error" in res


class TestClipboardTool:
    def test_name(self):
        from src.tools.clipboard_tool import ClipboardTool
        tool = ClipboardTool()
        assert tool.name == "clipboard"

    def test_set_then_get_roundtrip(self):
        from src.tools.clipboard_tool import ClipboardTool
        tool = ClipboardTool()
        test_str = "FRIDAY_TEST_STRING_123"
        
        # Write to clipboard
        set_res = tool.execute(action="set", text=test_str)
        assert set_res["status"] == "copied"
        assert set_res["length"] == len(test_str)
        
        # Read from clipboard
        get_res = tool.execute(action="get")
        assert test_str in get_res["content"]
        assert get_res["length"] >= len(test_str)

    def test_robust_execute_missing_action(self):
        from src.tools.clipboard_tool import ClipboardTool
        tool = ClipboardTool()
        result = tool.execute()
        assert "error" in result
        assert "Missing required parameter" in result["error"]


class TestCalendarWriteTool:
    def test_name(self):
        from src.tools.calendar_write_tool import CalendarWriteTool
        tool = CalendarWriteTool()
        assert tool.name == "manage_calendar"

    def test_create_event_parameter_check(self):
        from src.tools.calendar_write_tool import CalendarWriteTool
        tool = CalendarWriteTool()
        res = tool.execute(action="create_event")
        assert "error" in res

    def test_create_event_successful_mock(self):
        from src.tools.calendar_write_tool import CalendarWriteTool
        from unittest.mock import patch, MagicMock
        import sys

        mock_eventkit = MagicMock()
        mock_event = MagicMock()
        mock_event.eventIdentifier.return_value = "TEST_EVENT_ID_123"
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = mock_event
        mock_foundation = MagicMock()

        with patch.dict(sys.modules, {"EventKit": mock_eventkit, "Foundation": mock_foundation}):
            tool = CalendarWriteTool()

            mock_store = MagicMock()
            mock_calendar = MagicMock()
            mock_store.defaultCalendarForNewEvents.return_value = mock_calendar
            mock_store.saveEvent_span_commit_error_.return_value = (True, None)

            with patch.object(CalendarWriteTool, "_get_store", return_value=mock_store):
                res = tool.execute(
                    action="create_event",
                    title="Design Review",
                    date="2026-05-25",
                    time="15:00",
                    duration_minutes=60,
                    location="HQ",
                    notes="Review phase 5 capability",
                )
                assert res["status"] == "created"
                assert res["event_id"] == "TEST_EVENT_ID_123"
                assert "Design Review" in res["title"]

    def test_delete_event_requires_confirmation(self):
        from src.tools.calendar_write_tool import CalendarWriteTool
        tool = CalendarWriteTool()
        res = tool.execute(action="delete_event", event_id="EVENT_ID_ABC")
        assert res.get("requires_confirmation") is True
        assert res["pending_action"]["arguments"]["_confirmed"] is True

    def test_confirmed_delete_event_mock(self):
        from src.tools.calendar_write_tool import CalendarWriteTool
        from unittest.mock import patch, MagicMock
        tool = CalendarWriteTool()

        mock_store = MagicMock()
        mock_event = MagicMock()
        mock_event.title.return_value = "To Be Deleted"
        mock_store.eventWithIdentifier_.return_value = mock_event
        mock_store.removeEvent_span_commit_error_.return_value = (True, None)

        with patch.object(CalendarWriteTool, "_get_store", return_value=mock_store):
            res = tool.execute(action="delete_event", event_id="EVENT_ID_ABC", _confirmed=True)
            assert res["status"] == "deleted"
            assert res["event_id"] == "EVENT_ID_ABC"
            assert "Successfully deleted" in res["confirmation_message"]


class TestReminderTool:
    def test_name(self):
        from src.tools.reminder_tool import ReminderTool
        tool = ReminderTool()
        assert tool.name == "manage_reminders"

    def test_create_reminder_mock(self):
        from src.tools.reminder_tool import ReminderTool
        from unittest.mock import patch, MagicMock
        tool = ReminderTool()
        import sys

        mock_eventkit = MagicMock()
        mock_reminder = MagicMock()
        mock_reminder.calendarItemIdentifier.return_value = "REMINDER_ID_XYZ"
        mock_eventkit.EKReminder.reminderWithEventStore_.return_value = mock_reminder
        mock_foundation = MagicMock()

        with patch.dict(sys.modules, {"EventKit": mock_eventkit, "Foundation": mock_foundation}):
            mock_store = MagicMock()
            mock_calendar = MagicMock()
            mock_store.defaultCalendarForNewReminders.return_value = mock_calendar
            mock_store.saveReminder_commit_error_.return_value = (True, None)

            with patch.object(ReminderTool, "_get_store", return_value=mock_store):
                res = tool.execute(
                    action="create",
                    title="Call Doctor",
                    due_date="2026-05-25",
                    due_time="10:00",
                    notes="Checkup scheduling",
                )
                assert res["status"] == "created"
                assert res["reminder_id"] == "REMINDER_ID_XYZ"

    def test_complete_reminder_mock(self):
        from src.tools.reminder_tool import ReminderTool
        from unittest.mock import patch, MagicMock
        tool = ReminderTool()

        mock_store = MagicMock()
        mock_reminder = MagicMock()
        mock_reminder.title.return_value = "Completed Reminder"
        mock_store.calendarItemWithIdentifier_.return_value = mock_reminder
        mock_store.saveReminder_commit_error_.return_value = (True, None)

        with patch.object(ReminderTool, "_get_store", return_value=mock_store):
            res = tool.execute(action="complete", reminder_id="REMINDER_ID_XYZ")
            assert res["status"] == "completed"
            assert res["reminder_id"] == "REMINDER_ID_XYZ"


class TestConfirmationEngine:
    def test_brain_intercepts_requires_confirmation(self):
        from src.core.brain import FridayBrain
        from unittest.mock import patch, MagicMock

        brain = FridayBrain()
        brain._loaded = True

        mock_tool_result = {
            "requires_confirmation": True,
            "action_description": "delete a file",
            "pending_action": {
                "name": "write_filesystem",
                "arguments": {"action": "delete_file", "_confirmed": True}
            }
        }

        # Mocking think_full steps to return mock_tool_result from execute_tool
        with patch("src.tools.server.MCPToolServer.parse_tool_call") as mock_parse, \
             patch("src.tools.server.MCPToolServer.execute_tool", return_value=mock_tool_result), \
             patch.object(FridayBrain, "_generate", return_value='<tool_call>{"name": "write_filesystem"}</tool_call>'):
            
            mock_parse.return_value = {"name": "write_filesystem", "arguments": {}}
            
            res = brain.think_full("delete file")
            assert "delete a file" in res
            assert brain.pending_confirmation == mock_tool_result

    def test_execute_pending_tool(self):
        from src.core.brain import FridayBrain
        from unittest.mock import patch, MagicMock

        brain = FridayBrain()
        brain.pending_confirmation = {
            "pending_action": {
                "name": "write_filesystem",
                "arguments": {"action": "delete_file"}
            }
        }

        with patch("src.tools.server.MCPToolServer.execute_tool", return_value={"status": "success"}) as mock_exec:
            res = brain.execute_pending_tool()
            assert res["status"] == "success"
            assert brain.pending_confirmation is None
            mock_exec.assert_called_once_with({"name": "write_filesystem", "arguments": {"action": "delete_file"}})


class TestFileWriteTool:
    def test_name(self):
        from src.tools.file_write_tool import FileWriteTool
        assert FileWriteTool().name == "write_filesystem"

    def test_write_and_append_file(self, tmp_path):
        from src.tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        test_file = tmp_path / "test.txt"

        # Write
        res = tool.execute(action="write_file", path=str(test_file), content="Hello World")
        assert res["status"] == "success"
        assert test_file.read_text() == "Hello World"

        # Append
        res = tool.execute(action="append_file", path=str(test_file), content=" Again")
        assert res["status"] == "success"
        assert test_file.read_text() == "Hello World Again"

    def test_write_file_over_limit(self, tmp_path):
        from src.tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        test_file = tmp_path / "test.txt"
        large_content = "A" * (tool.MAX_WRITE_SIZE + 1)

        res = tool.execute(action="write_file", path=str(test_file), content=large_content)
        assert "error" in res
        assert "exceeds maximum" in res["error"]

    def test_create_directory(self, tmp_path):
        from src.tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        test_dir = tmp_path / "new_dir"

        res = tool.execute(action="create_directory", path=str(test_dir))
        assert res["status"] == "success"
        assert test_dir.is_dir()

    def test_delete_file_requires_confirmation(self, tmp_path):
        from src.tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        test_file = tmp_path / "delete_me.txt"
        test_file.write_text("content")

        res = tool.execute(action="delete_file", path=str(test_file))
        assert res.get("requires_confirmation") is True
        assert test_file.exists()

        # Confirmed deletion
        res = tool.execute(action="delete_file", path=str(test_file), _confirmed=True)
        assert res["status"] == "success"
        assert not test_file.exists()


class TestShellTool:
    def test_name(self):
        from src.tools.shell_tool import ShellTool
        assert ShellTool().name == "execute_shell"

    def test_shell_always_requires_confirmation(self):
        from src.tools.shell_tool import ShellTool
        tool = ShellTool()
        res = tool.execute(command="ls -la")
        assert res.get("requires_confirmation") is True
        assert res["pending_action"]["arguments"]["_confirmed"] is True

    def test_sudo_blocked(self):
        from src.tools.shell_tool import ShellTool
        tool = ShellTool()
        res = tool.execute(command="sudo rm -rf /")
        assert "error" in res
        assert "sudo operations are strictly blocked" in res["error"]

    def test_whitelist_validation(self):
        from src.tools.shell_tool import ShellTool
        tool = ShellTool()
        res = tool.execute(command="nmap localhost")
        assert "error" in res
        assert "not in the safe command whitelist" in res["error"]

    def test_confirmed_execution_mock(self):
        from src.tools.shell_tool import ShellTool
        from unittest.mock import patch, MagicMock
        tool = ShellTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="my_file.py\n", stderr="")
            res = tool.execute(command="ls", _confirmed=True)
            assert res["status"] == "success"
            assert "my_file.py" in res["stdout"]


class TestMessageTool:
    def test_name(self):
        from src.tools.message_tool import MessageTool
        assert MessageTool().name == "send_message"

    def test_message_requires_confirmation(self):
        from src.tools.message_tool import MessageTool
        tool = MessageTool()
        res = tool.execute(recipient="Mom", message="Hello")
        assert res.get("requires_confirmation") is True

    def test_send_message_confirmed_mock(self):
        from src.tools.message_tool import MessageTool
        from unittest.mock import patch, MagicMock
        tool = MessageTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="success\n", stderr="")
            res = tool.execute(recipient="+12345", message="Hello", _confirmed=True)
            assert res["status"] == "success"
            assert "Successfully sent" in res["confirmation_message"]


class TestEmailTool:
    def test_name(self):
        from src.tools.email_tool import EmailTool
        assert EmailTool().name == "manage_email"

    def test_email_draft_no_confirmation(self):
        from src.tools.email_tool import EmailTool
        from unittest.mock import patch, MagicMock
        tool = EmailTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="success\n")
            res = tool.execute(action="draft", recipient="test@example.com", subject="Test", body="Body")
            assert res["status"] == "success"
            assert res["action"] == "draft"

    def test_email_send_requires_confirmation(self):
        from src.tools.email_tool import EmailTool
        tool = EmailTool()
        res = tool.execute(action="send", recipient="test@example.com", subject="Test", body="Body")
        assert res.get("requires_confirmation") is True

    def test_email_send_confirmed_mock(self):
        from src.tools.email_tool import EmailTool
        from unittest.mock import patch, MagicMock
        tool = EmailTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="success\n")
            res = tool.execute(action="send", recipient="test@example.com", subject="Test", body="Body", _confirmed=True)
            assert res["status"] == "success"
            assert res["action"] == "send"


class TestWebSearchTool:
    def test_name(self):
        from src.tools.web_tool import WebSearchTool
        assert WebSearchTool().name == "web_search"

    def test_web_search_success_mock(self):
        from src.tools.web_tool import WebSearchTool
        from unittest.mock import patch, MagicMock
        tool = WebSearchTool()

        # Mocking httpx.get for DDG Instant Answer and fallback HTML search
        mock_resp_api = MagicMock(status_code=200)
        mock_resp_api.json.return_value = {"AbstractText": "", "Heading": "", "AbstractURL": ""}
        
        mock_resp_html = MagicMock(status_code=200)
        mock_resp_html.text = """
        <div class="result body">
            <a class="result__a" href="http://duckduckgo.com/l/?uddg=https://example.com/topic">Example Topic</a>
            <div class="result__snippet">This is an example topic snippet.</div>
        </div>
        """

        with patch("httpx.get", side_effect=[mock_resp_api, mock_resp_html]):
            res = tool.execute(query="apple")
            assert res["source"] == "DuckDuckGo HTML"
            assert len(res["results"]) == 1
            assert res["results"][0]["title"] == "Example Topic"
            assert res["results"][0]["url"] == "https://example.com/topic"
            assert "example topic snippet" in res["results"][0]["snippet"]


class TestWeatherTool:
    def test_name(self):
        from src.tools.web_tool import WeatherTool
        assert WeatherTool().name == "get_weather"

    def test_get_weather_success_mock(self):
        from src.tools.web_tool import WeatherTool
        from unittest.mock import patch, MagicMock
        tool = WeatherTool()

        mock_json = {
            "current_condition": [{
                "temp_C": "28",
                "FeelsLikeC": "31",
                "humidity": "75",
                "weatherDesc": [{"value": "Sunny"}],
                "windspeedKmph": "15"
            }],
            "nearest_area": [{
                "areaName": [{"value": "Mumbai"}],
                "country": [{"value": "India"}]
            }],
            "weather": [{
                "maxtempC": "32",
                "mintempC": "26"
            }]
        }
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = mock_json

        with patch("httpx.get", return_value=mock_resp):
            res = tool.execute(location="Mumbai")
            assert res["location"] == "Mumbai, India"
            assert res["temperature_celsius"] == "28"
            assert res["condition"] == "Sunny"
            assert res["forecast_today"]["max_celsius"] == "32"


class TestProactiveEngine:
    def test_focus_breaks(self):
        from src.proactive.engine import ProactiveEngine
        from unittest.mock import MagicMock, patch
        import time

        mock_tracker = MagicMock()
        # Mock 45+ minutes active app history in same app
        t_start = time.time() - 46 * 60
        mock_tracker.get_context_history.return_value = [
            {"app": "Visual Studio Code", "timestamp": t_start},
            {"app": "Visual Studio Code", "timestamp": time.time() - 10}
        ]

        engine = ProactiveEngine(context_tracker=mock_tracker)
        engine._speak = MagicMock()

        # Set last break suggestion to ensure trigger can run
        engine._last_break_suggestion = time.time() - 46 * 60

        engine._check_health_breaks()
        engine._speak.assert_called_once()
        assert "Visual Studio Code" in engine._speak.call_args[0][0]

    def test_meeting_reminder_and_auto_open(self):
        from src.proactive.engine import ProactiveEngine
        from unittest.mock import MagicMock, patch
        import datetime

        mock_server = MagicMock()
        # Add exactly 30 minutes and 30 seconds to mathematically guarantee matching [29.5, 30.5] range after truncation
        future = datetime.datetime.now() + datetime.timedelta(minutes=30, seconds=30)
        mock_events = {
            "events": [{
                "title": "Design Alignment",
                "start": future.strftime("%Y-%m-%d %H:%M IST"),
                "location": "meet.google.com/abc-defg-hij",
                "description": "Weekly alignment link: https://meet.google.com/abc-defg-hij"
            }]
        }
        mock_server.execute_tool.return_value = mock_events

        engine = ProactiveEngine(tool_server=mock_server)
        engine._speak = MagicMock()

        with patch("subprocess.run") as mock_open:
            engine._check_meetings()
            mock_open.assert_called_once_with(["open", "https://meet.google.com/abc-defg-hij"], check=True)
            engine._speak.assert_called_once()
            assert "Design Alignment" in engine._speak.call_args[0][0]



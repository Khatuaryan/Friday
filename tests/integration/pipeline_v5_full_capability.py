"""
Integration Test — Phase Set 5 Full Capability Verification.

Validates all 14 capability tools, safety guards, verbal confirmation payloads,
and correct action mappings within the unified pipeline.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.server import MCPToolServer
from src.core.brain import FridayBrain
from src.modules.voice_pipeline import VoicePipeline


class TestPipelineFullCapability:

    def test_all_fourteen_tools_registered(self):
        """Verify that the tool server registers all 14 tools cleanly."""
        server = MCPToolServer()
        names = server.get_tool_names()
        
        expected_tools = [
            "get_calendar_events",
            "read_file",
            "get_system_info",
            "control_application",
            "control_media",
            "clipboard",
            "manage_calendar",
            "manage_reminders",
            "write_filesystem",
            "execute_shell",
            "send_message",
            "manage_email",
            "web_search",
            "get_weather"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in names, f"Missing registered tool: {tool_name}"
        assert len(names) >= 14

    def test_e2e_voice_confirmation_gate_confirmed(self):
        """Test the end-to-end voice pipeline confirmation flow for destructive actions."""
        # 1. Setup mocks
        mock_stt = MagicMock()
        # Voice pipeline will listen for verbal confirmation, return "yes"
        mock_stt.listen.return_value = "yes, please confirm"

        mock_tts = MagicMock()

        brain = FridayBrain()
        brain._loaded = True

        # Construct voice pipeline
        pipeline = VoicePipeline(stt=mock_stt, tts=mock_tts, brain=brain)

        # 2. Mock a destructive user request (e.g., delete a file)
        # We mock think_full to return the confirmation alert response
        mock_action_desc = "permanently delete the file at 'test.txt'"
        mock_tool_result = {
            "requires_confirmation": True,
            "action_description": mock_action_desc,
            "pending_action": {
                "name": "write_filesystem",
                "arguments": {"action": "delete_file", "path": "test.txt", "_confirmed": True}
            }
        }

        # Mock brain.think_full returning the warning prompt, and setting pending_confirmation
        with patch.object(FridayBrain, "think_full") as mock_think, \
             patch.object(FridayBrain, "execute_pending_tool") as mock_execute:
            
            mock_think.return_value = f"I'm about to {mock_action_desc}. Please say confirm to proceed, or cancel."
            brain.pending_confirmation = mock_tool_result
            
            mock_execute.return_value = {
                "status": "success",
                "confirmation_message": "Successfully deleted the file at 'test.txt'."
            }

            # Run voice pipeline command loop
            response = pipeline.process_voice_command()

            # Verify TTS verbal alert was spoken
            mock_tts.speak.assert_any_call(
                f"I'm about to {mock_action_desc}. Please say confirm to proceed, or cancel.",
                blocking=True
            )
            # Verify user speech confirmation was requested
            mock_stt.listen.assert_any_call(timeout=8.0)
            
            # Verify execution triggered since user said "yes"
            mock_execute.assert_called_once()
            
            # Verify final confirmation message spoken
            mock_tts.speak.assert_any_call("Successfully deleted the file at 'test.txt'.", blocking=True)
            assert response == "Successfully deleted the file at 'test.txt'."

    def test_e2e_voice_confirmation_gate_cancelled(self):
        """Test the end-to-end voice pipeline confirmation flow when user says cancel or is silent."""
        mock_stt = MagicMock()
        mock_stt.listen.return_value = "no, cancel it"

        mock_tts = MagicMock()

        brain = FridayBrain()
        brain._loaded = True

        pipeline = VoicePipeline(stt=mock_stt, tts=mock_tts, brain=brain)

        mock_action_desc = "execute a shell command"
        mock_tool_result = {
            "requires_confirmation": True,
            "action_description": mock_action_desc,
            "pending_action": {
                "name": "execute_shell",
                "arguments": {"command": "ls", "_confirmed": True}
            }
        }

        with patch.object(FridayBrain, "think_full") as mock_think, \
             patch.object(FridayBrain, "execute_pending_tool") as mock_execute:
            
            mock_think.return_value = f"I'm about to {mock_action_desc}. Please say confirm to proceed, or cancel."
            brain.pending_confirmation = mock_tool_result

            response = pipeline.process_voice_command()

            # Verify TTS verbal alert was spoken
            mock_tts.speak.assert_any_call(
                f"I'm about to {mock_action_desc}. Please say confirm to proceed, or cancel.",
                blocking=True
            )
            
            # Verify execution was NOT triggered
            mock_execute.assert_not_called()
            
            # Verify pending confirmation is cleared
            assert brain.pending_confirmation is None
            
            # Verify cancellation message spoken
            mock_tts.speak.assert_any_call("Okay, cancelled.", blocking=True)
            assert response == "Okay, cancelled."

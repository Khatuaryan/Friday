"""
Message Tool — Send iMessages via macOS Messages App automation with forced verbal confirmation.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.message")


class MessageTool(Tool):
    """Sends iMessages on macOS using AppleScript."""

    @property
    def name(self) -> str:
        return "send_message"

    @property
    def description(self) -> str:
        return "Send an iMessage to a recipient phone number or email using native Messages.app"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Recipient's phone number or email address (e.g. '+1234567890' or 'friend@example.com')",
                },
                "message": {
                    "type": "string",
                    "description": "Body of the text message to send",
                },
                "_confirmed": {
                    "type": "boolean",
                    "description": "Internal flag verifying verbal user confirmation",
                    "default": False,
                },
            },
            "required": ["recipient", "message"],
        }

    def execute(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        recipient = recipient.strip()
        message = message.strip()

        if not recipient or not message:
            return {"error": "recipient and message are required parameters"}

        # Forced confirmation engine gate
        if not kwargs.get("_confirmed", False):
            return {
                "requires_confirmation": True,
                "action_description": f"send an iMessage to '{recipient}' containing '{message}'",
                "pending_action": {
                    "name": "send_message",
                    "arguments": {"recipient": recipient, "message": message, "_confirmed": True},
                },
            }

        return self._send_imessage(recipient, message)

    def _send_imessage(self, recipient: str, message: str) -> Dict[str, Any]:
        # Escape quotes for AppleScript
        escaped_message = message.replace('"', '\\"')
        
        # AppleScript command to send iMessage
        applescript = f'''
        tell application "Messages"
            try
                set targetService to 1st service whose service type is iMessage
                set targetBuddy to buddy "{recipient}" of targetService
                send "{escaped_message}" to targetBuddy
                return "success"
            on error errMsg
                try
                    -- Fallback to general buddy lookup if first service type is not active
                    set targetBuddy to buddy "{recipient}"
                    send "{escaped_message}" to targetBuddy
                    return "success"
                on error errMsg2
                    return errMsg2
                end try
            end try
        end tell
        '''

        try:
            res = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=15.0
            )

            output = res.stdout.strip()
            if "success" in output:
                return {
                    "status": "success",
                    "recipient": recipient,
                    "message": message,
                    "confirmation_message": f"Successfully sent the iMessage to '{recipient}'.",
                }
            else:
                err = res.stderr.strip() or output or "Recipient not found or Messages app unauthorized"
                return {"error": f"AppleScript execution failed: {err}"}
        except subprocess.TimeoutExpired:
            return {"error": "iMessage sending timed out"}
        except Exception as e:
            logger.error("Failed to send iMessage: %s", e)
            return {"error": str(e)}

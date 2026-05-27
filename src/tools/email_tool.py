"""
Email Tool — Draft and send emails via native macOS Mail.app with confirmation gates for sending.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.email")


class EmailTool(Tool):
    """Interfaces with macOS Mail.app via AppleScript."""

    @property
    def name(self) -> str:
        return "manage_email"

    @property
    def description(self) -> str:
        return "Draft or send an email to a recipient via macOS Mail.app"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["draft", "send"],
                    "description": "Email action: 'draft' (non-destructive) or 'send' (requires confirmation)",
                },
                "recipient": {
                    "type": "string",
                    "description": "Recipient's email address (e.g. 'colleague@example.com')",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject line of the email",
                },
                "body": {
                    "type": "string",
                    "description": "Email body content",
                },
                "_confirmed": {
                    "type": "boolean",
                    "description": "Internal flag verifying verbal user confirmation",
                    "default": False,
                },
            },
            "required": ["action", "recipient", "subject", "body"],
        }

    def execute(self, action: str, recipient: str, subject: str, body: str, **kwargs) -> Dict[str, Any]:
        recipient = recipient.strip()
        subject = subject.strip()
        body = body.strip()

        if not recipient or not subject or not body:
            return {"error": "recipient, subject, and body are required"}

        if action == "draft":
            return self._draft_email(recipient, subject, body)

        elif action == "send":
            # Destructive/active action requires confirmation
            if not kwargs.get("_confirmed", False):
                return {
                    "requires_confirmation": True,
                    "action_description": f"send the email to '{recipient}' with subject '{subject}'",
                    "pending_action": {
                        "name": "manage_email",
                        "arguments": {
                            "action": "send",
                            "recipient": recipient,
                            "subject": subject,
                            "body": body,
                            "_confirmed": True,
                        },
                    },
                }
            return self._send_email(recipient, subject, body)

        else:
            return {"error": f"Invalid email action: {action}"}

    def _draft_email(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        # Escape quotes for AppleScript
        subj_esc = subject.replace('"', '\\"')
        body_esc = body.replace('"', '\\"')

        applescript = f'''
        tell application "Mail"
            try
                set new_message to make new outgoing message with properties {{subject:"{subj_esc}", content:"{body_esc}", visible:true}}
                tell new_message
                    make new to recipient at end of to recipients with properties {{address:"{recipient}"}}
                end tell
                activate
                return "success"
            on error errMsg
                return errMsg
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
                    "action": "draft",
                    "recipient": recipient,
                    "subject": subject,
                    "message": "Draft created successfully in Mail.app.",
                }
            else:
                err = res.stderr.strip() or output
                return {"error": f"AppleScript failed: {err}"}
        except Exception as e:
            logger.error("Failed to draft email: %s", e)
            return {"error": str(e)}

    def _send_email(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        # Escape quotes for AppleScript
        subj_esc = subject.replace('"', '\\"')
        body_esc = body.replace('"', '\\"')

        applescript = f'''
        tell application "Mail"
            try
                set new_message to make new outgoing message with properties {{subject:"{subj_esc}", content:"{body_esc}", visible:false}}
                tell new_message
                    make new to recipient at end of to recipients with properties {{address:"{recipient}"}}
                    send
                end tell
                return "success"
            on error errMsg
                return errMsg
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
                    "action": "send",
                    "recipient": recipient,
                    "subject": subject,
                    "confirmation_message": f"Successfully sent the email to '{recipient}'.",
                }
            else:
                err = res.stderr.strip() or output
                return {"error": f"AppleScript failed: {err}"}
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return {"error": str(e)}

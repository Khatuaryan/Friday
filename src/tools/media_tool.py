"""
Media Control Tool — Control system volume and music applications (Music/Spotify) via AppleScript.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.media")


class MediaControlTool(Tool):
    """Control system audio and media playback (Apple Music / Spotify)."""

    @property
    def name(self) -> str:
        return "control_media"

    @property
    def description(self) -> str:
        return "Control media playback (play, pause, skip) and adjust system volume"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "play",
                        "pause",
                        "next_track",
                        "previous_track",
                        "set_volume",
                        "get_volume",
                        "get_now_playing",
                        "mute",
                        "unmute",
                    ],
                    "description": "The media or volume control action to execute",
                },
                "volume": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Target volume level (required only for set_volume)",
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, volume: int | None = None) -> Dict[str, Any]:
        if action == "set_volume":
            if volume is None:
                return {"error": "volume parameter is required for set_volume"}
            return self._set_volume(volume)
        elif action == "get_volume":
            return self._get_volume()
        elif action == "mute":
            return self._set_mute(True)
        elif action == "unmute":
            return self._set_mute(False)
        elif action in ["play", "pause", "next_track", "previous_track", "get_now_playing"]:
            return self._playback_action(action)
        else:
            return {"error": f"Invalid action: {action}"}

    def _run_applescript(self, script: str) -> str:
        """Helper to run AppleScript and return stdout or raise Exception."""
        result = subprocess.run(
            ["osascript", "-e", script], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def _set_volume(self, level: int) -> Dict[str, Any]:
        try:
            self._run_applescript(f"set volume output volume {level}")
            return {"status": "set", "volume": level}
        except Exception as e:
            logger.error("Failed to set volume to %d: %s", level, e)
            return {"error": f"Failed to set volume: {e}"}

    def _get_volume(self) -> Dict[str, Any]:
        try:
            vol_str = self._run_applescript("output volume of (get volume settings)")
            return {"volume": int(vol_str)}
        except Exception as e:
            logger.error("Failed to query volume: %s", e)
            return {"error": f"Failed to get volume: {e}"}

    def _set_mute(self, mute: bool) -> Dict[str, Any]:
        state = "with" if mute else "without"
        status = "muted" if mute else "unmuted"
        try:
            self._run_applescript(f"set volume {state} output muted")
            return {"status": status}
        except Exception as e:
            logger.error("Failed to toggle mute state to %s: %s", mute, e)
            return {"error": f"Failed to adjust mute state: {e}"}

    def _playback_action(self, action: str) -> Dict[str, Any]:
        if action == "get_now_playing":
            script = """
            tell application "System Events"
                set musicRunning to exists (processes whose name is "Music")
                set spotifyRunning to exists (processes whose name is "Spotify")
            end tell
            if musicRunning then
                tell application "Music"
                    if player state is playing then
                        return "Music: " & name of current track & " - " & artist of current track
                    end if
                end tell
            end if
            if spotifyRunning then
                tell application "Spotify"
                    if player state is playing then
                        return "Spotify: " & name of current track & " - " & artist of current track
                    end if
                end tell
            end if
            return "nothing playing"
            """
            try:
                res = self._run_applescript(script)
                if res == "nothing playing" or not res:
                    return {"status": "nothing playing"}
                
                # Format response nicely
                parts = res.split(": ", 1)
                source = parts[0]
                details = parts[1].split(" - ", 1) if len(parts) > 1 else ["Unknown", "Unknown"]
                track = details[0]
                artist = details[1] if len(details) > 1 else "Unknown"
                return {"status": "playing", "source": source, "track": track, "artist": artist}
            except Exception as e:
                logger.error("Failed to query now playing info: %s", e)
                return {"status": "nothing playing", "note": str(e)}

        # Direct media control keys
        app_command = {
            "play": "play",
            "pause": "pause",
            "next_track": "next track",
            "previous_track": "previous track",
        }[action]

        script = f"""
        tell application "System Events"
            set musicRunning to exists (processes whose name is "Music")
            set spotifyRunning to exists (processes whose name is "Spotify")
        end tell
        if musicRunning then
            tell application "Music" to {app_command}
            return "Music"
        elif spotifyRunning then
            tell application "Spotify" to {app_command}
            return "Spotify"
        else
            error "No active media application running"
        end if
        """

        try:
            target = self._run_applescript(script)
            return {"status": "done", "action": action, "target": target}
        except Exception as e:
            logger.warning("Playback action '%s' failed (no active media app found): %s", action, e)
            return {"error": "No media app (Music or Spotify) running or available"}

import time
from src.utils.logger import get_logger
import threading
import os
import datetime
import re
import subprocess
from collections import deque
from typing import Any, Dict

logger = get_logger("friday.proactive_engine")


class ProactiveEngine:
    """
    Background daemon for meeting reminders, daily briefings, and health breaks.

    TTS arbitration:
        The engine holds a reference to the ActivationHandler. Before speaking,
        it checks `activation_handler.state`. If the pipeline is in any state
        other than LISTENING or IDLE, the utterance is deferred to a retry
        queue and attempted on the next loop cycle. This prevents the proactive
        engine from speaking over an active wake-word → voice interaction.
    """

    BREAK_INTERVAL_SECONDS = 45 * 60  # 45 minutes for workspace app breaks

    def __init__(self, context_tracker=None, voice_pipeline=None, activation_handler=None, tool_server=None):
        self.context_tracker = context_tracker
        self.voice_pipeline = voice_pipeline
        self.activation_handler = activation_handler
        self._tool_server = tool_server

        self._running = False
        self._thread = None

        self._last_break_suggestion = time.time()
        self._daily_briefing_done = False
        self._eod_summary_done = False
        self._notified_meetings = set()

        # Deferred messages when pipeline is busy
        self._deferred: deque[tuple[str, str]] = deque(maxlen=5)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._engine_loop, daemon=True, name="friday-proactive")
        self._thread.start()
        logger.info("Proactive Engine started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Proactive Engine stopped.")

    def _pipeline_is_busy(self) -> bool:
        """Check if the activation pipeline is currently handling a voice interaction."""
        if not self.activation_handler:
            return False
        state = self.activation_handler.state
        # Only safe to speak when the pipeline is idle or passively listening
        return state.value not in ("idle", "listening")

    def _show_notification(self, title: str, message: str):
        """Route notification through IPC to Swift HUD instead of macOS alerts."""
        if self.activation_handler and self.activation_handler.ipc_bridge:
            self.activation_handler.ipc_bridge.update_text(
                last_command="", last_response=f"[{title}] {message}"
            )
            self.activation_handler.ipc_bridge.write_status("speaking")
        logger.info("Proactive notification: %s — %s", title, message)

    def _speak(self, text: str, notification_title: str = "F.R.I.D.A.Y.",
               notification_msg: str = ""):
        """
        Speak via TTS only if the activation pipeline is not busy.
        If busy, defer the message for the next cycle.
        """
        if self._pipeline_is_busy():
            logger.info("Pipeline busy — deferring proactive message: %s", text[:60])
            self._deferred.append((text, notification_msg))
            return

        # Show notification regardless
        if notification_msg:
            self._show_notification(notification_title, notification_msg)

        if self.voice_pipeline and hasattr(self.voice_pipeline, 'tts'):
            # Don't block the engine loop
            threading.Thread(
                target=self.voice_pipeline.tts.speak,
                args=(text, True),
                daemon=True,
            ).start()

    def _drain_deferred(self):
        """Attempt to deliver any deferred messages if the pipeline is now free."""
        while self._deferred and not self._pipeline_is_busy():
            text, notif = self._deferred.popleft()
            logger.info("Delivering deferred proactive message: %s", text[:60])
            self._speak(text, notification_msg=notif)

    def trigger_calendar_sync(self):
        # Stub for future calendar API integration
        pass

    def _check_health_breaks(self):
        now = time.time()

        if self.context_tracker:
            history = self.context_tracker.get_context_history()
            if history:
                current_context = history[-1]
                current_app = current_context.get("app", "Unknown App")
                
                # Check if user remains in the same workspace app continuously for >45 minutes
                cutoff = now - 45 * 60
                recent_entries = [h for h in history if h.get("timestamp", 0) >= cutoff]
                
                # Filter for regular workspace apps (excluding Finder, System apps etc. if blacklisted)
                all_same_app = all(h.get("app") == current_app for h in recent_entries)
                
                # Find start time of continuous usage of this app in history
                first_app_entry = None
                for h in reversed(history):
                    if h.get("app") == current_app:
                        first_app_entry = h
                    else:
                        break
                
                if first_app_entry and (now - first_app_entry.get("timestamp", 0) >= 45 * 60) and all_same_app:
                    if now - self._last_break_suggestion > self.BREAK_INTERVAL_SECONDS:
                        logger.info("Triggering break suggestion for focus app: %s", current_app)
                        self._speak(
                            f"Excuse me boss, you've been working on {current_app} for over 45 minutes. Might I suggest a short stretch break?",
                            notification_msg=f"Active in {current_app} for >45 mins. Time to stretch!",
                        )
                        self._last_break_suggestion = now
                        return

            # Fallback legacy break logic
            last_activity = self.context_tracker.last_activity_time
            if (now - last_activity < 300) and (now - self._last_break_suggestion > 90 * 60):
                logger.info("Triggering standard break suggestion.")
                self._speak(
                    "Excuse me boss, you've been working for 90 minutes. Might I suggest a short break?",
                    notification_msg="You've been active for 90 minutes. Consider taking a short break.",
                )
                self._last_break_suggestion = now

    def _check_daily_briefing(self):
        now = datetime.datetime.now()

        # Reset at midnight
        if now.hour == 0:
            self._daily_briefing_done = False

        # Trigger at 8 AM if not done
        if now.hour == 8 and not self._daily_briefing_done:
            logger.info("Triggering morning briefing.")
            
            event_msg = "You have no meetings scheduled for today."
            if hasattr(self, "_tool_server") and self._tool_server is not None:
                try:
                    res = self._tool_server.execute_tool({
                        "name": "get_calendar_events",
                        "arguments": {"date": "today"}
                    })
                    events = res.get("events", [])
                    if events and not any("error" in e for e in events):
                        count = len(events)
                        titles = ", ".join(e.get("title", "Untitled") for e in events[:3])
                        event_msg = f"You have {count} meetings scheduled for today, including: {titles}."
                    
                    # Open Calendar app
                    self._tool_server.execute_tool({
                        "name": "control_application",
                        "arguments": {"action": "open", "app_name": "Calendar"}
                    })
                except Exception as e:
                    logger.warning("Failed to construct daily briefing calendar: %s", e)

            self._speak(
                f"Good morning boss. I've prepared your daily briefing. {event_msg}",
                notification_msg="Morning Briefing is ready.",
            )
            self._daily_briefing_done = True

    def _check_eod_summary(self):
        """Trigger EOD summary at 6:00 PM."""
        now = datetime.datetime.now()
        
        # Reset at midnight
        if now.hour == 0:
            self._eod_summary_done = False
            
        if now.hour == 18 and not self._eod_summary_done:
            logger.info("Triggering EOD summary.")
            reminders_msg = ""
            if hasattr(self, "_tool_server") and self._tool_server is not None:
                try:
                    res = self._tool_server.execute_tool({
                        "name": "manage_reminders",
                        "arguments": {"action": "list"}
                    })
                    reminders = res.get("reminders", [])
                    incomplete = [r for r in reminders if not r.get("completed")]
                    if incomplete:
                        titles = ", ".join(r.get("title", "Untitled") for r in incomplete[:3])
                        reminders_msg = f" You still have {len(incomplete)} incomplete reminders, including: {titles}."
                    else:
                        reminders_msg = " You have completed all your tasks for today."
                except Exception as e:
                    logger.warning("Failed to fetch reminders for EOD: %s", e)

            self._speak(
                f"Excuse me boss, it's 6:00 PM. Here is your end of day summary.{reminders_msg} Shall we plan tomorrow's schedule?",
                notification_msg="End of Day Summary is ready.",
            )
            self._eod_summary_done = True

    def _check_meetings(self):
        """Check for upcoming meetings (30 minutes and 5 minutes before) and open links."""
        if not hasattr(self, "_tool_server") or self._tool_server is None:
            return

        now = datetime.datetime.now()
        # Fetch today's calendar events
        try:
            res = self._tool_server.execute_tool({
                "name": "get_calendar_events",
                "arguments": {"date": "today"}
            })
            events = res.get("events", [])
        except Exception as e:
            logger.warning("Failed to fetch calendar events in proactive engine: %s", e)
            return

        for event in events:
            if not isinstance(event, dict) or "error" in event:
                continue
            title = event.get("title", "Untitled Meeting")
            start_str = event.get("start", "")
            if not start_str:
                continue

            try:
                # Parse start time, format: YYYY-MM-DD HH:MM IST
                clean_start_str = start_str.replace(" IST", "").strip()
                start_dt = datetime.datetime.strptime(clean_start_str, "%Y-%m-%d %H:%M")
            except Exception:
                continue

            delta = start_dt - now
            minutes_to_start = delta.total_seconds() / 60.0

            # Match Zoom, Google Meet, and Teams meeting URLs
            location = event.get("location", "")
            description = event.get("description", "")
            
            # Simple URL regex to search location and description
            url_match = re.search(r'https?://[^\s<>"]+', location + "\n" + description)
            if not url_match:
                continue

            meeting_url = url_match.group(0)
            
            # Verify if it's a meeting domain
            is_meeting = False
            for domain in ["meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com"]:
                if domain in meeting_url:
                    is_meeting = True
                    break

            if not is_meeting:
                continue

            # Alert points: 30 minutes and 5 minutes before event
            for alert_min in [30, 5]:
                # Trigger within a 60-second window
                if alert_min - 0.5 <= minutes_to_start <= alert_min + 0.5:
                    alert_key = (title, start_str, alert_min)
                    
                    if alert_key not in self._notified_meetings:
                        self._notified_meetings.add(alert_key)
                        
                        # Open the meeting URL automatically!
                        try:
                            subprocess.run(["open", meeting_url], check=True)
                            logger.info("Automatically opened meeting URL: %s", meeting_url)
                        except Exception as e:
                            logger.error("Failed to open meeting URL %s: %s", meeting_url, e)

                        self._speak(
                            f"Excuse me boss, your meeting '{title}' starts in {alert_min} minutes. I've automatically opened the meeting link for you.",
                            notification_msg=f"Meeting '{title}' in {alert_min}m. Opening link...",
                        )

    def _engine_loop(self):
        while self._running:
            try:
                self._drain_deferred()
                self._check_health_breaks()
                self._check_daily_briefing()
                self._check_eod_summary()
                self._check_meetings()
            except Exception as e:
                logger.debug(f"Proactive Engine Error: {e}")

            time.sleep(30)  # Check every 30 seconds

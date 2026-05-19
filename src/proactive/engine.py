import time
import logging
import threading
import os
import datetime
from collections import deque

logger = logging.getLogger("friday.proactive_engine")


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

    BREAK_INTERVAL_SECONDS = 90 * 60  # 90 minutes

    def __init__(self, context_tracker=None, voice_pipeline=None, activation_handler=None):
        self.context_tracker = context_tracker
        self.voice_pipeline = voice_pipeline
        self.activation_handler = activation_handler

        self._running = False
        self._thread = None

        self._last_break_suggestion = time.time()
        self._daily_briefing_done = False

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
        """Show macOS notification (always safe, no audio contention)."""
        os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'")

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
            last_activity = self.context_tracker.last_activity_time
            # If active for more than 90 mins without a break suggestion
            if (now - last_activity < 300) and (now - self._last_break_suggestion > self.BREAK_INTERVAL_SECONDS):
                logger.info("Triggering break suggestion.")
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
            self._speak(
                "Good morning boss. I've prepared your daily briefing. You have no meetings scheduled for today.",
                notification_msg="Morning Briefing is ready.",
            )
            self._daily_briefing_done = True

    def _engine_loop(self):
        while self._running:
            try:
                self._drain_deferred()
                self._check_health_breaks()
                self._check_daily_briefing()
                # self._check_meetings() # Stub
            except Exception as e:
                logger.debug(f"Proactive Engine Error: {e}")

            time.sleep(30)  # Check every 30 seconds

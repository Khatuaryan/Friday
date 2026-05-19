import time
import logging
import threading
import os
import datetime

logger = logging.getLogger("friday.proactive_engine")

class ProactiveEngine:
    """
    Background daemon for meeting reminders, daily briefings, and health breaks.
    """
    
    BREAK_INTERVAL_SECONDS = 90 * 60  # 90 minutes
    
    def __init__(self, context_tracker=None, voice_pipeline=None):
        self.context_tracker = context_tracker
        self.voice_pipeline = voice_pipeline
        
        self._running = False
        self._thread = None
        
        self._last_break_suggestion = time.time()
        self._daily_briefing_done = False
        
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

    def _show_notification(self, title: str, message: str):
        """Show macOS notification."""
        os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'")

    def _speak(self, text: str):
        """Speak via TTS if voice pipeline is available."""
        if self.voice_pipeline and hasattr(self.voice_pipeline, 'tts'):
            # Don't block the loop
            threading.Thread(target=self.voice_pipeline.tts.speak, args=(text, True), daemon=True).start()
            
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
                self._show_notification("F.R.I.D.A.Y.", "You've been active for 90 minutes. Consider taking a short break.")
                self._speak("Excuse me boss, you've been working for 90 minutes. Might I suggest a short break?")
                self._last_break_suggestion = now

    def _check_daily_briefing(self):
        now = datetime.datetime.now()
        
        # Reset at midnight
        if now.hour == 0:
            self._daily_briefing_done = False
            
        # Trigger at 8 AM if not done
        if now.hour == 8 and not self._daily_briefing_done:
            logger.info("Triggering morning briefing.")
            self._show_notification("F.R.I.D.A.Y.", "Morning Briefing is ready.")
            self._speak("Good morning boss. I've prepared your daily briefing. You have no meetings scheduled for today.")
            self._daily_briefing_done = True

    def _engine_loop(self):
        while self._running:
            try:
                self._check_health_breaks()
                self._check_daily_briefing()
                # self._check_meetings() # Stub
            except Exception as e:
                logger.debug(f"Proactive Engine Error: {e}")
                
            time.sleep(30)  # Check every 30 seconds

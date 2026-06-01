import time
from src.utils.logger import get_logger
import threading
from typing import Dict, Any, List, Optional
import AppKit
import Quartz

logger = get_logger("friday.context_tracker")

class ContextTracker:
    """
    Monitors active macOS application and window using PyObjC (NSWorkspace and Quartz).
    Non-blocking background thread.
    """
    
    BLACKLIST = {"com.apple.iCal", "com.apple.mail", "com.apple.keychainaccess"}
    
    def __init__(self, history_size: int = 10, poll_interval: float = 2.0):
        self.history_size = history_size
        self.poll_interval = poll_interval
        
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._last_activity = time.time()

    @property
    def last_activity_time(self) -> float:
        with self._lock:
            return self._last_activity

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="friday-context-tracker")
        self._thread.start()
        logger.info("Context Tracker started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 1)
        logger.info("Context Tracker stopped.")

    def _get_active_app_info(self) -> Optional[Dict[str, Any]]:
        try:
            workspace = AppKit.NSWorkspace.sharedWorkspace()
            active_app = workspace.frontmostApplication()
            
            if not active_app:
                return None
                
            bundle_id = active_app.bundleIdentifier()
            app_name = active_app.localizedName()
            
            if bundle_id in self.BLACKLIST:
                return None
                
            # Use Quartz to get active window title safely
            window_title = ""
            options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
            window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
            
            for window in window_list:
                # Find the window belonging to the active app
                if window.get(Quartz.kCGWindowOwnerPID) == active_app.processIdentifier():
                    # kCGWindowName might be missing
                    title = window.get(Quartz.kCGWindowName, "")
                    if title:
                        window_title = str(title)
                        break
                        
            return {
                "app": str(app_name),
                "bundle_id": str(bundle_id),
                "window": window_title,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.debug(f"Failed to get active app info: {e}")
            return None

    def _poll_loop(self):
        while self._running:
            info = self._get_active_app_info()
            
            if info:
                with self._lock:
                    # Update activity if context changed
                    if not self._history or (self._history[-1]["app"] != info["app"] or self._history[-1]["window"] != info["window"]):
                        self._history.append(info)
                        self._last_activity = info["timestamp"]
                        if len(self._history) > self.history_size:
                            self._history.pop(0)
            
            time.sleep(self.poll_interval)

    def get_current_context(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._history[-1] if self._history else None
            
    def get_context_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

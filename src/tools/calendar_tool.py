"""
Calendar Tool — Read macOS Calendar via EventKit.

Handles async EventKit authorization properly using a semaphore
to block until the OS permission dialog resolves.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .base import Tool

logger = logging.getLogger("friday.tools.calendar")


class CalendarTool(Tool):
    """Read macOS Calendar events via native EventKit framework."""

    _authorized: bool | None = None  # Class-level auth cache

    @property
    def name(self) -> str:
        return "get_calendar_events"

    @property
    def description(self) -> str:
        return "Get calendar events for a specific date or date range"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date: 'today', 'tomorrow', or 'YYYY-MM-DD'",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default: 1)",
                    "default": 1,
                },
            },
            "required": ["date"],
        }

    def execute(self, date: str = "today", days: int = 1) -> Dict[str, Any]:
        """Get calendar events for a date range."""
        start_date = self._parse_date(date)
        end_date = start_date + timedelta(days=days)

        events = self._get_events(start_date, end_date)

        return {
            "events": events,
            "date_range": f"{start_date.date()} to {end_date.date()}",
            "count": len(events),
        }

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse date string to datetime."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if date_str.lower() == "today":
            return today
        elif date_str.lower() == "tomorrow":
            return today + timedelta(days=1)
        elif date_str.lower() == "yesterday":
            return today - timedelta(days=1)
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")

    def _get_events(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get events from macOS Calendar via EventKit."""
        try:
            from EventKit import EKEntityTypeEvent, EKEventStore
            from Foundation import NSDate
        except ImportError:
            return [{"error": "EventKit not available — install pyobjc-framework-EventKit"}]

        store = EKEventStore.alloc().init()

        # Handle async authorization with a semaphore
        if CalendarTool._authorized is None:
            auth_result = [False]
            sem = threading.Semaphore(0)

            def auth_callback(granted, error):
                auth_result[0] = granted
                if error:
                    logger.error("Calendar auth error: %s", error)
                sem.release()

            store.requestAccessToEntityType_completion_(
                EKEntityTypeEvent, auth_callback
            )

            # Block until OS permission dialog resolves (timeout 30s)
            if not sem.acquire(timeout=30):
                logger.error("Calendar authorization timed out")
                return [{"error": "Calendar access timed out"}]

            CalendarTool._authorized = auth_result[0]

        if not CalendarTool._authorized:
            return [{"error": "Calendar access denied — grant in System Preferences"}]

        # Convert to NSDate
        start_ns = NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp())
        end_ns = NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp())

        # Fetch events
        calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            start_ns, end_ns, calendars
        )
        ek_events = store.eventsMatchingPredicate_(predicate)

        events = []
        for ek_event in ek_events or []:
            try:
                local_dt = datetime.fromtimestamp(
                    ek_event.startDate().timeIntervalSince1970()
                )
                end_dt = datetime.fromtimestamp(
                    ek_event.endDate().timeIntervalSince1970()
                )
                start_str = local_dt.strftime("%Y-%m-%d %H:%M IST")
                end_str = end_dt.strftime("%Y-%m-%d %H:%M IST")
            except Exception:
                start_str = str(ek_event.startDate().description())
                end_str = str(ek_event.endDate().description())

            events.append({
                "title": str(ek_event.title() or "Untitled"),
                "start": start_str,
                "end": end_str,
                "location": str(ek_event.location() or ""),
                "all_day": bool(ek_event.isAllDay()),
                "description": str(ek_event.notes() or ""),
            })

        return events

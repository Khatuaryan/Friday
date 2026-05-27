"""
Calendar Write Tool — Create and delete events in macOS Calendar via EventKit.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger("friday.tools.calendar_write")


class CalendarWriteTool(Tool):
    """Create and delete calendar events in macOS Calendar via native EventKit framework."""

    _authorized: bool | None = None  # Class-level auth cache

    @property
    def name(self) -> str:
        return "manage_calendar"

    @property
    def description(self) -> str:
        return "Create or delete events in the macOS Calendar"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_event", "delete_event"],
                    "description": "Calendar action: 'create_event' or 'delete_event'",
                },
                "title": {
                    "type": "string",
                    "description": "Event title (required for create_event)",
                },
                "date": {
                    "type": "string",
                    "description": "Event date in YYYY-MM-DD format (required for create_event)",
                },
                "time": {
                    "type": "string",
                    "description": "Event start time in 24h HH:MM format, e.g. '14:30' (required for create_event)",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Event duration in minutes (default: 60)",
                    "default": 60,
                },
                "location": {
                    "type": "string",
                    "description": "Event location (optional)",
                },
                "notes": {
                    "type": "string",
                    "description": "Event description or notes (optional)",
                },
                "event_id": {
                    "type": "string",
                    "description": "The target event identifier (required for delete_event)",
                },
                "_confirmed": {
                    "type": "boolean",
                    "description": "Internal flag verifying verbal user confirmation",
                    "default": False,
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        if action == "create_event":
            title = kwargs.get("title")
            date = kwargs.get("date")
            time_str = kwargs.get("time")
            if not title or not date or not time_str:
                return {"error": "title, date, and time are required for create_event"}
            
            duration = int(kwargs.get("duration_minutes", 60))
            location = kwargs.get("location")
            notes = kwargs.get("notes")
            return self._create_event(title, date, time_str, duration, location, notes)

        elif action == "delete_event":
            event_id = kwargs.get("event_id")
            if not event_id:
                return {"error": "event_id is required for delete_event"}
            
            # Gated confirmation pattern (Phase 5C integration)
            if not kwargs.get("_confirmed", False):
                return {
                    "requires_confirmation": True,
                    "action_description": f"permanently delete the calendar event '{event_id}'",
                    "pending_action": {
                        "name": "manage_calendar",
                        "arguments": {"action": "delete_event", "event_id": event_id, "_confirmed": True},
                    },
                }
            
            return self._delete_event(event_id)
        else:
            return {"error": f"Invalid action: {action}"}

    def _get_store(self) -> Any:
        """Resolve store and ensure permissions."""
        try:
            from EventKit import EKEntityTypeEvent, EKEventStore
        except ImportError:
            raise ImportError("EventKit not available — install pyobjc-framework-EventKit")

        store = EKEventStore.alloc().init()

        # Handle async authorization with a semaphore
        if CalendarWriteTool._authorized is None:
            auth_result = [False]
            sem = threading.Semaphore(0)

            def auth_callback(granted, error):
                auth_result[0] = granted
                if error:
                    logger.error("Calendar write auth error: %s", error)
                sem.release()

            store.requestAccessToEntityType_completion_(
                EKEntityTypeEvent, auth_callback
            )

            # Block until OS permission dialog resolves (timeout 30s)
            if not sem.acquire(timeout=30):
                raise TimeoutError("Calendar authorization timed out")

            CalendarWriteTool._authorized = auth_result[0]

        if not CalendarWriteTool._authorized:
            raise PermissionError("Calendar access denied — grant in System Preferences")

        return store

    def _create_event(
        self, title: str, date: str, time_str: str, duration: int, location: str | None, notes: str | None
    ) -> Dict[str, Any]:
        try:
            from EventKit import EKEvent
            from Foundation import NSDate
        except ImportError:
            return {"error": "EventKit/Foundation frameworks are not available"}

        try:
            store = self._get_store()
            
            # Parse date + time
            dt_str = f"{date} {time_str}"
            start_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration)

            start_ns = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
            end_ns = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

            calendar = store.defaultCalendarForNewEvents()
            if not calendar:
                return {"error": "No default calendar found for new events"}

            event = EKEvent.eventWithEventStore_(store)
            event.setTitle_(title)
            event.setStartDate_(start_ns)
            event.setEndDate_(end_ns)
            event.setCalendar_(calendar)

            if location:
                event.setLocation_(location)
            if notes:
                event.setNotes_(notes)

            # EKSpanThisEvent = 0
            success, error = store.saveEvent_span_commit_error_(event, 0, True, None)

            if success:
                return {
                    "status": "created",
                    "title": title,
                    "start": start_dt.strftime("%Y-%m-%d %H:%M IST"),
                    "end": end_dt.strftime("%Y-%m-%d %H:%M IST"),
                    "event_id": str(event.eventIdentifier()),
                }
            else:
                err_msg = str(error) if error else "Unknown error"
                return {"error": f"Failed to save event via EventKit: {err_msg}"}
        except Exception as e:
            logger.error("Failed to create calendar event: %s", e)
            return {"error": str(e)}

    def _delete_event(self, event_id: str) -> Dict[str, Any]:
        try:
            store = self._get_store()
            event = store.eventWithIdentifier_(event_id)
            if not event:
                return {"error": f"Event with ID '{event_id}' not found"}

            title = str(event.title() or "Untitled")
            # EKSpanThisEvent = 0
            success, error = store.removeEvent_span_commit_error_(event, 0, True, None)

            if success:
                return {
                    "status": "deleted",
                    "event_id": event_id,
                    "confirmation_message": f"Successfully deleted the calendar event '{title}'.",
                }
            else:
                err_msg = str(error) if error else "Unknown error"
                return {"error": f"Failed to delete event: {err_msg}"}
        except Exception as e:
            logger.error("Failed to delete calendar event: %s", e)
            return {"error": str(e)}

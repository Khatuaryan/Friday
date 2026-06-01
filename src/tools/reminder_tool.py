"""
Reminders Tool — Create, list, and complete macOS Reminders via EventKit.
"""

from __future__ import annotations

from src.utils.logger import get_logger
import threading
from datetime import datetime
from typing import Any, Dict

from .base import Tool

logger = get_logger("friday.tools.reminder")


class ReminderTool(Tool):
    """Create, list, and complete tasks in macOS Reminders via native EventKit framework."""

    _authorized: bool | None = None  # Class-level auth cache

    @property
    def name(self) -> str:
        return "manage_reminders"

    @property
    def description(self) -> str:
        return "Create, list, or complete reminders in macOS Reminders"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "complete"],
                    "description": "Reminder action: 'create', 'list', or 'complete'",
                },
                "title": {
                    "type": "string",
                    "description": "Reminder title (required for create action)",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in YYYY-MM-DD format (optional for create)",
                },
                "due_time": {
                    "type": "string",
                    "description": "Due time in HH:MM format, e.g. '09:00' (optional for create)",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional description or notes (optional for create)",
                },
                "reminder_id": {
                    "type": "string",
                    "description": "Identifier of the reminder to mark complete (required for complete action)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of reminders to list (default: 10)",
                    "default": 10,
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        if action == "create":
            title = kwargs.get("title")
            if not title:
                return {"error": "title is required for create action"}
            
            due_date = kwargs.get("due_date")
            due_time = kwargs.get("due_time")
            notes = kwargs.get("notes")
            return self._create_reminder(title, due_date, due_time, notes)

        elif action == "list":
            limit = int(kwargs.get("limit", 10))
            return self._list_reminders(limit)

        elif action == "complete":
            reminder_id = kwargs.get("reminder_id")
            if not reminder_id:
                return {"error": "reminder_id is required for complete action"}
            return self._complete_reminder(reminder_id)
        else:
            return {"error": f"Invalid action: {action}"}

    def _get_store(self) -> Any:
        """Resolve store and ensure reminder permissions."""
        try:
            from EventKit import EKEntityTypeReminder, EKEventStore
        except ImportError:
            raise ImportError("EventKit not available — install pyobjc-framework-EventKit")

        store = EKEventStore.alloc().init()

        # Handle async authorization with a semaphore
        if ReminderTool._authorized is None:
            auth_result = [False]
            sem = threading.Semaphore(0)

            def auth_callback(granted, error):
                auth_result[0] = granted
                if error:
                    logger.error("Reminders auth error: %s", error)
                sem.release()

            store.requestAccessToEntityType_completion_(
                EKEntityTypeReminder, auth_callback
            )

            # Block until OS permission dialog resolves (timeout 30s)
            if not sem.acquire(timeout=30):
                raise TimeoutError("Reminders authorization timed out")

            ReminderTool._authorized = auth_result[0]

        if not ReminderTool._authorized:
            raise PermissionError("Reminders access denied — grant in System Preferences")

        return store

    def _create_reminder(
        self, title: str, due_date: str | None, due_time: str | None, notes: str | None
    ) -> Dict[str, Any]:
        try:
            from EventKit import EKReminder
            from Foundation import NSDateComponents
        except ImportError:
            return {"error": "EventKit/Foundation frameworks are not available"}

        try:
            store = self._get_store()
            reminder = EKReminder.reminderWithEventStore_(store)
            reminder.setTitle_(title)
            
            # Select default reminders calendar list
            calendar = store.defaultCalendarForNewReminders()
            if not calendar:
                return {"error": "No default reminders list found"}
            reminder.setCalendar_(calendar)

            if due_date:
                dt_str = f"{due_date} {due_time or '09:00'}"
                due_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                
                comps = NSDateComponents.alloc().init()
                comps.setYear_(due_dt.year)
                comps.setMonth_(due_dt.month)
                comps.setDay_(due_dt.day)
                comps.setHour_(due_dt.hour)
                comps.setMinute_(due_dt.minute)
                reminder.setDueDateComponents_(comps)

            if notes:
                reminder.setNotes_(notes)

            success, error = store.saveReminder_commit_error_(reminder, True, None)

            if success:
                return {
                    "status": "created",
                    "title": title,
                    "reminder_id": str(reminder.calendarItemIdentifier()),
                }
            else:
                err_msg = str(error) if error else "Unknown error"
                return {"error": f"Failed to save reminder: {err_msg}"}
        except Exception as e:
            logger.error("Failed to create reminder: %s", e)
            return {"error": str(e)}

    def _list_reminders(self, limit: int) -> Dict[str, Any]:
        try:
            store = self._get_store()
            
            # Fetch incomplete reminders
            predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
                None, None, None
            )

            fetched = [None]
            sem = threading.Semaphore(0)

            def completion(reminders):
                fetched[0] = reminders
                sem.release()

            store.fetchRemindersMatchingPredicate_completion_(predicate, completion)

            if not sem.acquire(timeout=15):
                return {"error": "Listing reminders timed out"}

            reminders_list = []
            for rem in (fetched[0] or [])[:limit]:
                due_str = None
                comps = rem.dueDateComponents()
                if comps:
                    try:
                        due_str = f"{comps.year()}-{comps.month():02d}-{comps.day():02d}"
                        if comps.hour() != -1 and comps.minute() != -1:
                            due_str += f" {comps.hour():02d}:{comps.minute():02d}"
                    except Exception:
                        pass

                reminders_list.append({
                    "title": str(rem.title() or "Untitled"),
                    "id": str(rem.calendarItemIdentifier() or ""),
                    "notes": str(rem.notes() or ""),
                    "due": due_str,
                })

            return {"reminders": reminders_list, "count": len(reminders_list)}
        except Exception as e:
            logger.error("Failed to list reminders: %s", e)
            return {"error": str(e)}

    def _complete_reminder(self, reminder_id: str) -> Dict[str, Any]:
        try:
            store = self._get_store()
            reminder = store.calendarItemWithIdentifier_(reminder_id)
            if not reminder:
                return {"error": f"Reminder with ID '{reminder_id}' not found"}

            title = str(reminder.title() or "Untitled")
            reminder.setCompleted_(True)

            success, error = store.saveReminder_commit_error_(reminder, True, None)

            if success:
                return {
                    "status": "completed",
                    "reminder_id": reminder_id,
                    "title": title,
                    "confirmation_message": f"Marked reminder '{title}' as completed.",
                }
            else:
                err_msg = str(error) if error else "Unknown error"
                return {"error": f"Failed to complete reminder: {err_msg}"}
        except Exception as e:
            logger.error("Failed to complete reminder: %s", e)
            return {"error": str(e)}

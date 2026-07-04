"""Task (VTODO) operations for CalDavClient (mixin)."""

from __future__ import annotations

import logging
from typing import Any

from ._shared import Task, _comp_dt, _comp_text, _wrap_caldav_op

logger = logging.getLogger(__name__)


class _TaskOpsMixin:
    """Mixin providing VTODO task operations.

    Mixed into :class:`CalDavClient` alongside the other domain mixins.
    """

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_task(obj: Any, calendar_id: str = "") -> Task:
        """Convert a caldav VTODO object to our :class:`Task`.

        Reads via caldav 2.0's ``icalendar_component`` (the ``icalendar`` lib),
        same pattern as ``_to_calendar_event`` but for VTODO fields.
        """
        comp = obj.icalendar_component

        return Task(
            uid=_comp_text(comp, "UID"),
            summary=_comp_text(comp, "SUMMARY"),
            description=_comp_text(comp, "DESCRIPTION"),
            dtstart=_comp_dt(comp, "DTSTART"),
            due=_comp_dt(comp, "DUE"),
            status=_comp_text(comp, "STATUS"),
            calendar_id=calendar_id,
        )

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list tasks")
    def list_tasks(self, calendar_id: str = "") -> list[Task]:
        """Return all VTODO tasks from CalDAV calendar collections.

        When *calendar_id* is empty, tasks are aggregated from **all**
        calendars.  Each task is tagged with its source ``calendar_id``.
        """
        logger.debug("list_tasks calendar_id=%r", calendar_id)
        aggregated: list[Task] = []
        for cal in self._iter_calendars(calendar_id):
            results = cal.search(todo=True)
            aggregated.extend(self._to_task(r, calendar_id=cal.name) for r in results)
        return aggregated

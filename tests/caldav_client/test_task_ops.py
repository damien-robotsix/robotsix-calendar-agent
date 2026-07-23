"""Tests for task operations — listing, aggregation, conversion."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from robotsix_calendar_agent.caldav_client import CalDavClient, Task
from tests.caldav_client.conftest import _mock_vtodo

# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_returns_list_of_tasks(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.return_value = [
            _mock_vtodo(uid="task-1"),
            _mock_vtodo(uid="task-2", summary="Second task"),
        ]

        result = client.list_tasks()

        assert len(result) == 2
        assert isinstance(result[0], Task)
        assert result[0].uid == "task-1"
        assert result[1].uid == "task-2"


class TestListTasksAggregation:
    def test_aggregates_across_all_calendars_when_calendar_id_empty(
        self, client: CalDavClient
    ) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vtodo(uid="task-a")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.search.return_value = [
            _mock_vtodo(uid="task-b1"),
            _mock_vtodo(uid="task-b2"),
        ]
        cal_c = MagicMock(name="Damien")
        cal_c.name = "Damien"
        cal_c.search.return_value = []  # VTODO collections with no tasks
        client._principal.calendars.return_value = [cal_a, cal_b, cal_c]

        result = client.list_tasks()

        assert len(result) == 3
        assert result[0].uid == "task-a"
        assert result[0].calendar_id == "Robotsix"
        assert result[1].uid == "task-b1"
        assert result[1].calendar_id == "Birthdays"
        assert result[2].uid == "task-b2"
        assert result[2].calendar_id == "Birthdays"

    def test_single_calendar_when_id_provided(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vtodo(uid="task-a")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client.list_tasks(calendar_id="Robotsix")

        assert len(result) == 1
        assert result[0].uid == "task-a"
        cal_b.search.assert_not_called()


class TestToTask:
    def test_all_fields_parsed_from_ical(self) -> None:
        """VTODO fields map correctly via _to_task."""
        import datetime

        values: dict[str, Any] = {
            "UID": "task-1",
            "SUMMARY": "Buy milk",
            "DESCRIPTION": "Get 2%",
            "DTSTART": MagicMock(dt=datetime.datetime(2026, 6, 20, 8, 0, 0)),
            "DUE": MagicMock(dt=datetime.date(2026, 6, 21)),
            "STATUS": "NEEDS-ACTION",
        }
        comp = MagicMock()
        comp.get.side_effect = lambda name, default=None: values.get(name, default)
        obj = MagicMock()
        obj.icalendar_component = comp

        task = CalDavClient._to_task(obj, calendar_id="cal")

        assert task.uid == "task-1"
        assert task.summary == "Buy milk"
        assert task.description == "Get 2%"
        assert task.dtstart == "2026-06-20T08:00:00"
        assert task.due == "2026-06-21"
        assert task.status == "NEEDS-ACTION"
        assert task.calendar_id == "cal"

    def test_missing_fields_yield_empty(self) -> None:
        comp = MagicMock()
        comp.get.side_effect = lambda _name, default=None: default
        obj = MagicMock()
        obj.icalendar_component = comp

        task = CalDavClient._to_task(obj)

        assert task.uid == ""
        assert task.summary == ""
        assert task.description == ""
        assert task.dtstart == ""
        assert task.due == ""
        assert task.status == ""
        assert task.calendar_id == ""

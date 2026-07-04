"""Tests for CalendarAgent — all external deps mocked."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Shared helpers live in conftest.

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalendarAgentInit:
    def test_creates_with_env_vars(self) -> None:
        os.environ["RADICALE_URL"] = "https://x.com"
        os.environ["RADICALE_USERNAME"] = "u"
        os.environ["RADICALE_PASSWORD"] = "p"

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            agent = CalendarAgent()
            assert agent._agent_id == "calendar"

    def test_raises_value_error_for_missing_credentials(self) -> None:
        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            with pytest.raises(ValueError, match="credentials"):
                CalendarAgent()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_start_and_stop_are_no_ops(self, calendar_agent: MagicMock) -> None:
        # start/stop are now no-ops but must not raise
        calendar_agent.start()
        calendar_agent.stop()

    def test_context_manager(self, calendar_agent: MagicMock) -> None:
        with calendar_agent as ctx:
            assert ctx is calendar_agent


# ---------------------------------------------------------------------------
# Dispatch-enum consistency
# ---------------------------------------------------------------------------


class TestDispatchEnumSync:
    """Verify _DISPATCH keys stay in sync with all operation enums."""

    def test_dispatch_keys_match_enum_values(self) -> None:
        from robotsix_calendar_agent.agent import _DISPATCH
        from robotsix_calendar_agent.intent_parser import (
            CalendarOperation,
            ContactOperation,
            TaskOperation,
        )

        dispatch_keys = set(_DISPATCH)
        enum_values = (
            {m.value for m in CalendarOperation}
            | {m.value for m in ContactOperation}
            | {m.value for m in TaskOperation}
        )
        assert dispatch_keys == enum_values, (
            f"Mismatch: extra in dict={dispatch_keys - enum_values}, "
            f"missing={enum_values - dispatch_keys}"
        )


# ---------------------------------------------------------------------------
# Telemetry counters
# ---------------------------------------------------------------------------


class TestTelemetry:
    def test_counters_initialise_to_zero(self, calendar_agent: MagicMock) -> None:
        assert calendar_agent._request_count == 0
        assert calendar_agent._error_count == 0
        assert calendar_agent._in_flight == 0
        assert calendar_agent._started_at is not None
        assert calendar_agent._last_request_ts is None

    def test_monitor_snapshot_contains_live_counters(
        self, calendar_agent: MagicMock
    ) -> None:
        calendar_agent._mock_caldav.health.return_value = {
            "connected": True,
            "calendar_count": 1,
        }
        calendar_agent._mock_caldav._url = "https://rad.example.com"
        calendar_agent._mock_caldav._default_calendar = "TestCal"

        snap = calendar_agent.monitor_snapshot()
        assert snap["agent_id"] == "calendar"
        assert snap["request_count"] == 0
        assert snap["error_count"] == 0
        assert snap["in_flight"] == 0
        assert isinstance(snap["uptime_seconds"], float)
        assert snap["uptime_seconds"] >= 0
        assert snap["caldav_health"]["connected"] is True
        assert snap["caldav_health"]["calendar_count"] == 1


# ---------------------------------------------------------------------------
# _summarize_item unit tests
# ---------------------------------------------------------------------------


class TestSummarizeItem:
    def test_bare_string_passthrough(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        assert _summarize_item("hello") == "hello"  # type: ignore[arg-type]

    def test_task_with_due_and_status(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Buy milk",
                "due": "2026-06-21",
                "status": "NEEDS-ACTION",
                "uid": "t1",
            }
        )
        assert result == "Buy milk due 2026-06-21 [NEEDS-ACTION] [uid=t1]"

    def test_task_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21"})
        assert result == "(untitled) due 2026-06-21"

    def test_task_untitled_no_fields(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21", "uid": "t2"})
        assert "(untitled)" in result
        assert "[uid=t2]" in result

    def test_event_with_summary_and_dtstart_and_location(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Lunch",
                "dtstart": "2026-01-02T12:00:00",
                "location": "Office",
                "uid": "e1",
            }
        )
        assert result == "Lunch at 2026-01-02T12:00:00 (Office) [uid=e1]"

    def test_event_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "Meeting", "dtstart": "2026-07-01"})
        assert result == "Meeting at 2026-07-01"

    def test_event_without_dtstart_summary_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "No time event"})
        assert result == "No time event"

    def test_contact_with_name_and_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe", "email": "jane@example.com"})
        assert result == "Jane Doe <jane@example.com>"

    def test_contact_without_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe"})
        assert result == "Jane Doe"

    def test_contact_without_name(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"email": "anon@example.com"})
        assert result == "(no name) <anon@example.com>"

    def test_unknown_dict_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"color": "blue", "size": 3})
        # Should fall through to json.dumps
        assert "color" in result
        assert "blue" in result


# ---------------------------------------------------------------------------
# _render_reply unit tests
# ---------------------------------------------------------------------------


class TestRenderReply:
    def test_deleted_confirmation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("delete_event", {"deleted": True}) == (
            "Done — the item was deleted."
        )

    def test_empty_list_events(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", []) == "No events found."

    def test_empty_list_calendars(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_calendars", []) == "No calendars found."

    def test_empty_list_tasks(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_tasks", []) == "No tasks found."

    def test_empty_list_contacts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_contacts", []) == "No contacts found."

    def test_empty_list_unknown_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("frobnicate", []) == "No items found."

    def test_non_empty_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_events",
            [
                {"summary": "Lunch", "dtstart": "2026-01-02T12:00:00", "uid": "e1"},
                {"summary": "Dinner", "dtstart": "2026-01-02T19:00:00"},
            ],
        )
        assert result.startswith("Found 2:\n")
        assert "Lunch" in result
        assert "Dinner" in result
        assert "- " in result

    def test_dict_update_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "update_event", {"summary": "Updated meeting", "uid": "e1"}
        )
        assert result.startswith("Updated: ")

    def test_dict_create_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("create_event", {"summary": "New event", "uid": "e2"})
        assert result.startswith("Created: ")

    def test_dict_other_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("delete_event", {"summary": "X"})
        assert result.startswith("Result: ")

    def test_fallback_non_dict_non_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", 42) == "42"
        assert _render_reply("list_events", "plain") == "plain"

    def test_list_with_calendar_strings(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("list_calendars", ["Robotsix", "Birthdays"])
        assert "Found 2" in result
        assert "Robotsix" in result
        assert "Birthdays" in result

    def test_list_with_contact_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_contacts",
            [{"full_name": "John Doe", "email": "j@x.com"}, {"full_name": "Jane"}],
        )
        assert "Found 2" in result
        assert "John Doe" in result
        assert "Jane" in result

    def test_list_with_task_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_tasks",
            [
                {
                    "summary": "Buy milk",
                    "due": "2026-06-21",
                    "status": "NEEDS-ACTION",
                    "uid": "t1",
                }
            ],
        )
        assert "Found 1" in result
        assert "Buy milk" in result

    def test_deleted_not_true_is_not_deleted_branch(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        # {"deleted": False} should NOT match the deleted branch — falls to dict branch
        result = _render_reply("delete_event", {"deleted": False, "uid": "e1"})
        assert result != "Done — the item was deleted."
        assert "Result:" in result


# ---------------------------------------------------------------------------
# _build_add_to_calendar_instruction
# ---------------------------------------------------------------------------


class TestBuildAddToCalendarInstruction:
    """Tests for _build_add_to_calendar_instruction — the synthetic
    instruction builder that bridges structured add_to_calendar payloads
    to the LLM intent parser."""

    def test_explicit_dates_produce_direct_instruction(self) -> None:
        from robotsix_calendar_agent.agent import _build_add_to_calendar_instruction

        instruction = _build_add_to_calendar_instruction(
            {
                "subject": "Team Lunch",
                "suggested_dtstart": "2026-06-01T12:00:00",
                "suggested_dtend": "2026-06-01T13:00:00",
            }
        )
        assert "add event:" in instruction
        assert "subject=Team Lunch" in instruction
        assert "dtstart=2026-06-01T12:00:00" in instruction
        assert "dtend=2026-06-01T13:00:00" in instruction
        assert "Create a calendar event" not in instruction

    def test_explicit_dates_include_description_and_location(self) -> None:
        from robotsix_calendar_agent.agent import _build_add_to_calendar_instruction

        instruction = _build_add_to_calendar_instruction(
            {
                "subject": "Team Lunch",
                "suggested_dtstart": "2026-06-01T12:00:00",
                "suggested_dtend": "2026-06-01T13:00:00",
                "description": "Monthly sync",
                "location": "Room A",
            }
        )
        assert "description=Monthly sync" in instruction
        assert "location=Room A" in instruction

    def test_no_explicit_dates_delegates_to_resolution_instruction(self) -> None:
        from robotsix_calendar_agent.agent import _build_add_to_calendar_instruction

        instruction = _build_add_to_calendar_instruction(
            {
                "subject": "Team Lunch",
                "body_text": "Let's meet at noon.",
                "email_date": "2026-03-15",
                "extracted_dates": ["2026-03-20", "noon"],
                "description": "Monthly team gathering",
                "location": "Conference Room B",
            }
        )
        # Should use the resolution instruction pattern, not the "add event:" pattern
        assert "add event:" not in instruction
        assert "Create a calendar event for the following email." in instruction
        assert "Email subject: Team Lunch" in instruction
        assert "Description: Monthly team gathering" in instruction
        assert "Location: Conference Room B" in instruction
        assert "Email date: 2026-03-15" in instruction
        assert "Date/time references found: 2026-03-20, noon" in instruction
        assert "Email body:" in instruction
        assert "Let's meet at noon." in instruction
        assert "Resolve a concrete start and end datetime in ISO 8601" in instruction

    def test_no_explicit_dates_minimal_payload(self) -> None:
        from robotsix_calendar_agent.agent import _build_add_to_calendar_instruction

        instruction = _build_add_to_calendar_instruction({"subject": "Quick Call"})
        assert "Create a calendar event for the following email." in instruction
        assert "Email subject: Quick Call" in instruction
        assert "Description:" not in instruction
        assert "Location:" not in instruction
        assert "Email date:" not in instruction
        assert "Date/time references found:" not in instruction
        assert "Email body:" not in instruction
        assert "Resolve a concrete start and end datetime in ISO 8601" in instruction

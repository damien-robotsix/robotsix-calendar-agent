"""Shared pytest fixtures and helpers for CalendarAgent tests."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, settings

# Re-export the session-scoped integration fixture so it is explicitly
# available to all test modules.
from tests.caldav_client.caldav_test_server import caldav_client  # noqa: F401

# ---------------------------------------------------------------------------
# Hypothesis profile registration
# ---------------------------------------------------------------------------
settings.register_profile(
    "ci",
    max_examples=200,
    derandomize=True,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "dev",
    max_examples=50,
    deadline=5000,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
# In CI (GitHub Actions sets CI=true) default to the 'ci' profile;
# locally default to 'dev'.  HYPOTHESIS_PROFILE env var always wins
# when explicitly set.
_default_profile = "ci" if os.getenv("CI") == "true" else "dev"
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", _default_profile))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env() -> None:
    """Remove Radicale + logging env vars so tests don't leak state."""
    for key in (
        "RADICALE_URL",
        "RADICALE_USERNAME",
        "RADICALE_PASSWORD",
        "LOG_LEVEL",
        "JSON_LOGS",
    ):
        os.environ.pop(key, None)


@pytest.fixture
def calendar_agent() -> Any:
    """Create a CalendarAgent with all external deps mocked.

    The returned agent has ``_mock_parser`` and ``_mock_caldav``
    attributes attached for test assertions.
    """
    with (
        patch(
            "robotsix_calendar_agent.agent.CalDavClient",
            autospec=True,
        ) as mock_caldav,
        patch(
            "robotsix_calendar_agent.agent.IntentParser",
            autospec=True,
        ) as mock_parser_cls,
    ):
        mock_parser = MagicMock()
        mock_parser_cls.return_value = mock_parser

        os.environ["RADICALE_URL"] = "https://radicale.example.com"
        os.environ["RADICALE_USERNAME"] = "user"
        os.environ["RADICALE_PASSWORD"] = "pass"  # pragma: allowlist secret

        from robotsix_calendar_agent.agent import CalendarAgent

        agent = CalendarAgent()
        agent._mock_parser = mock_parser  # type: ignore[attr-defined]
        agent._mock_caldav = mock_caldav.return_value  # type: ignore[attr-defined]

        yield agent

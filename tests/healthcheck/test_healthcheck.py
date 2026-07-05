"""Unit tests for the Docker HEALTHCHECK probe."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr


def _make_mock_settings(
    url: str = "https://radicale.example.com",
    username: str = "user",
    password: str = "pass",  # noqa: S107
    default_calendar: str = "cal",
) -> MagicMock:
    """Return a MagicMock Settings with the given credential fields."""
    settings = MagicMock()
    settings.RADICALE_URL = url
    settings.RADICALE_USERNAME = username
    settings.RADICALE_PASSWORD = SecretStr(password)
    settings.RADICALE_DEFAULT_CALENDAR = default_calendar
    return settings


def _make_mock_client(health_result: dict[str, Any]) -> MagicMock:
    """Return a MagicMock CalDavClient with :meth:`health` stubbed."""
    client = MagicMock()
    client.health.return_value = health_result
    return client


# ---------------------------------------------------------------------------
# main() — credential validation
# ---------------------------------------------------------------------------


class TestMainMissingCredentials:
    """``main()`` exits early when required credentials are missing."""

    @pytest.mark.parametrize(
        ("url", "username", "password"),
        [
            ("", "user", "pass"),
            ("https://x", "", "pass"),
            ("https://x", "user", ""),
        ],
    )
    def test_exits_code_1_when_credential_missing(
        self, url: str, username: str, password: str
    ) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings(url=url, username=username, password=password)

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# main() — success branches
# ---------------------------------------------------------------------------


class TestMainSuccess:
    """``main()`` exits 0 when the CalDAV server responds."""

    def test_success_on_first_attempt(self, capsys: pytest.CaptureFixture[str]) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client = _make_mock_client({"connected": True, "calendar_count": 3})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "healthcheck OK:" in captured.out
        assert "connected" in captured.out
        mock_sleep.assert_not_called()

    def test_success_after_one_retry(self, capsys: pytest.CaptureFixture[str]) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client_fail = _make_mock_client({"connected": False, "error": "timeout"})
        client_ok = _make_mock_client({"connected": True, "calendar_count": 1})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                side_effect=[client_fail, client_ok],
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 0
        mock_sleep.assert_called_once_with(2)


# ---------------------------------------------------------------------------
# main() — failure branches
# ---------------------------------------------------------------------------


class TestMainFailure:
    """``main()`` exits 1 after all retries are exhausted."""

    def test_all_retries_exhausted_connected_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client = _make_mock_client({"connected": False, "error": "refused"})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "healthcheck FAILED after 3 attempts" in captured.err

    def test_retry_then_all_exhausted(self, capsys: pytest.CaptureFixture[str]) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client = _make_mock_client({"connected": False, "error": "boom"})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1
        # 3 attempts → 2 sleep calls (no sleep after last failure)
        assert mock_sleep.call_count == 2

    def test_exception_during_client_creation(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                side_effect=ValueError("bad url"),
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "healthcheck FAILED after 3 attempts" in captured.err


# ---------------------------------------------------------------------------
# main() — mixed retry scenarios
# ---------------------------------------------------------------------------


class TestMainRetryLogic:
    """Edge cases in the retry loop."""

    def test_second_attempt_exception_third_connected(
        self,
    ) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client_fail1 = _make_mock_client({"connected": False, "error": "e1"})
        client_ok = _make_mock_client({"connected": True, "calendar_count": 2})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                side_effect=[client_fail1, ValueError("crash"), client_ok],
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 0

    def test_stderr_on_each_failed_attempt(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from robotsix_calendar_agent.healthcheck import main

        settings = _make_mock_settings()
        client = _make_mock_client({"connected": False, "error": "nope"})

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit),
        ):
            main()

        captured = capsys.readouterr()
        assert "attempt 1/3 failed: nope" in captured.err
        assert "attempt 2/3 failed: nope" in captured.err
        # Third failure prints "FAILED after 3 attempts" —
        # there is no "attempt 3/3 failed" line.

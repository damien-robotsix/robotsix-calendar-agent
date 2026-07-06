"""Tests for the Docker HEALTHCHECK probe."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_settings_mock(
    url: str = "https://radicale.example.com",
    username: str = "testuser",
    password: str = "testpass",  # noqa: S107
    default_calendar: str = "default-cal",
) -> MagicMock:
    """Build a Settings mock with the given credential values."""
    settings = MagicMock()
    settings.RADICALE_URL = url
    settings.RADICALE_USERNAME = username
    pw_mock = MagicMock()
    pw_mock.get_secret_value.return_value = password
    settings.RADICALE_PASSWORD = pw_mock
    settings.RADICALE_DEFAULT_CALENDAR = default_calendar
    return settings


class TestCredentialsMissing:
    """When required credentials are missing, main() exits with code 1."""

    @pytest.mark.parametrize(
        "url,username,password",
        [
            ("", "user", "pass"),
            ("https://r.example.com", "", "pass"),
            ("https://r.example.com", "user", ""),
            ("", "", ""),
        ],
    )
    def test_exits_1_when_credential_missing(
        self, url: str, username: str, password: str
    ) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock(url=url, username=username, password=password)

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch("robotsix_calendar_agent.healthcheck.CalDavClient") as mock_caldav,
            pytest.raises(SystemExit) as exc_info,
        ):
            healthcheck.main()

        assert exc_info.value.code == 1
        mock_caldav.assert_not_called()


class TestSuccessPath:
    """When the CalDAV health check returns connected=True, main() exits 0."""

    def test_exits_0_on_successful_health(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.return_value = {"connected": True}

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            healthcheck.main()

        assert exc_info.value.code == 0
        mock_sleep.assert_not_called()


class TestFailureExhausted:
    """When all retry attempts fail, main() exits with code 1."""

    def test_exits_1_when_health_returns_not_connected(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.return_value = {"connected": False, "error": "timeout"}

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            healthcheck.main()

        assert exc_info.value.code == 1
        # 3 attempts total: sleep called between attempts 1 and 2, and 2 and 3
        assert mock_sleep.call_count == 2

    def test_exits_1_when_health_raises(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.side_effect = RuntimeError("connection refused")

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            healthcheck.main()

        assert exc_info.value.code == 1
        assert mock_sleep.call_count == 2


class TestRetryLogic:
    """Retry behaviour: retries up to 3 times with 2-second delays."""

    def test_retries_exactly_three_times(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.return_value = {"connected": False, "error": "boom"}

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit),
        ):
            healthcheck.main()

        # CalDavClient created 3 times and health() called 3 times
        assert mock_client.health.call_count == 3

    def test_succeeds_on_second_attempt(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.side_effect = [
            {"connected": False, "error": "first fail"},
            {"connected": True},
        ]

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            healthcheck.main()

        assert exc_info.value.code == 0
        assert mock_client.health.call_count == 2
        mock_sleep.assert_called_once_with(2)

    def test_sleep_delay_is_two_seconds(self) -> None:
        from robotsix_calendar_agent import healthcheck

        settings = _make_settings_mock()
        mock_client = MagicMock()
        mock_client.health.return_value = {"connected": False, "error": "fail"}

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                return_value=mock_client,
            ),
            patch("robotsix_calendar_agent.healthcheck.time.sleep") as mock_sleep,
            pytest.raises(SystemExit),
        ):
            healthcheck.main()

        mock_sleep.assert_called_with(2)
        assert all(call.args == (2,) for call in mock_sleep.call_args_list)

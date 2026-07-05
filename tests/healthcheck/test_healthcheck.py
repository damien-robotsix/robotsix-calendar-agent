"""Tests for the Docker HEALTHCHECK probe."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings_mock(
    url: str = "https://radicale.example.com",
    username: str = "user",
    password: str = "pass",  # noqa: S107
    default_calendar: str = "Robotsix",
) -> MagicMock:
    """Return a MagicMock mimicking a Settings instance."""
    settings = MagicMock()
    settings.RADICALE_URL = url
    settings.RADICALE_USERNAME = username
    settings.RADICALE_PASSWORD.get_secret_value.return_value = password
    settings.RADICALE_DEFAULT_CALENDAR = default_calendar
    return settings


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestHealthCheckMain:
    # -- missing credentials -------------------------------------------------

    @pytest.mark.parametrize(
        "missing_field",
        ["url", "username", "password"],
    )
    def test_exits_1_when_credential_is_empty(self, missing_field: str) -> None:
        kwargs: dict[str, str] = {
            "url": "https://radicale.example.com",
            "username": "user",
            "password": "pass",
        }
        kwargs[missing_field] = ""

        settings = _make_settings_mock(**kwargs)

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch("robotsix_calendar_agent.healthcheck.CalDavClient"),
            patch("robotsix_calendar_agent.healthcheck.time.sleep"),
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 1

    # -- successful first attempt --------------------------------------------

    def test_exits_0_on_first_successful_health_check(self) -> None:
        settings = _make_settings_mock()

        mock_client_cls = MagicMock()
        mock_client = mock_client_cls.return_value
        mock_client.health.return_value = {"connected": True, "version": "3.0.0"}

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                mock_client_cls,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.time.sleep",
            ) as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 0
        mock_sleep.assert_not_called()

    # -- transient failure then success (retry) ------------------------------

    def test_retries_on_failure_then_succeeds(self) -> None:
        settings = _make_settings_mock()

        mock_client_cls = MagicMock()
        mock_client = mock_client_cls.return_value
        # First call: not connected; second call: connected
        mock_client.health.side_effect = [
            {"connected": False, "error": "timeout"},
            {"connected": True},
        ]

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                mock_client_cls,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.time.sleep",
            ) as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 0
        mock_sleep.assert_called_once()
        assert mock_client.health.call_count == 2

    # -- all retries exhausted -----------------------------------------------

    def test_exits_1_after_all_retries_exhausted(self) -> None:
        settings = _make_settings_mock()

        mock_client_cls = MagicMock()
        mock_client = mock_client_cls.return_value
        mock_client.health.return_value = {
            "connected": False,
            "error": "connection refused",
        }

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                mock_client_cls,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.time.sleep",
            ) as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 1
        # RETRIES=3, so sleep called between attempts 1→2 and 2→3
        assert mock_sleep.call_count == 2
        assert mock_client.health.call_count == 3

    # -- exception handling --------------------------------------------------

    def test_handles_exception_and_retries(self) -> None:
        settings = _make_settings_mock()

        mock_client_cls = MagicMock()
        mock_client = mock_client_cls.return_value
        mock_client.health.side_effect = [
            ConnectionError("refused"),
            {"connected": True},
        ]

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                mock_client_cls,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.time.sleep",
            ) as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 0
        mock_sleep.assert_called_once()
        assert mock_client.health.call_count == 2

    def test_exits_1_when_all_attempts_raise_exceptions(self) -> None:
        settings = _make_settings_mock()

        mock_client_cls = MagicMock()
        mock_client = mock_client_cls.return_value
        mock_client.health.side_effect = ConnectionError("refused")

        with (
            patch(
                "robotsix_calendar_agent.healthcheck.Settings",
                return_value=settings,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.CalDavClient",
                mock_client_cls,
            ),
            patch(
                "robotsix_calendar_agent.healthcheck.time.sleep",
            ) as mock_sleep,
            pytest.raises(SystemExit) as exc_info,
        ):
            from robotsix_calendar_agent.healthcheck import main

            main()

        assert exc_info.value.code == 1
        assert mock_sleep.call_count == 2
        assert mock_client.health.call_count == 3

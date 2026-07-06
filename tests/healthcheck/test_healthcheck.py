"""Unit tests for the Docker HEALTHCHECK probe."""

from __future__ import annotations

import pytest

from tests.healthcheck.conftest import _make_mock_client, _make_mock_settings

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
        self,
        url: str,
        username: str,
        password: str,
        healthcheck_main,
    ) -> None:
        settings = _make_mock_settings(url=url, username=username, password=password)
        excinfo, _output, _mock_sleep = healthcheck_main(settings=settings)
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# main() — success branches
# ---------------------------------------------------------------------------


class TestMainSuccess:
    """``main()`` exits 0 when the CalDAV server responds."""

    def test_success_on_first_attempt(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": True, "calendar_count": 3})
        excinfo, output, mock_sleep = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 0
        assert "healthcheck OK:" in output.out
        assert "connected" in output.out
        mock_sleep.assert_not_called()

    def test_success_after_one_retry(self, healthcheck_main) -> None:
        client_fail = _make_mock_client({"connected": False, "error": "timeout"})
        client_ok = _make_mock_client({"connected": True, "calendar_count": 1})
        excinfo, _output, mock_sleep = healthcheck_main(
            caldav_spec={"side_effect": [client_fail, client_ok]}
        )
        assert excinfo.value.code == 0
        mock_sleep.assert_called_once_with(2)


# ---------------------------------------------------------------------------
# main() — failure branches
# ---------------------------------------------------------------------------


class TestMainFailure:
    """``main()`` exits 1 after all retries are exhausted."""

    def test_all_retries_exhausted_connected_false(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": False, "error": "refused"})
        excinfo, output, _mock_sleep = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED after 3 attempts" in output.err

    def test_retry_then_all_exhausted(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": False, "error": "boom"})
        excinfo, _output, mock_sleep = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 1
        # 3 attempts → 2 sleep calls (no sleep after last failure)
        assert mock_sleep.call_count == 2

    def test_exception_during_client_creation(self, healthcheck_main) -> None:
        excinfo, output, _mock_sleep = healthcheck_main(
            caldav_spec={"side_effect": ValueError("bad url")}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED after 3 attempts" in output.err


# ---------------------------------------------------------------------------
# main() — mixed retry scenarios
# ---------------------------------------------------------------------------


class TestMainRetryLogic:
    """Edge cases in the retry loop."""

    def test_second_attempt_exception_third_connected(self, healthcheck_main) -> None:
        client_fail1 = _make_mock_client({"connected": False, "error": "e1"})
        client_ok = _make_mock_client({"connected": True, "calendar_count": 2})
        excinfo, _output, _mock_sleep = healthcheck_main(
            caldav_spec={"side_effect": [client_fail1, ValueError("crash"), client_ok]}
        )
        assert excinfo.value.code == 0

    def test_stderr_on_each_failed_attempt(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": False, "error": "nope"})
        _excinfo, output, _mock_sleep = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert "attempt 1/3 failed: nope" in output.err
        assert "attempt 2/3 failed: nope" in output.err
        # Third failure prints "FAILED after 3 attempts" —
        # there is no "attempt 3/3 failed" line.

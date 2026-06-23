"""Unit tests for the Settings class and its validators."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from robotsix_calendar_agent.settings import Settings

# ---------------------------------------------------------------------------
# _normalize_transport
# ---------------------------------------------------------------------------


class TestNormalizeTransport:
    """Tests for the ``_normalize_transport`` field validator."""

    def test_strips_whitespace(self) -> None:
        assert Settings._normalize_transport("  inprocess  ") == "inprocess"

    def test_lower_cases(self) -> None:
        assert Settings._normalize_transport("INPROCESS") == "inprocess"

    def test_mixed_case_and_whitespace(self) -> None:
        assert Settings._normalize_transport("  InProcess  ") == "inprocess"

    def test_already_normalized(self) -> None:
        assert Settings._normalize_transport("inprocess") == "inprocess"


# ---------------------------------------------------------------------------
# _validate_port
# ---------------------------------------------------------------------------


class TestValidatePort:
    """Tests for the ``_validate_port`` field validator."""

    _PORT_MSG = "BROKER_PORT must be an integer between 1 and 65535"

    # -- Valid ports ---------------------------------------------------------

    def test_valid_int_port(self) -> None:
        assert Settings._validate_port(9090) == 9090

    def test_min_port(self) -> None:
        assert Settings._validate_port(1) == 1

    def test_max_port(self) -> None:
        assert Settings._validate_port(65535) == 65535

    def test_valid_string_port(self) -> None:
        assert Settings._validate_port("9090") == 9090

    # -- Invalid ports: non-numeric strings ----------------------------------

    def test_non_numeric_string_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port("abc")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port("")

    # -- Invalid ports: out of range -----------------------------------------

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port(-1)

    def test_above_max_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port(65536)

    # -- Invalid ports: non-convertible types --------------------------------

    def test_none_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port(None)

    def test_list_raises(self) -> None:
        with pytest.raises(ValueError, match=self._PORT_MSG):
            Settings._validate_port([9090])


# ---------------------------------------------------------------------------
# _empty_str_to_none
# ---------------------------------------------------------------------------


class TestEmptyStrToNone:
    """Tests for the ``_empty_str_to_none`` field validator."""

    def test_empty_string_returns_none(self) -> None:
        assert Settings._empty_str_to_none("") is None

    def test_non_empty_string_unchanged(self) -> None:
        assert Settings._empty_str_to_none("/path/to/cert.pem") == "/path/to/cert.pem"

    def test_none_unchanged(self) -> None:
        assert Settings._empty_str_to_none(None) is None

    def test_non_string_type_unchanged(self) -> None:
        assert Settings._empty_str_to_none(42) == 42


# ---------------------------------------------------------------------------
# Full Settings construction with env var overrides
# ---------------------------------------------------------------------------


class TestSettingsConstruction:
    """Integration-style tests exercising ``Settings()`` with env vars."""

    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.RADICALE_URL == ""
            assert s.BROKER_HOST == ""
            assert s.BROKER_PORT == 9090
            assert s.CALENDAR_AGENT_TRANSPORT == "inprocess"

    def test_port_from_env_string(self) -> None:
        with patch.dict(os.environ, {"BROKER_PORT": "8080"}, clear=True):
            s = Settings()
            assert s.BROKER_PORT == 8080

    def test_port_from_env_int(self) -> None:
        # BaseSettings stores env vars as strings, but _validate_port
        # handles ints already — test that construction still works.
        with patch.dict(os.environ, {"BROKER_PORT": "8080"}, clear=True):
            s = Settings()
            assert s.BROKER_PORT == 8080

    def test_transport_normalized_in_construction(self) -> None:
        with patch.dict(
            os.environ,
            {"CALENDAR_AGENT_TRANSPORT": "  STDIO  "},
            clear=True,
        ):
            s = Settings()
            assert s.CALENDAR_AGENT_TRANSPORT == "stdio"

    def test_empty_mtls_fields_become_none(self) -> None:
        with patch.dict(
            os.environ,
            {"BROKER_TLS_CA": "", "BROKER_CLIENT_CERT": "", "BROKER_CLIENT_KEY": ""},
            clear=True,
        ):
            s = Settings()
            assert s.BROKER_TLS_CA is None
            assert s.BROKER_CLIENT_CERT is None
            assert s.BROKER_CLIENT_KEY is None

    def test_non_empty_mtls_fields_preserved(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BROKER_TLS_CA": "/etc/ssl/ca.pem",
                "BROKER_CLIENT_CERT": "/etc/ssl/cert.pem",
                "BROKER_CLIENT_KEY": "/etc/ssl/key.pem",
            },
            clear=True,
        ):
            s = Settings()
            assert s.BROKER_TLS_CA == "/etc/ssl/ca.pem"
            assert s.BROKER_CLIENT_CERT == "/etc/ssl/cert.pem"
            assert s.BROKER_CLIENT_KEY == "/etc/ssl/key.pem"

    def test_radicale_fields_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RADICALE_URL": "https://radicale.example.com",
                "RADICALE_USERNAME": "user",
                "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
            },
            clear=True,
        ):
            s = Settings()
            assert s.RADICALE_URL == "https://radicale.example.com"
            assert s.RADICALE_USERNAME == "user"
            assert s.RADICALE_PASSWORD.get_secret_value() == "secret"

    def test_broker_host_and_scheme_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {"BROKER_HOST": "broker.example.com", "BROKER_SCHEME": "http"},
            clear=True,
        ):
            s = Settings()
            assert s.BROKER_HOST == "broker.example.com"
            assert s.BROKER_SCHEME == "http"

    def test_invalid_port_raises_during_construction(self) -> None:
        with (
            patch.dict(os.environ, {"BROKER_PORT": "abc"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

    def test_out_of_range_port_raises_during_construction(self) -> None:
        with (
            patch.dict(os.environ, {"BROKER_PORT": "0"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

"""Long-lived service entrypoint for :class:`CalendarAgent`.

Selects the transport based on the ``CALENDAR_AGENT_TRANSPORT``
environment variable, wires the agent, and blocks until ``SIGTERM``/``SIGINT``
requests a graceful shutdown.

Transport modes:

- ``inprocess`` (or unset) — :class:`CalendarAgent` builds its own in-process
  agent (single-process / tests).
- ``brokered`` — connect to a secured broker over HTTPS using the ``BROKER_*``
  environment variables, via the shared
  :class:`robotsix_agent_comm.sdk.BrokeredAgent` (mailbox/pull mode, NAT-safe,
  self-healing across broker restarts), registered as ``robotsix-calendar``.
"""

from __future__ import annotations

import logging
import signal
import ssl
import threading
from typing import Any

from .agent import CalendarAgent

logger = logging.getLogger(__name__)

__all__ = ["main"]

#: Agent id the calendar agent registers under on the broker. auto-mail
#: addresses calendar requests to this exact id.
_DEFAULT_AGENT_ID = "robotsix-calendar"


def _build_brokered_agent() -> Any:
    """Build a :class:`BrokeredAgent` from the ``BROKER_*`` env vars.

    The deployed broker is fronted by a publicly-trusted TLS endpoint, so by
    default no CA file is needed — system trust + a bearer token. ``BROKER_TLS_CA``
    may point at a custom CA PEM for a privately-signed broker certificate.

    Mutual TLS (mTLS) is configured via ``BROKER_CLIENT_CERT`` and
    ``BROKER_CLIENT_KEY``.  When either is set, an :class:`ssl.SSLContext`
    is built with the client certificate chain and passed via
    ``ssl_context``, which takes precedence over ``tls_ca``.

    Raises:
        ValueError: If a required brokered env var is missing.
    """
    from robotsix_agent_comm.sdk import BrokeredAgent

    from .settings import Settings

    settings = Settings()

    host = settings.BROKER_HOST
    if not host:
        _MISSING_HOST_MSG = (
            "BROKER_HOST is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )
        raise ValueError(_MISSING_HOST_MSG)
    token = settings.BROKER_AGENT_TOKEN.get_secret_value()
    if not token:
        raise ValueError(
            "BROKER_AGENT_TOKEN is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    port = settings.BROKER_PORT
    scheme = settings.BROKER_SCHEME
    tls_ca = settings.BROKER_TLS_CA
    client_cert = settings.BROKER_CLIENT_CERT
    client_key = settings.BROKER_CLIENT_KEY
    agent_id = settings.CALENDAR_AGENT_ID

    # Build an explicit SSLContext when mTLS is configured, since
    # BrokeredAgent does not accept client_cert / client_key directly.
    ssl_context: ssl.SSLContext | None = None
    if client_cert and client_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if tls_ca:
            ssl_context.load_verify_locations(cafile=tls_ca)
        ssl_context.load_cert_chain(certfile=client_cert, keyfile=client_key)

    logger.info(
        "Connecting to broker at %s://%s:%d (custom CA=%s, mTLS=%s) as %s",
        scheme,
        host,
        port,
        "yes" if tls_ca else "no (system trust)",
        "yes" if ssl_context else "no",
        agent_id,
    )

    return BrokeredAgent(
        agent_id,
        broker_host=host,
        broker_port=port,
        broker_scheme=scheme,
        broker_token=token,
        tls_ca=tls_ca if ssl_context is None else None,
        ssl_context=ssl_context,
    )


def _serve_blocking(agent: CalendarAgent) -> None:
    """Start *agent* and block until ``SIGTERM``/``SIGINT`` (in-process mode)."""
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    agent.start()
    logger.info("CalendarAgent service running; awaiting shutdown signal")
    try:
        stop_event.wait()
    finally:
        agent.stop()
        logger.info("CalendarAgent service stopped")


def main() -> None:
    """Run the calendar agent as a long-lived service.

    Raises:
        ValueError: If ``CALENDAR_AGENT_TRANSPORT`` holds an unrecognised value
            or a required brokered env var is missing.
    """
    from .settings import Settings

    settings = Settings()
    mode = settings.CALENDAR_AGENT_TRANSPORT

    if mode == "brokered":
        brokered = _build_brokered_agent()
        # CalendarAgent wires its request handler onto the shared client.
        CalendarAgent(brokered.agent_id, agent=brokered)
        # BrokeredAgent.serve_forever() installs signal handlers, starts the
        # mailbox/pull loop, and blocks until SIGTERM/SIGINT.
        brokered.serve_forever()
        return

    if mode in ("", "inprocess"):
        logger.info("Using in-process transport")
        _serve_blocking(CalendarAgent())
        return

    _invalid_msg = (
        f"Invalid CALENDAR_AGENT_TRANSPORT={mode!r}; "
        "expected 'inprocess' or 'brokered'."
    )
    raise ValueError(_invalid_msg)

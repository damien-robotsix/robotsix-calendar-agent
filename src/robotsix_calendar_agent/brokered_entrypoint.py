"""Long-lived service entrypoint for :class:`CalendarAgent`.

Selects the transport based on the ``CALENDAR_AGENT_TRANSPORT``
environment variable, instantiates the agent, starts it, and blocks
until ``SIGTERM``/``SIGINT`` requests a graceful shutdown.

Transport modes:

- ``inprocess`` (or unset) — the agent constructs its own in-process
  :class:`robotsix_agent_comm.transport.Registry`.
- ``brokered`` — connect to a secured broker over TLS using the
  ``BROKER_*`` environment variables and pass the resulting transport
  client to the agent.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
from typing import Any

from .agent import CalendarAgent

logger = logging.getLogger(__name__)

__all__ = ["main"]


def _build_brokered_transport() -> Any:
    """Build the brokered transport client from the ``BROKER_*`` env vars.

    The brokered client class (``BrokerClient``) is resolved dynamically
    from :mod:`robotsix_agent_comm.transport` so that this module imports
    cleanly even on an agent-comm revision that predates the secured
    broker client. Bumping the ``robotsix-agent-comm`` pin (``uv lock``)
    to a revision that ships the brokered client is what enables this
    path at runtime.

    Raises:
        ValueError: If a required brokered env var is missing.
        RuntimeError: If the installed agent-comm has no brokered client.
    """
    import importlib

    transport_mod = importlib.import_module("robotsix_agent_comm.transport")

    host = os.environ.get("BROKER_HOST", "")
    if not host:
        raise ValueError(
            "BROKER_HOST is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    tls_ca = os.environ.get("BROKER_TLS_CA", "")
    if not tls_ca:
        raise ValueError(
            "BROKER_TLS_CA is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    token = os.environ.get("BROKER_AGENT_TOKEN", "")
    if not token:
        raise ValueError(
            "BROKER_AGENT_TOKEN is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    broker_client_cls = getattr(transport_mod, "BrokerClient", None)
    if broker_client_cls is None:  # pragma: no cover - requires newer agent-comm
        raise RuntimeError(
            "The installed robotsix-agent-comm provides no brokered transport "
            "client (robotsix_agent_comm.transport.BrokerClient). Update the "
            "robotsix-agent-comm pin (run `uv lock`) to a revision that ships "
            "the secured broker client."
        )

    port = int(os.environ.get("BROKER_PORT", "9090"))
    client_cert = os.environ.get("BROKER_CLIENT_CERT") or None
    client_key = os.environ.get("BROKER_CLIENT_KEY") or None

    logger.info(
        "Connecting to broker at %s:%d (TLS CA=%s, mTLS=%s)",
        host,
        port,
        tls_ca,
        "yes" if client_cert and client_key else "no",
    )

    return broker_client_cls(
        host=host,
        port=port,
        tls_ca=tls_ca,
        client_cert=client_cert,
        client_key=client_key,
        token=token,
    )


def _build_transport() -> Any | None:
    """Return the transport selected by ``CALENDAR_AGENT_TRANSPORT``.

    Returns ``None`` for the in-process path (so :class:`CalendarAgent`
    builds its own :class:`Registry`), or a brokered transport client
    when ``brokered`` is selected.

    Raises:
        ValueError: If the env var holds an unrecognised value, or a
            required brokered env var is missing.
    """
    mode = os.environ.get("CALENDAR_AGENT_TRANSPORT", "inprocess").strip().lower()

    if mode in ("", "inprocess"):
        logger.info("Using in-process Registry transport")
        return None

    if mode == "brokered":
        return _build_brokered_transport()

    raise ValueError(
        f"Invalid CALENDAR_AGENT_TRANSPORT={mode!r}; "
        "expected 'inprocess' or 'brokered'."
    )


def main() -> None:
    """Run the calendar agent as a long-lived service.

    Selects the transport, starts the agent, then blocks until a
    ``SIGTERM``/``SIGINT`` is received, at which point the agent is
    stopped and the process exits cleanly.
    """
    transport = _build_transport()
    agent = CalendarAgent(transport=transport)

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

"""Long-lived service entrypoint for :class:`CalendarAgent`.

Selects the transport based on the ``CALENDAR_AGENT_TRANSPORT``
environment variable, instantiates the agent, starts it, and blocks
until ``SIGTERM``/``SIGINT`` requests a graceful shutdown.

Transport modes:

- ``inprocess`` (or unset) — the agent constructs its own in-process
  :class:`robotsix_agent_comm.transport.Registry`.
- ``brokered`` — connect to a secured broker over HTTPS using the
  ``BROKER_*`` environment variables and run the agent in mailbox/pull
  mode (NAT-safe, outbound-only) registered as ``robotsix-calendar``.
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

#: Agent id the calendar agent registers under on the broker. auto-mail
#: addresses calendar requests to this exact id.
_DEFAULT_AGENT_ID = "robotsix-calendar"


def _build_brokered_transport() -> tuple[Any, Any]:
    """Build the ``(registry, transport)`` pair from the ``BROKER_*`` env vars.

    Uses the shipping :func:`robotsix_agent_comm.transport.create_transport_pair`
    factory (resolved dynamically so this module imports cleanly even against an
    agent-comm revision that predates it). The deployed broker is fronted by a
    publicly-trusted TLS endpoint, so by default no CA file or client cert is
    needed — system trust + a bearer token. ``BROKER_TLS_CA`` may point at a
    custom CA PEM for a privately-signed broker certificate.

    Raises:
        ValueError: If a required brokered env var is missing.
    """
    import importlib

    transport_mod = importlib.import_module("robotsix_agent_comm.transport")
    create_transport_pair = transport_mod.create_transport_pair

    host = os.environ.get("BROKER_HOST", "")
    if not host:
        raise ValueError(
            "BROKER_HOST is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    token = os.environ.get("BROKER_AGENT_TOKEN", "")
    if not token:
        raise ValueError(
            "BROKER_AGENT_TOKEN is required when CALENDAR_AGENT_TRANSPORT=brokered."
        )

    port = int(os.environ.get("BROKER_PORT", "443"))
    scheme = os.environ.get("BROKER_SCHEME", "https")

    # Custom CA only needed for a privately-signed broker cert; otherwise rely
    # on the system trust store (matching the working board-agent client).
    tls_ca = os.environ.get("BROKER_TLS_CA", "")
    ssl_context = None
    if tls_ca:
        import ssl

        ssl_context = ssl.create_default_context(cafile=tls_ca)

    logger.info(
        "Connecting to broker at %s://%s:%d (custom CA=%s)",
        scheme,
        host,
        port,
        "yes" if tls_ca else "no (system trust)",
    )

    registry, transport = create_transport_pair(
        "brokered",
        broker_host=host,
        broker_port=port,
        broker_scheme=scheme,
        broker_ssl_context=ssl_context,
        broker_token=token,
    )
    return registry, transport


def _build_transport() -> tuple[Any, Any] | None:
    """Return the transport selected by ``CALENDAR_AGENT_TRANSPORT``.

    Returns ``None`` for the in-process path (so :class:`CalendarAgent`
    builds its own :class:`Registry`), or a ``(registry, transport)`` pair
    for the brokered path.

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
    pair = _build_transport()
    if pair is None:
        agent = CalendarAgent()
    else:
        registry, transport = pair
        agent_id = os.environ.get("CALENDAR_AGENT_ID", _DEFAULT_AGENT_ID)
        agent = CalendarAgent(
            agent_id, registry=registry, transport=transport, pull=True
        )

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

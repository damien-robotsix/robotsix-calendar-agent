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

When the component-agent responder is enabled
(``COMPONENT_AGENT_ENABLED=true``), the brokered branch composes a
:class:`~robotsix_calendar_agent.component_agent.responder.ComponentAgentResponder`
onto the same ``BrokeredAgent`` connection, so ``monitor`` /
``config-get`` / ``config-set`` kinds are served under the existing
``robotsix-calendar`` agent identity — no second broker connection.
"""

from __future__ import annotations

import importlib.util
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
        _MISSING_TOKEN_MSG = (
            "BROKER_AGENT_TOKEN is required when CALENDAR_AGENT_TRANSPORT=brokered."  # nosec B105 — error message, not a credential
        )
        raise ValueError(_MISSING_TOKEN_MSG)

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

    # -- optional component-agent responder --------------------------------
    component_responder = _build_component_responder(settings)

    if mode == "brokered":
        brokered = _build_brokered_agent()
        # CalendarAgent wires its request handler onto the shared client.
        CalendarAgent(
            brokered.agent_id,
            agent=brokered,
            component_responder=component_responder,
        )
        # BrokeredAgent.serve_forever() installs signal handlers, starts the
        # mailbox/pull loop, and blocks until SIGTERM/SIGINT.
        brokered.serve_forever()
        return

    if mode in ("", "inprocess"):
        logger.info("Using in-process transport")
        _serve_blocking(CalendarAgent(component_responder=component_responder))
        return

    _invalid_msg = (
        f"Invalid CALENDAR_AGENT_TRANSPORT={mode!r}; "
        "expected 'inprocess' or 'brokered'."
    )
    raise ValueError(_invalid_msg)


def _build_component_responder(settings: Any) -> Any | None:
    """Build a :class:`ComponentAgentResponder` when enabled and available.

    Gated by BOTH:

    1. ``importlib.util.find_spec("robotsix_agent_comm")`` — the SDK is
       installed (defense-in-depth; it is a core dependency).
    2. ``ComponentAgentSettings.COMPONENT_AGENT_ENABLED`` is true.

    Returns ``None`` when the responder is disabled or the SDK is absent.
    The responder is passed to :class:`CalendarAgent` which composes it
    into its request-handling dispatch.

    .. note::

        The ``find_spec`` gate is **defense-in-depth parity** with the
        robotsix-chat template.  In this repo ``robotsix-agent-comm`` is
        a core dependency (not optional), so the spec will normally be
        found.  We do **not** move it to an ``[optional]`` extra because
        that would break ``brokered_entrypoint`` which requires it for
        the primary brokered transport.
    """
    try:
        sdk_available = importlib.util.find_spec("robotsix_agent_comm") is not None
    except (ValueError, ImportError):
        sdk_available = False
    if not sdk_available:
        logger.info("Component-agent responder disabled: robotsix_agent_comm not found")
        return None
    from .component_agent.settings import ComponentAgentSettings

    comp = ComponentAgentSettings()
    if not comp.COMPONENT_AGENT_ENABLED:
        logger.info("Component-agent responder disabled (not enabled)")
        return None

    # Token-required-when-enabled invariant is enforced by
    # ComponentAgentSettings at construction time; if we reach here the
    # token is non-empty.  We still verify for clarity.
    token = comp.COMPONENT_AGENT_TOKEN.get_secret_value()
    if not token:
        logger.warning("Component-agent responder disabled: token is empty")
        return None

    from .component_agent.responder import ComponentAgentResponder

    logger.info(
        "Component-agent responder enabled (agent_id=%r)",
        comp.COMPONENT_AGENT_ID,
    )
    # The responder will be wired into CalendarAgent which passes it the
    # running agent reference at construction time.  We create the
    # responder with a placeholder agent=None and the settings object;
    # CalendarAgent will set the agent reference later.  Actually, the
    # CalendarAgent passes itself as `agent` when constructing the
    # responder — but here we pre-build it.  We'll restructure:
    # CalendarAgent receives the responder and the responder already has
    # the settings.  The responder's agent reference is set inside
    # CalendarAgent.__init__ or we pass a factory.
    #
    # Simplest: build the responder now with settings, and CalendarAgent
    # will update its _agent reference.
    return ComponentAgentResponder(None, settings)

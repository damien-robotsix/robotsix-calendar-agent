"""ComponentAgentResponder — broker-agnostic dispatch for management kinds.

Handles ``monitor``, ``config-get``, and ``config-set`` request kinds
on behalf of the running :class:`CalendarAgent`.  Built to compose
inside the existing brokered lifecycle without a second broker
connection.

.. note::

    This module mirrors the *responder template* from ``robotsix-chat``
    conceptually, but diverges in one important way: instead of starting
    a standalone responder connection (``asyncio.to_thread(serve_forever)``),
    we compose dispatch on the **same** ``BrokeredAgent`` connection the
    calendar agent already owns.  This avoids a duplicate ``agent-id``
    conflict on the broker.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..agent import CalendarAgent

logger = logging.getLogger(__name__)

#: The management kinds this responder handles.  Exposed as a constant
#: so registry discovery (and the ``monitor`` payload) can advertise them.
COMPONENT_KINDS: tuple[str, ...] = ("monitor", "config-get", "config-set")


class ComponentAgentResponder:
    """Dispatch management-kind requests to live telemetry / config.

    Holds references to the running agent (for telemetry) and the live
    settings object (for config read/write).  It is transport-agnostic:
    it receives a ``request`` object and returns a protocol message;
    the caller owns the broker connection.

    Args:
        agent: The running :class:`CalendarAgent` instance.
        settings: The live :class:`~robotsix_calendar_agent.settings.Settings`
            instance the agent was built with.
    """

    def __init__(self, agent: CalendarAgent | None, settings: Any) -> None:
        self._agent = agent
        self._settings = settings

    def set_agent(self, agent: CalendarAgent) -> None:
        """Bind the responder to a live :class:`CalendarAgent` instance.

        Called by :class:`CalendarAgent.__init__` after the responder
        is constructed, resolving the chicken-and-egg between the
        responder (needs agent for telemetry) and the agent (needs
        responder for dispatch).
        """
        self._agent = agent

    # ------------------------------------------------------------------
    # public dispatch entry point
    # ------------------------------------------------------------------

    def on_request(self, request: Any) -> Any:
        """Handle an incoming management-kind request.

        Dispatches on ``request.body.get("kind")``.  Unknown or missing
        kinds receive a broker ``Error``.
        """
        from robotsix_agent_comm.protocol import Error

        body: dict[str, Any] = request.body or {}
        kind: str | None = body.get("kind")

        if not kind:
            return Error.to(
                request,
                code="unknown_kind",
                message="Request body must contain a 'kind' key (monitor, "
                "config-get, or config-set).",
            )

        handler = _KIND_DISPATCH.get(kind)
        if handler is None:
            return Error.to(
                request,
                code="unknown_kind",
                message=f"Unknown management kind: {kind!r}. "
                f"Supported kinds: {', '.join(COMPONENT_KINDS)}",
            )

        return handler(self, request)

    # ------------------------------------------------------------------
    # kind handlers
    # ------------------------------------------------------------------

    def _handle_monitor(self, request: Any) -> Any:
        """Return genuine live telemetry from the running agent."""
        from robotsix_agent_comm.protocol import Response

        if self._agent is None:
            from robotsix_agent_comm.protocol import Error

            return Error.to(
                request,
                code="internal_error",
                message="ComponentAgentResponder not bound to an agent",
            )

        snapshot = self._agent.monitor_snapshot()
        # Advertise supported capabilities
        snapshot["capabilities"] = list(COMPONENT_KINDS)
        return Response.to(request, body=snapshot)

    def _handle_config_get(self, request: Any) -> Any:
        """Return the redacted config snapshot + descriptors."""
        from robotsix_agent_comm.protocol import Response

        from .config_contract import describe_config, get_config_snapshot
        from .settings import ComponentAgentSettings

        comp_settings = ComponentAgentSettings()
        snapshot = get_config_snapshot(self._settings, comp_settings)
        descriptors = describe_config(self._settings, comp_settings)
        return Response.to(
            request,
            body={"snapshot": snapshot, "descriptors": descriptors},
        )

    def _handle_config_set(self, request: Any) -> Any:
        """Validate, apply, and return audit map for a config update."""
        from robotsix_agent_comm.protocol import Error
        from robotsix_agent_comm.protocol import Response as BrokerResponse

        from .config_contract import (
            ConfigContractError,
            apply_config_update,
        )

        body: dict[str, Any] = request.body or {}
        updates: dict[str, Any] = body.get("updates", {})
        if not isinstance(updates, dict):
            return Error.to(
                request,
                code="invalid_request",
                message="config-set requires an 'updates' dict in the request body",
            )

        if not updates:
            return Error.to(
                request,
                code="invalid_request",
                message="config-set 'updates' dict must not be empty",
            )

        try:
            audit = apply_config_update(self._settings, updates)
        except ConfigContractError as exc:
            return Error.to(
                request,
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )

        # Additionally update CalendarAgent's live CalDavClient default
        # calendar if that key was changed.
        if self._agent is not None:
            for key, (_old, _new) in audit.items():
                if key == "radicale_default_calendar":
                    new_val = updates[key]
                    self._agent._caldav._default_calendar = new_val
                    logger.info("Updated CalDavClient._default_calendar to %r", new_val)

        return BrokerResponse.to(request, body={"audit": audit})


# ------------------------------------------------------------------
# dispatch table
# ------------------------------------------------------------------

_KIND_DISPATCH: dict[str, Any] = {
    "monitor": ComponentAgentResponder._handle_monitor,
    "config-get": ComponentAgentResponder._handle_config_get,
    "config-set": ComponentAgentResponder._handle_config_set,
}

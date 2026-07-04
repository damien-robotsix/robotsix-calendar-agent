# Component-Agent Management

!!! note "Removed"
    The component-agent management responder (``monitor``, ``config-get``,
    ``config-set`` kinds) has been removed as part of the
    ``robotsix-agent-comm`` broker decommissioning.  The management
    plane will be reimplemented via the central-deploy system in a
    future release.

    The live telemetry snapshot is still available directly on the
    agent instance:

    ```python
    from robotsix_calendar_agent import CalendarAgent

    agent = CalendarAgent()
    snap = agent.monitor_snapshot()
    print(f"Uptime: {snap['uptime_seconds']:.0f}s")
    print(f"CalDAV health: {snap['caldav_health']}")
    ```

## Next steps

- [Configuration](../../configuration.md) — complete environment variable
  reference.

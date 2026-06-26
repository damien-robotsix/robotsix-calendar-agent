#!/usr/bin/env python3
"""Docker HEALTHCHECK probe — validates CalDAV reachability.

Loads credentials from the same environment variables the agent uses,
creates a :class:`~robotsix_calendar_agent.caldav_client.CalDavClient`,
and calls :meth:`~robotsix_calendar_agent.caldav_client.CalDavClient.health`.

Exit codes:
    0 — CalDAV server is reachable and responsive.
    1 — health probe failed after retries.
"""

from __future__ import annotations

import sys
import time

from robotsix_calendar_agent.caldav_client import CalDavClient
from robotsix_calendar_agent.settings import Settings

RETRIES = 3
RETRY_DELAY_SECONDS = 2


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    url = settings.RADICALE_URL
    username = settings.RADICALE_USERNAME
    password = settings.RADICALE_PASSWORD.get_secret_value()
    default_calendar = settings.RADICALE_DEFAULT_CALENDAR

    if not url or not username or not password:
        print(
            "healthcheck: RADICALE_URL, RADICALE_USERNAME, and "
            "RADICALE_PASSWORD must be set",
            file=sys.stderr,
        )
        sys.exit(1)

    last_error: str | None = None

    for attempt in range(1, RETRIES + 1):
        try:
            client = CalDavClient(
                url=url,
                username=username,
                password=password,
                default_calendar=default_calendar,
            )
            result = client.health()
        except Exception as exc:
            last_error = str(exc)
        else:
            if result.get("connected"):
                print(f"healthcheck OK: {result}")
                sys.exit(0)
            last_error = result.get("error", "unknown error")

        if attempt < RETRIES:
            print(
                f"healthcheck attempt {attempt}/{RETRIES} failed: {last_error}",
                file=sys.stderr,
            )
            time.sleep(RETRY_DELAY_SECONDS)

    print(
        f"healthcheck FAILED after {RETRIES} attempts: {last_error}",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

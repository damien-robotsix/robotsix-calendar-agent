"""In-process Radicale test server fixture for integration tests.

Provides a session-scoped ``caldav_client`` fixture that points a real
``caldav.DAVClient`` at an ephemeral Radicale WSGI server backed by a
temporary filesystem storage directory.  No external process is spawned
— everything runs in-process via ``wsgiref.simple_server``.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from wsgiref.simple_server import make_server

import pytest


def radicale_app(storage_dir: Path) -> Any:
    """Create a Radicale WSGI application with permissive auth.

    Args:
        storage_dir: Directory for ``multifilesystem`` storage.
            Must already exist.

    Returns:
        A Radicale WSGI application (``radicale.app.Application``).
    """
    import radicale.app
    import radicale.config

    config = radicale.config.load()
    config.update(
        {
            "storage": {"filesystem_folder": str(storage_dir)},
            "auth": {"type": "none", "delay": "0.001"},
        },
        source="test",
        privileged=True,
    )
    return radicale.app.Application(config)


@pytest.fixture(scope="session")
def caldav_client(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """Session-scoped fixture yielding a real ``caldav.DAVClient``.

    The client is connected to an in-process Radicale server with a
    temporary storage directory.  A default calendar is created so
    tests can immediately save and search events.

    The ``tests/caldav_client/test_caldav_client.py`` unit-test suite
    manages its own ``sys.modules["caldav"]`` mock via a per-test
    fixture, so this fixture can safely import and use the real
    ``caldav`` library without interference.
    """
    import caldav

    storage_dir = tmp_path_factory.mktemp("radicale_storage")
    app = radicale_app(storage_dir)

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{port}"
    client = caldav.DAVClient(url=url, username="x", password="x")

    # Ensure the principal has a default calendar so test code can
    # immediately call ``principal.calendars()`` and get a non-empty
    # list.
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        principal.make_calendar(name="default")

    yield client

    server.shutdown()
    server.server_close()
    t.join(timeout=5)

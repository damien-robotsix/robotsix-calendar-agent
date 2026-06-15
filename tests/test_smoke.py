"""Smoke test: verify the package imports and has a version string."""


def test_import_package() -> None:
    import robotsix_calendar_agent

    assert isinstance(robotsix_calendar_agent.__version__, str)

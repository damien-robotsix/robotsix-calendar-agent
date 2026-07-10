# vulture whitelist — symbols listed here are excluded from dead-code detection.
# Add false-positive names one per line (bare names, not strings).

# Set in __init__ and used via self._url
_url

# StrEnum members — used via the enum class, invisible to vulture
LIST_EVENTS
LIST_CALENDARS
CREATE_EVENT
UPDATE_EVENT
DELETE_EVENT
LIST_TASKS
LIST_CONTACTS
CREATE_CONTACT
UPDATE_CONTACT
DELETE_CONTACT

# Dataclass field with default
original_text

# Pydantic field-validator methods — invoked by the framework, not dead code
_normalize_log_level
_token_required_when_enabled
cls

# logging.Formatter subclass — format() called by logging framework internals
format

# CalDavClient health probe — public API called on-demand by monitor;
# monitor_snapshot was removed but health is kept as public API
health

# CalDavClient health probe — public API called on-demand by monitor
health

# CalendarAgent attributes/methods — used by removed broker integration;
# kept as public API / still exercised in unit tests
_settings
_intent_parser
_dispatch
_render_reply

# IntentParser.parse — public API method; the only in-tree consumer
# (add_to_calendar_handler.py) was removed, but external callers rely on it.
parse

# CalendarError.code — public attribute set in __init__; the only in-tree
# consumer (add_to_calendar_handler.py's exc.code check) was removed.
code

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
_normalize_transport
_validate_port
_empty_str_to_none
_token_required_when_enabled
cls

# Planned helper — kept for future use in config contract
_read_value

# vulture whitelist — symbols listed here are excluded from dead-code detection.
# Add false-positive names one per line (bare names, not strings).

# Public API alias for stop()
close

# Set in __init__ and used via self._url
_url

# StrEnum members — used via the enum class, invisible to vulture
LIST_EVENTS
CREATE_EVENT
UPDATE_EVENT
DELETE_EVENT
LIST_CONTACTS
CREATE_CONTACT
UPDATE_CONTACT
DELETE_CONTACT

# Dataclass field with default
original_text

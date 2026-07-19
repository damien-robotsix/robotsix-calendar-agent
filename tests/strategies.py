"""Shared Hypothesis strategies for property-based tests."""

from __future__ import annotations

import datetime

from hypothesis import strategies as st

# Printable text — includes spaces, punctuation, emoji, but excludes
# control characters and newlines (significant in iCal folding).
text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cc", "Cs"),
        blacklist_characters="\n\r",
    ),
    max_size=80,
)

# Non-empty variant for required fields.
text_required = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cc", "Cs"),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=80,
)

# ISO-8601 dates (date-only) in range 2020–2030.
dates = st.dates(
    min_value=datetime.date(2020, 1, 1),
    max_value=datetime.date(2030, 12, 31),
).map(datetime.date.isoformat)

# Valid CalDAV/CardDAV UIDs.
uids = st.uuids().map(str)

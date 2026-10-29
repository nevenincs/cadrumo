"""The workspace page, as a navigation register id, that shows what each registered operation reads or changes."""

from __future__ import annotations

from typing import Final

_PAGE_BY_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("modelo.", "declarations"),
    ("export.", "declarations"),
    ("ledger.", "ledger"),
    ("user-profile.", "profile"),
    ("auth.", "profile/aeat-access"),
)
"""Ordered most specific first; the first matching prefix names the register view."""


def operation_destination(definition_id: str) -> str | None:
    """Name the register view a person opens to see this operation's records, or ``None`` when none shows them."""
    return next((page for prefix, page in _PAGE_BY_PREFIX if definition_id.startswith(prefix)), None)

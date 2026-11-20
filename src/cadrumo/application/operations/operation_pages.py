"""The workspace page, as a navigation register id, that shows what each registered operation reads or changes."""

from __future__ import annotations

from typing import Final

_PAGE_BY_PREFIX: Final[tuple[tuple[str, str | None], ...]] = (
    # Received-invoice withholding is captured for a workbench no surface implements yet, and the
    # entry shadows the declarations page below.
    ("modelo.aggregate.capture_received_invoice_retencion", None),
    # Filed evidence is compared on the AEAT page, beside what was read from the AEAT.
    ("modelo.reconcile.", "aeat-sync"),
    ("modelo.", "declarations"),
    ("export.", "declarations"),
    ("ledger.", "ledger"),
    ("live.", "aeat-sync"),
    ("user-profile.", "profile"),
    ("auth.", "profile/aeat-access"),
    # The calendar read is drawn on its own page; the overview's other reads are what Home shows.
    ("overview.calendar", "calendar"),
    ("overview.", "home"),
)
"""Ordered most specific first; the first matching prefix names the register view, or ``None`` for no page.

A page names only a register element some surface implements.
"""


def operation_destination(definition_id: str) -> str | None:
    """Name the register view a person opens to see this operation's records, or ``None`` when none shows them."""
    return next((page for prefix, page in _PAGE_BY_PREFIX if definition_id.startswith(prefix)), None)

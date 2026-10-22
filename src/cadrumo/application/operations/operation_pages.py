"""The workspace page that shows what each registered operation reads or changes."""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.presentation import PresentationDestination

_PAGE_BY_PREFIX: Final[tuple[tuple[str, PresentationDestination], ...]] = (
    # Received-invoice withholding is captured for the withholding workbench, not a declaration.
    ("modelo.aggregate.capture_received_invoice_retencion", "withholding"),
    # Filed evidence is compared on the AEAT page, beside what was read from the AEAT.
    ("modelo.reconcile.", "aeat_sync"),
    ("modelo.", "declarations"),
    ("export.", "declarations"),
    ("ledger.", "ledger"),
    ("live.", "aeat_sync"),
    ("user-profile.", "profile"),
    ("auth.", "aeat_auth"),
    ("overview.", "home"),
    ("dependencies.", "setup"),
    ("local-reader.", "setup"),
)
"""Ordered most specific first; the first matching prefix names the page."""


def operation_destination(definition_id: str) -> PresentationDestination | None:
    """Name the page a person opens to see this operation's records, or ``None`` when no page shows them."""
    return next((page for prefix, page in _PAGE_BY_PREFIX if definition_id.startswith(prefix)), None)

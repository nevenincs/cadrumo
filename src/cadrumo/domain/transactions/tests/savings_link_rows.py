"""Build ledger rows that carry a savings link, for the tests that exercise it."""

from __future__ import annotations

from ..models import Transaction
from .rental_link_rows import rental_row


def savings_row(*, provider_id: str = "savings-link-row", **fields: object) -> Transaction:
    """Return one validated ledger row with ``fields`` layered over a plain outgoing row."""
    return rental_row(provider_id=provider_id, **fields)

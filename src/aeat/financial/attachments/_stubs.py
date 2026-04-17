"""Typing-only Protocol placeholders for sibling packages not yet on main."""

from __future__ import annotations

from typing import Protocol


class SupportsTransactionId(Protocol):
    """Minimum typing surface for a transaction reference."""

    transaction_id: str


class SupportsInvoiceId(Protocol):
    """Minimum typing surface for a future invoice reference (#75)."""

    invoice_id: str

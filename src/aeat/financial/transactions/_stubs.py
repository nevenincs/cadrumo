"""Typing-only Protocol placeholders for sibling packages not yet on main."""

from __future__ import annotations

from typing import Protocol


class SupportsInvoiceId(Protocol):
    """Minimum typing surface for a future invoice reference."""

    invoice_id: str


class SupportsCategoryId(Protocol):
    """Minimum typing surface for a future tax-category reference."""

    category_id: str

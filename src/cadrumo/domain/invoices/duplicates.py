"""Which stored invoice a document may already be.

A likely duplicate is a question for the person, not a refusal: the invoice id folds
exact identity, and this asks what a differently spelled number or a second copy of
one purchase would still share.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal

from ..iva.schema import InvoiceKind
from .models import Invoice

_NOT_COMPARED: Final = re.compile(r"[^A-Z0-9]+")

type DuplicateBasis = Literal["number", "party_day_total"]


@dataclass(frozen=True)
class LikelyDuplicate:
    """The stored invoice found, and what it shares with the document."""

    invoice_id: str
    basis: DuplicateBasis


def _folded(text: str | None) -> str:
    return _NOT_COMPARED.sub("", (text or "").upper())


def likely_duplicate_invoice(
    invoices: Iterable[Invoice],
    *,
    kind: InvoiceKind,
    invoice_number: str | None,
    counterparty_tax_id: str | None,
    invoice_date: date | None,
    grand_total: Decimal | None,
) -> LikelyDuplicate | None:
    """Return the first of ``invoices`` this document may already be.

    The same kind and number with no disagreeing tax id comes first. Only where none has
    it, the same kind, tax id, date and total. Numbers and tax ids compare without case,
    spaces or punctuation. A fact the document does not state matches nothing.
    """
    same_kind = tuple(invoice for invoice in invoices if invoice.kind == kind)
    tax_id = _folded(counterparty_tax_id)
    return _same_number(same_kind, _folded(invoice_number), tax_id) or _same_party_day_total(
        same_kind, tax_id, invoice_date, grand_total
    )


def _same_number(invoices: tuple[Invoice, ...], number: str, tax_id: str) -> LikelyDuplicate | None:
    if not number:
        return None
    for invoice in invoices:
        theirs = _folded(invoice.counterparty_tax_id)
        if _folded(invoice.invoice_number) == number and (not tax_id or not theirs or tax_id == theirs):
            return LikelyDuplicate(invoice_id=invoice.invoice_id, basis="number")
    return None


def _same_party_day_total(
    invoices: tuple[Invoice, ...], tax_id: str, invoice_date: date | None, grand_total: Decimal | None
) -> LikelyDuplicate | None:
    if not tax_id or invoice_date is None or grand_total is None:
        return None
    for invoice in invoices:
        if (
            _folded(invoice.counterparty_tax_id) == tax_id
            and invoice.issued_at == invoice_date
            and invoice.grand_total == grand_total
        ):
            return LikelyDuplicate(invoice_id=invoice.invoice_id, basis="party_day_total")
    return None


__all__ = ["DuplicateBasis", "LikelyDuplicate", "likely_duplicate_invoice"]

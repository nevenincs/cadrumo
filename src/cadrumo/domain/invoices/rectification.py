"""Which facts a factura rectificativa must state before its modification can be declared.

A rectificativa's amounts are magnitudes like every other invoice's, so the
document alone does not say what modification it makes: RD 1619/2012 art. 15.5
fixes two readings of the same figures, and LIVA art. 89.Cinco and art. 114.Dos
place the modification in different periods depending on the side and the
ground. The facts named by
:class:`~cadrumo.domain.invoices.enums.RectificationFact` are the ones the
record must hold before any of that can be read.

This module says which of them a side needs and which are absent. It derives
nothing and defaults nothing: a record missing one is a record the declaration
refuses, naming the gap, not one this module fills in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..iva.schema import InvoiceKind
from .enums import RectificationFact, invoice_class_rectificativa
from .validation_pass import answer_once

if TYPE_CHECKING:
    from .models import Invoice

__all__ = [
    "missing_rectification_facts",
    "required_rectification_facts",
]


#: The facts both sides need: the method says what the stated amounts mean
#: (RD 1619/2012 art. 15.5), the cause is the ground that places the
#: modification in a period (LIVA art. 89.Cinco and art. 114.Dos), and the
#: direction carries its economic sense while the amounts stay magnitudes.
_BOTH_SIDES: tuple[RectificationFact, ...] = (
    RectificationFact.RECTIFICATION_METHOD,
    RectificationFact.RECTIFICATION_CAUSE,
    RectificationFact.RECTIFICATION_DIRECTION,
)


def required_rectification_facts(kind: InvoiceKind) -> tuple[RectificationFact, ...]:
    """The facts a rectificativa on ``kind``'s side must state.

    The received side adds the reception date, which LIVA art. 114.Dos makes
    the period for an increase and for a minoración on most grounds. The issued
    side has no such date: the issuer's period comes from the cause and the
    art. 89.Cinco election, so asking for one there would record a fact the
    document does not state and the record never observed.
    """
    if kind is InvoiceKind.RECEIVED:
        return (*_BOTH_SIDES, RectificationFact.DOCUMENT_RECEIVED_ON)
    return _BOTH_SIDES


def missing_rectification_facts(invoice: Invoice) -> tuple[RectificationFact, ...]:
    """The facts ``invoice``'s side needs and the record does not hold, in declaration order.

    Answers empty for any other invoice class, because no other class states
    these facts at all; the class is read through the dated registry on the
    invoice's own issue date, as every other rule on this record reads it.
    """
    if invoice.invoice_class != answer_once(invoice_class_rectificativa, effective_date=invoice.issued_at):
        return ()
    return tuple(fact for fact in required_rectification_facts(invoice.kind) if getattr(invoice, fact.value) is None)

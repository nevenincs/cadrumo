"""The signed per-rate modification a factura rectificativa makes.

RD 1619/2012 art. 15.5 permits two readings of the figures a rectificativa
prints, and only two: the document states "directamente el importe de la
rectificación, con independencia de su signo", or it states the figures "tal y
como queden tras la rectificación efectuada". So the same printed amounts mean
two different modifications, and the recorded method is what says which.

Under the difference method the document's own lines ARE the modification, and
the recorded direction supplies its economic sense, because every stored amount
is a non-negative magnitude. Under the substitution method the lines are the
post-rectification figures, so the modification is the substitute minus the
original, per rate and per category, and its sign is the arithmetic's own. The
original must be exactly one catalogue invoice, or there is no difference to
take and this module refuses, naming which way it failed.

Nothing here declares anything. It derives one typed, signed modification from
a record and refuses when the record cannot support one; which period that
modification belongs to is LIVA art. 89.Cinco and art. 114.Dos, and is not
decided here. The totals on the record stay non-negative: the sign exists only
in what this module returns.

One cross-check art. 15.5 states is not available. A substitution invoice also
states "el importe de dicha rectificación", which would compare against the
derived difference. :class:`~cadrumo.domain.invoices.models.Invoice` holds no
such field, so no comparison can run and none is faked here; the field is not
added either, because a fact the person must supply belongs with the other
rectification facts and their write admission.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...core.parsing.codes import IsoCurrencyCode
from ..calculations.registry.invoice_legal_classification import (
    InvoiceLegalClassificationCatalogue,
    resolve_invoice_legal_classification_catalogue,
)
from ..iva.schema import IvaCategory
from .enums import IvaRate, RectificationDirection, RectificationMethod
from .rectification import missing_rectification_facts
from .validation_pass import answer_once

if TYPE_CHECKING:
    from ..calculations.registry.governed_fact_scope import GovernedFactSource
    from .models import Invoice

__all__ = [
    "DerivedRectificationModification",
    "RectificationModification",
    "RectificationModificationRefusal",
    "RectificationModificationRow",
    "derive_rectification_modification",
]


_ZERO = Decimal("0")


class RectificationModificationRefusal(StrEnum):
    """Why a rectificativa's modification cannot be derived from the record.

    Each member names one thing the person can act on. None of them is a
    statement about the period the modification belongs to, which is a separate
    question with its own answer.
    """

    #: The invoice is not a factura rectificativa at all, by the dated
    #: invoice-class token. No other invoice makes a modification.
    NOT_A_RECTIFICATIVA = "rectification_not_a_rectificativa"
    #: The record does not hold every rectification fact its side needs, so the
    #: method that says what the figures mean may itself be absent.
    FACTS_NOT_STATED = "rectification_facts_not_stated"
    #: A substitution invoice that names no original invoice number. Without it
    #: there is nothing to subtract from.
    ORIGINAL_NOT_STATED = "rectification_original_not_stated"
    #: A substitution invoice whose named original is in no catalogue invoice of
    #: the same kind and counterparty.
    ORIGINAL_NOT_FOUND = "rectification_original_not_found"
    #: A substitution invoice whose named original matches more than one
    #: catalogue invoice, so which figures it replaces is unresolved.
    ORIGINAL_AMBIGUOUS = "rectification_original_ambiguous"
    #: A substitution invoice stated in one currency and its original in
    #: another. Subtracting them would net two different units of account.
    ORIGINAL_CURRENCY_DIFFERS = "rectification_original_currency_differs"
    #: A substitution invoice whose derived difference runs the opposite way to
    #: the recorded direction. Both describe the same document, so one of them
    #: is wrong and neither may be preferred silently.
    DIRECTION_CONTRADICTS_DIFFERENCE = "rectification_direction_contradicts_difference"


class RectificationModificationRow(BaseModel):
    """The signed modification one IVA rate and category carries."""

    model_config = STRICT_FROZEN_CONFIG

    iva_rate: IvaRate
    #: The IVA treatment of the operation the row modifies, which a record may
    #: leave unstated; it is never derived from the rate.
    iva_category: IvaCategory | None
    base: Decimal
    cuota: Decimal


class RectificationModification(BaseModel):
    """One rectificativa's signed modification of bases and cuotas.

    The rows carry the sign; a negative base and cuota are a minoración, as the
    Modelo 303 instructions require of casillas 40 and 41 and permit of 14 and
    15. The amounts are in :attr:`currency`, which the record states; nothing
    here converts them.
    """

    model_config = STRICT_FROZEN_CONFIG

    method: RectificationMethod
    direction: RectificationDirection
    currency: IsoCurrencyCode
    rows: tuple[RectificationModificationRow, ...]
    #: The signed recargo de equivalencia the modification carries, ``None``
    #: when neither the document nor the original it replaces states one.
    recargo: Decimal | None
    #: The original invoice the substitution replaces, ``None`` under the
    #: difference method, which replaces nothing.
    original_invoice_id: str | None

    @property
    def base(self) -> Decimal:
        """The signed total modification of taxable bases."""
        return round_to_cents(sum((row.base for row in self.rows), _ZERO))

    @property
    def cuota(self) -> Decimal:
        """The signed total modification of cuotas."""
        return round_to_cents(sum((row.cuota for row in self.rows), _ZERO))


@dataclass(frozen=True, slots=True)
class DerivedRectificationModification:
    """Either one rectificativa's signed modification or the refusal that stands in its way.

    Exactly one of the two is set. ``original_candidates`` is how many catalogue
    invoices the named original resolved to, so a refusal can say whether none
    or several were found without the caller resolving them again.
    """

    modification: RectificationModification | None = None
    refusal: RectificationModificationRefusal | None = None
    original_candidates: int = 0


def derive_rectification_modification(
    invoice: Invoice,
    *,
    originals: Sequence[Invoice] = (),
    authority: GovernedFactSource | None = None,
) -> DerivedRectificationModification:
    """Derive the signed per-rate, per-category modification ``invoice`` makes.

    ``originals`` are the catalogue invoices the document's
    ``rectifies_invoice_number`` resolved to, which only the substitution
    method reads: the one resolver that answers that question runs over the
    profile's catalogue, and this module takes its answer rather than asking it
    a second way. Exactly one candidate is required there; none or several is a
    refusal that names which.
    """
    catalogue = answer_once(
        resolve_invoice_legal_classification_catalogue,
        effective_date=invoice.issued_at,
        authority=authority,
    )
    if invoice.invoice_class != catalogue.rectificativa_token:
        return DerivedRectificationModification(refusal=RectificationModificationRefusal.NOT_A_RECTIFICATIVA)
    if missing_rectification_facts(invoice):
        return DerivedRectificationModification(refusal=RectificationModificationRefusal.FACTS_NOT_STATED)
    method = invoice.rectification_method
    direction = invoice.rectification_direction
    if method is None or direction is None:
        # The gate above names both facts for every side, so this answers the
        # same refusal rather than a different one: it keeps the promise
        # checkable instead of assuming it.
        return DerivedRectificationModification(refusal=RectificationModificationRefusal.FACTS_NOT_STATED)
    if method == catalogue.diferencia_token:
        return _difference_modification(invoice, method=method, direction=direction, catalogue=catalogue)
    return _substitution_modification(
        invoice,
        method=method,
        direction=direction,
        originals=originals,
        catalogue=catalogue,
    )


def _sign(direction: RectificationDirection, *, minoracion: RectificationDirection) -> Decimal:
    """The sign the recorded direction gives a magnitude."""
    return Decimal("-1") if direction == minoracion else Decimal("1")


def _difference_modification(
    invoice: Invoice,
    *,
    method: RectificationMethod,
    direction: RectificationDirection,
    catalogue: InvoiceLegalClassificationCatalogue,
) -> DerivedRectificationModification:
    """The document's own lines, signed by the recorded direction (art. 15.5, first reading)."""
    sign = _sign(direction, minoracion=catalogue.minoracion_token)
    rows = tuple(
        RectificationModificationRow(
            iva_rate=rate,
            iva_category=category,
            base=round_to_cents(base * sign),
            cuota=round_to_cents(cuota * sign),
        )
        for (rate, category), (base, cuota) in _figures_by_rate(invoice).items()
    )
    recargo = None if invoice.recargo_amount is None else round_to_cents(invoice.recargo_amount * sign)
    return DerivedRectificationModification(
        modification=RectificationModification(
            method=method,
            direction=direction,
            currency=invoice.currency,
            rows=_without_empty_rows(rows),
            recargo=recargo,
            original_invoice_id=None,
        ),
    )


def _substitution_modification(
    invoice: Invoice,
    *,
    method: RectificationMethod,
    direction: RectificationDirection,
    originals: Sequence[Invoice],
    catalogue: InvoiceLegalClassificationCatalogue,
) -> DerivedRectificationModification:
    """The substitute minus the original, per rate and per category (art. 15.5, second reading)."""
    if invoice.rectifies_invoice_number is None:
        return DerivedRectificationModification(refusal=RectificationModificationRefusal.ORIGINAL_NOT_STATED)
    candidates = tuple(originals)
    if len(candidates) != 1:
        # One answer or none of the figures can be subtracted: an invoice
        # number is unique to its issuer, but a correction records the number
        # alone and not that invoice's series, so two records can answer to it.
        return DerivedRectificationModification(
            refusal=(
                RectificationModificationRefusal.ORIGINAL_NOT_FOUND
                if not candidates
                else RectificationModificationRefusal.ORIGINAL_AMBIGUOUS
            ),
            original_candidates=len(candidates),
        )
    original = next(iter(candidates))
    if original.currency != invoice.currency:
        return DerivedRectificationModification(
            refusal=RectificationModificationRefusal.ORIGINAL_CURRENCY_DIFFERS,
            original_candidates=1,
        )
    substitute_figures = _figures_by_rate(invoice)
    original_figures = _figures_by_rate(original)
    rows = tuple(
        RectificationModificationRow(
            iva_rate=rate,
            iva_category=category,
            base=round_to_cents(
                substitute_figures.get((rate, category), (_ZERO, _ZERO))[0]
                - original_figures.get((rate, category), (_ZERO, _ZERO))[0],
            ),
            cuota=round_to_cents(
                substitute_figures.get((rate, category), (_ZERO, _ZERO))[1]
                - original_figures.get((rate, category), (_ZERO, _ZERO))[1],
            ),
        )
        for rate, category in _row_keys(substitute_figures, original_figures)
    )
    recargo = _substitution_recargo(invoice, original)
    modification = RectificationModification(
        method=method,
        direction=direction,
        currency=invoice.currency,
        rows=_without_empty_rows(rows),
        recargo=recargo,
        original_invoice_id=original.invoice_id,
    )
    expected = _sign(direction, minoracion=catalogue.minoracion_token)
    net = modification.base + modification.cuota + (recargo or _ZERO)
    if net != _ZERO and (net > _ZERO) != (expected > _ZERO):
        return DerivedRectificationModification(
            refusal=RectificationModificationRefusal.DIRECTION_CONTRADICTS_DIFFERENCE,
            original_candidates=1,
        )
    return DerivedRectificationModification(modification=modification, original_candidates=1)


def _substitution_recargo(invoice: Invoice, original: Invoice) -> Decimal | None:
    """The recargo de equivalencia difference, ``None`` when neither invoice states one."""
    if invoice.recargo_amount is None and original.recargo_amount is None:
        return None
    return round_to_cents((invoice.recargo_amount or _ZERO) - (original.recargo_amount or _ZERO))


def _figures_by_rate(invoice: Invoice) -> dict[tuple[IvaRate, IvaCategory | None], tuple[Decimal, Decimal]]:
    """Sum ``invoice``'s line magnitudes by IVA rate and the category it declares."""
    figures: dict[tuple[IvaRate, IvaCategory | None], tuple[Decimal, Decimal]] = {}
    for line in invoice.lines:
        key = (line.iva_rate, invoice.iva_category)
        base, cuota = figures.get(key, (_ZERO, _ZERO))
        figures[key] = (base + line.subtotal, cuota + line.iva_amount)
    return figures


def _row_keys(
    substitute: dict[tuple[IvaRate, IvaCategory | None], tuple[Decimal, Decimal]],
    original: dict[tuple[IvaRate, IvaCategory | None], tuple[Decimal, Decimal]],
) -> tuple[tuple[IvaRate, IvaCategory | None], ...]:
    """Every rate and category either invoice states, in the substitute's order first.

    A rate the original carried and the substitute dropped still modifies: its
    whole base and cuota come off. A rate only the substitute carries is a new
    one the rectification adds.
    """
    keys = list(substitute)
    keys.extend(key for key in original if key not in substitute)
    return tuple(keys)


def _without_empty_rows(rows: Iterable[RectificationModificationRow]) -> tuple[RectificationModificationRow, ...]:
    """Drop the rates nothing moved on, which modify neither base nor cuota."""
    return tuple(row for row in rows if row.base != _ZERO or row.cuota != _ZERO)

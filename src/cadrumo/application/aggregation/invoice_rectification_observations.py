"""The observations a received rectificativa's modification declares in casillas 40 and 41.

The Modelo 303 instructions for casillas 40 and 41 ask for "el importe de la
base imponible y de las cuotas deducibles rectificadas, regularizadas en las
autoliquidaciones del ejercicio", with a minoración carried "con signo
negativo". The registry already binds those boxes: their providers are
``ledger_iva_aggregation`` sources keyed on the rectification deduction kind,
and fact 0085 declares which input side a rectification of each category
settles on. So a received rectificativa reaches them through the one
observation stream, exactly as a refunding bank movement already does.

Three facts the rectificativa alone does not supply come from the catalogue
invoice it corrects: the IVA category that routes the box (interiores,
importaciones or intracomunitarias), the rate tier the operation bore, and the
ledger row the rectification corrects. LIVA art. 114 rectifies "las deducciones
practicadas", so the deduction being rectified is the original's, and reading
the family off the rectificativa would route a corrected import into the
domestic box. The original must therefore resolve to exactly one catalogue
invoice, and the caller blocks when it does not.

The declaration date is the date the modification is DECLARED on, inside the
period the period rule decided, because an observation dated outside that
period would state one quarter while being declared in another. The rate tier
and the applied rate are resolved on the ORIGINAL operation's devengo date
instead: that is the rate the operation bore, and a modification declared years
later must not be re-priced at whatever the tier means then.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.i18n.translatable import Translatable as tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...domain.calculations.registry.iva_deduction_catalogue import resolve_iva_deduction_catalogue
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.invoices.enums import iva_rate_percentage
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance, rectification_settlement_flow
from ...domain.iva.invoice_classification import classify_invoice_line_for_iva
from ...domain.iva.schema import IvaLedgerObservationRole
from .errors import AggregationValidationError
from .invoice_devengo import resolve_invoice_devengo

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.invoices.models import Invoice
    from ...domain.invoices.rectification_modification import (
        RectificationModification,
        RectificationModificationRow,
    )

__all__ = [
    "ReceivedRectificationDeclaration",
    "RectificationDeclarationRefusal",
    "received_rectification_observations",
]

_ZERO = Decimal("0")
_RECTIFICATION_KIND_KEY = "kind.rectification"
_RECTIFICATION_AUTHORITY_ROLE = "rectification_evidence"


class RectificationDeclarationRefusal(StrEnum):
    """Why a received modification cannot be declared in casillas 40 and 41."""

    #: The rectificativa names no single catalogue invoice, so the deduction
    #: family, the rate tier and the corrected ledger row are all unresolved.
    ORIGINAL_UNRESOLVED = "rectification_original_unresolved"
    #: A modification row carries a base with no cuota, or a category the
    #: registry declares no rectification flow for. Casillas 40 and 41 declare
    #: rectified DEDUCIBLE cuotas, so neither row has a box, and dropping it
    #: would understate the rectification without saying so.
    ROW_UNDECLARABLE = "rectification_deduction_row_undeclarable"


@dataclass(frozen=True, slots=True)
class ReceivedRectificationDeclaration:
    """Either the observations one received modification declares or the refusal in their way."""

    observations: tuple[IvaLedgerObservation, ...] = ()
    refusal: RectificationDeclarationRefusal | None = None


def received_rectification_observations(
    rectificativa: Invoice,
    *,
    modification: RectificationModification,
    original: Invoice | None,
    period: Period,
    declared_on: date,
    operation: PinnedAuthorityOperation,
) -> ReceivedRectificationDeclaration:
    """Project one received modification into its casilla 40/41 observations.

    ``declared_on`` is the date inside ``period`` the modification is declared
    on, which the caller resolves from the route the period rule took.

    Core types:
    :class:`~cadrumo.core.period.Period`,
    :class:`~cadrumo.domain.calculations.registry.ledger_iva_bindings.IvaLedgerObservation`.
    """
    if original is None:
        return ReceivedRectificationDeclaration(refusal=RectificationDeclarationRefusal.ORIGINAL_UNRESOLVED)
    original_devengo = resolve_invoice_devengo(original).devengo_date
    kind = _rectification_deduction_kind(declared_on, operation=operation)
    provenance = IvaDeductionClassificationProvenance(
        authority=resolve_iva_deduction_catalogue(
            effective_date=declared_on,
            authority=operation,
        ).require_authority(_RECTIFICATION_AUTHORITY_ROLE),
        source_locator=f"invoice:{rectificativa.invoice_id}",
        evidence_digest=rectificativa.invoice_id,
    )
    observations: list[IvaLedgerObservation] = []
    for row_index, row in enumerate(modification.rows):
        projected = _row_observation(
            rectificativa,
            row=row,
            row_index=row_index,
            original=original,
            original_devengo=original_devengo,
            declared_on=declared_on,
            period=period,
            deduction_fact_kind=kind,
            provenance=provenance,
            operation=operation,
        )
        if projected is None:
            return ReceivedRectificationDeclaration(refusal=RectificationDeclarationRefusal.ROW_UNDECLARABLE)
        observations.append(projected)
    return ReceivedRectificationDeclaration(observations=tuple(observations))


def _rectification_deduction_kind(
    declared_on: date,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaDeductionFactKind:
    """The one deduction kind fact 0085 projects as its rectification family."""
    kinds = resolve_iva_deduction_catalogue(effective_date=declared_on, authority=operation).projection(
        _RECTIFICATION_KIND_KEY,
    )
    if len(kinds) != 1:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.rectification_deduction_kind_ambiguous"),
            context={"kind_count": str(len(kinds))},
        )
    return next(iter(kinds))


def _row_observation(
    rectificativa: Invoice,
    *,
    row: RectificationModificationRow,
    row_index: int,
    original: Invoice,
    original_devengo: date,
    declared_on: date,
    period: Period,
    deduction_fact_kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerObservation | None:
    """One rate's signed modification as a rectificación de deducciones, or ``None`` when no box holds it."""
    base_amount = _eur(rectificativa, row.base, row_index=row_index)
    iva_amount = _eur(rectificativa, row.cuota, row_index=row_index)
    if iva_amount == _ZERO:
        # Fact 0085 requires a rectification to carry signed non-zero base AND
        # cuota, and casillas 40 and 41 declare rectified DEDUCIBLE cuotas. A
        # row that moves only a base therefore has no box here.
        return None
    classification = classify_invoice_line_for_iva(
        iva_rate=row.iva_rate,
        invoice_kind=original.kind,
        on_date=original_devengo,
    )
    if classification.rate_kind is None:
        return None
    category = row.iva_category or original.iva_category or classification.category
    flow = rectification_settlement_flow(category=category, effective_date=declared_on)
    if flow is None:
        return None
    return IvaLedgerObservation(
        ledger_id=f"invoice:{rectificativa.invoice_id}:rectification:{row_index}",
        transaction_date=_declaration_date(declared_on, period),
        category=category,
        rate_kind=classification.rate_kind,
        flow_direction=flow,
        base_amount=base_amount,
        iva_amount=iva_amount,
        applied_rate=iva_rate_percentage(row.iva_rate, original_devengo),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=provenance,
        rectifies_ledger_id=f"invoice:{original.invoice_id}",
    )


def _declaration_date(declared_on: date, period: Period) -> date:
    """The date the observation carries, which must sit inside the period it is declared in.

    The route's own date is used where the period holds it, which is every
    route whose period IS a date's period. An elected period that the route's
    date falls outside takes that period's first day, because the date exists
    here to place the observation in the declaración-liquidación it belongs to
    and the document holds no other date inside it.
    """
    return declared_on if period.has_date_span() and period.contains(declared_on) else period.start_date


def _eur(invoice: Invoice, amount: Decimal, *, row_index: int) -> Decimal:
    """One signed modification amount in EUR, refusing an invoice that resolves no rate."""
    converted = invoice.line_amount_eur(amount)
    if converted is None:
        raise AggregationValidationError(
            tr("aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "currency": invoice.currency,
                "line_index": str(row_index),
            },
        )
    return converted

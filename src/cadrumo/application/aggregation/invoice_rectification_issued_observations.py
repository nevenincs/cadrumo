"""The observations an issued rectificativa's modification declares in casillas 14 and 15.

The Modelo 303 instructions for casillas 14 and 15 ask the issuer to state
"con el signo que corresponda la modificación de bases imponibles y cuotas de
operaciones en las que concurra cualquiera de las causas previstas en el
artículo 80 de la LIVA (Artículo 24, apartado 1 y 2 del RIVA), así como
cualquier otra modificación de bases y cuotas". So the modification is declared
on the output side as its own figure, beside the operations it corrects rather
than inside them.

That "beside" is why the observation carries its own role. An issued
modification is devengado and carries no deduction at all, so the deduction
family that routes the received side's casillas 40 and 41 says nothing here,
and the ordinary rate bindings must not absorb it: a correction of a 21 %
sale is not a 21 % sale. The bindings for 14 and 15 select
:attr:`~cadrumo.domain.iva.schema.IvaLedgerObservationRole.RECTIFICATION_MODIFICATION`
and every ordinary devengado binding keeps the settlement role, which is what
keeps the two populations apart.

The declaration date is the date inside the decided period, as on the received
side. The rate tier and the applied rate are resolved on the ORIGINAL
operation's devengo date where the record resolves one, because that is the
rate the operation bore; a modification declared later must not be re-priced at
whatever the tier means then. With no single original, the rectificativa's own
devengo stands in, which is the date the document itself was raised on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.decimal.constants import ZERO
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    iva_build_matcher,
)
from ...domain.invoices.enums import iva_rate_percentage
from ...domain.iva.flow import derive_flow_for_classification
from ...domain.iva.invoice_classification import classify_invoice_line_for_iva
from ...domain.iva.schema import InvoiceKind, IvaLedgerObservationRole
from .invoice_devengo import resolve_invoice_devengo
from .invoice_rectification_observations import (
    rectification_amount_eur,
    rectification_declaration_date,
)

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.invoices.models import Invoice
    from ...domain.invoices.rectification_modification import (
        RectificationModification,
        RectificationModificationRow,
    )

__all__ = [
    "IssuedRectificationDeclaration",
    "IssuedRectificationDeclarationRefusal",
    "issued_rectification_observations",
]


class IssuedRectificationDeclarationRefusal(StrEnum):
    """Why an issued modification cannot be declared in casillas 14 and 15."""

    #: A modification row carries a rate the dated tier table places in no
    #: slot, so no rung of the return holds the figure and dropping the row
    #: would understate the modification without saying so.
    ROW_UNDECLARABLE = "issued_rectification_row_undeclarable"
    #: The modification moves a recargo de equivalencia across several rate
    #: rows. LIVA art. 161 pairs one recargo rate with each IVA rate, and the
    #: document states one recargo figure for the whole modification, so no
    #: figure says how much of it each rung bears. Casilla 26 states the
    #: recargo of the rows that carried it; splitting it by guess would file a
    #: rung the document never stated.
    RECARGO_SPLIT_UNRESOLVED = "issued_rectification_recargo_split_unresolved"
    #: A modification row the selected Modelo 303 edition holds no binding for:
    #: an issued domestic reverse-charge supply repercutes nothing, an
    #: intra-community supply or an export carries its own boxes, and an
    #: edition whose casillas 14 and 15 are still operator input binds no
    #: modification at all. Held rather than emitted, because an observation no
    #: binding selects reaches no casilla, and a cuota-less one is excluded from
    #: the unrouted screen as well, so the period would be filed short in
    #: silence.
    NO_BINDING = "issued_rectification_no_binding"


@dataclass(frozen=True, slots=True)
class IssuedRectificationDeclaration:
    """Either the observations one issued modification declares or the refusal in their way."""

    observations: tuple[IvaLedgerObservation, ...] = ()
    refusal: IssuedRectificationDeclarationRefusal | None = None


def issued_rectification_observations(
    rectificativa: Invoice,
    *,
    modification: RectificationModification,
    original: Invoice | None,
    period: Period,
    declared_on: date,
    binding_selectors: Sequence[LedgerIvaProvider],
) -> IssuedRectificationDeclaration:
    """Project one issued modification into its casilla 14/15 observations.

    ``declared_on`` is the date inside ``period`` the modification is declared
    on, which the caller resolves from the route the period rule took.
    ``original`` is the invoice the modification corrects when the catalogue
    resolves exactly one; it supplies the devengo date the rate is read on and
    nothing else.

    ``binding_selectors`` are the selected edition's ledger IVA selectors. Each
    projected row must be one some selector admits: the registry decides which
    modifications the return holds a box for, and a row no selector admits is
    held rather than emitted into a return that would not print it.

    Core types:
    :class:`~cadrumo.core.period.Period`,
    :class:`~cadrumo.domain.calculations.registry.ledger_iva_bindings.IvaLedgerObservation`.
    """
    recargo = modification.recargo
    if recargo is not None and recargo != ZERO and len(modification.rows) != 1:
        return IssuedRectificationDeclaration(refusal=IssuedRectificationDeclarationRefusal.RECARGO_SPLIT_UNRESOLVED)
    priced_on = resolve_invoice_devengo(original if original is not None else rectificativa).devengo_date
    observations: list[IvaLedgerObservation] = []
    for row_index, row in enumerate(modification.rows):
        projected = _row_observation(
            rectificativa,
            row=row,
            row_index=row_index,
            original=original,
            priced_on=priced_on,
            declared_on=declared_on,
            period=period,
            binding_selectors=binding_selectors,
            recargo=recargo if recargo is not None else ZERO,
        )
        if isinstance(projected, IssuedRectificationDeclarationRefusal):
            return IssuedRectificationDeclaration(refusal=projected)
        observations.append(projected)
    return IssuedRectificationDeclaration(observations=tuple(observations))


def _row_observation(
    rectificativa: Invoice,
    *,
    row: RectificationModificationRow,
    row_index: int,
    original: Invoice | None,
    priced_on: date,
    declared_on: date,
    period: Period,
    binding_selectors: Sequence[LedgerIvaProvider],
    recargo: Decimal,
) -> IvaLedgerObservation | IssuedRectificationDeclarationRefusal:
    """One rate's signed modification as a repercutido figure, or the refusal in its way.

    A row that moves a base and no cuota is declarable here, unlike on the
    deducible side: casilla 14 is the base and 15 the cuota, so a modification
    of an operation that bore no cuota by law still has a box.
    """
    classification = classify_invoice_line_for_iva(
        iva_rate=row.iva_rate,
        invoice_kind=InvoiceKind.ISSUED,
        on_date=priced_on,
    )
    if classification.rate_kind is None:
        return IssuedRectificationDeclarationRefusal.ROW_UNDECLARABLE
    category = row.iva_category or rectificativa.iva_category or classification.category
    flow = derive_flow_for_classification(
        category=category,
        invoice_direction=InvoiceKind.ISSUED,
        effective_date=priced_on,
    )
    observation = IvaLedgerObservation(
        ledger_id=f"invoice:{rectificativa.invoice_id}:rectification:{row_index}",
        transaction_date=rectification_declaration_date(declared_on, period),
        category=category,
        rate_kind=classification.rate_kind,
        flow_direction=flow,
        base_amount=rectification_amount_eur(rectificativa, row.base, row_index=row_index),
        iva_amount=rectification_amount_eur(rectificativa, row.cuota, row_index=row_index),
        applied_rate=iva_rate_percentage(row.iva_rate, priced_on),
        recargo_amount=rectification_amount_eur(rectificativa, recargo, row_index=row_index),
        observation_role=IvaLedgerObservationRole.RECTIFICATION_MODIFICATION,
        rectifies_ledger_id=None if original is None else f"invoice:{original.invoice_id}",
    )
    admitted = any(iva_build_matcher(selector)(observation) for selector in binding_selectors)
    return observation if admitted else IssuedRectificationDeclarationRefusal.NO_BINDING

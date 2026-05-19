"""Reusable IVA classification record for ledger-side categorization.

Bridges the substrate's three IVA classification axes
(:class:`IvaCategory`, :class:`IvaRateKind`, :class:`IvaFlowDirection`)
into one frozen pydantic record that the ledger and downstream
filing surfaces can pass around without re-deriving the mapping.

Every IVA-bearing ledger line — invoice line, payment, ledger entry —
carries one :class:`IvaInvoiceClassification`. The record captures:

- The operation kind (domestic / intra-community / recargo / OSS / etc.).
- The applicable rate tier (general / reduced / super-reduced / zero / exempt).
- The flow direction (output / input / self-assessed reverse charge).
- The derived settlement-side classification (devengada and / or
  deducible) — pre-computed at construction time so consumers don't
  have to call :func:`settlement_sides_for_flow` repeatedly.

Why a separate record instead of fields on
:class:`aeat.domain.invoices.Invoice`?

Multiple ledger surfaces need the same triple — invoice lines,
payment-record IVA splits, expense-report ledger lines, OSS / IOSS
observations, recargo de equivalencia entries — and embedding the
fields directly on each model would scatter the substrate-bridge
logic across the codebase. The record is the canonical reusable
construct: build one from substrate primitives once, pass it down
the ledger pipeline.

The :func:`classify_invoice_line_for_iva` helper accepts an
:class:`IvaRate` plus the invoice direction (issued / received) and
returns a :class:`IvaInvoiceClassification` for the standard
domestic-IVA case (the most common autónomo operation). For
reverse-charge, intra-community, OSS / IOSS, and other non-domestic
cases, callers construct the record directly with the appropriate
:class:`IvaCategory` from the substrate's classifier output
(:func:`classify_iva`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from ._classification import InvoiceKind
from ._flow import (
    IvaFlowDirection,
    IvaSettlementSide,
    is_deducible_flow,
    is_devengada_flow,
    settlement_sides_for_flow,
)
from ._schema import IvaCategory, IvaRateKind
from ..invoices._enums import IvaRate
from ..invoices._errors import InvoiceValidationError

if TYPE_CHECKING:
    from ..calculations.registry import IvaLedgerObservation


_IVA_RATE_TO_VAT_KIND: dict[IvaRate, IvaRateKind] = {
    IvaRate.RATE_0: IvaRateKind.ZERO,
    IvaRate.RATE_4: IvaRateKind.SUPER_REDUCED,
    IvaRate.RATE_10: IvaRateKind.REDUCED,
    IvaRate.RATE_21: IvaRateKind.GENERAL,
    IvaRate.EXEMPT: IvaRateKind.EXEMPT,
}
"""Closed mapping from invoice IvaRate slot to substrate IvaRateKind.

NOT_SUBJECT is intentionally absent — operations outside the scope of
IVA do not carry a rate-tier classification. Callers handling
NOT_SUBJECT lines must construct the record directly with
``IvaCategory.OPERACION_NO_SUJETA`` and skip the rate-tier axis."""

_IVA_RATE_TO_DOMESTIC_CATEGORY: dict[IvaRate, IvaCategory] = {
    IvaRate.RATE_0: IvaCategory.DOMESTIC_ZERO,
    IvaRate.RATE_4: IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    IvaRate.RATE_10: IvaCategory.DOMESTIC_REDUCED_10,
    IvaRate.RATE_21: IvaCategory.DOMESTIC_GENERAL_21,
    IvaRate.EXEMPT: IvaCategory.DOMESTIC_EXEMPT,
}
"""Closed mapping from invoice IvaRate slot to the matching domestic
:class:`IvaCategory` for the standard autónomo case.

This mapping covers DOMESTIC operations only. Intra-community,
export, import, recargo de equivalencia, OSS / IOSS, and reverse-charge
operations have their own IvaCategory values not derivable from
IvaRate alone."""


class IvaInvoiceClassification(BaseModel):
    """Frozen pydantic record bundling the IVA classification triple
    plus the derived settlement-side classification.

    Attributes:
        category: Substrate :class:`IvaCategory` classifying the
            operation kind.
        rate_kind: Substrate :class:`IvaRateKind` rate tier; ``None``
            for operations outside the scope of IVA (NOT_SUBJECT,
            ERRONEOUS_INVOICE, UNKNOWN).
        flow_direction: Substrate :class:`IvaFlowDirection` —
            REPERCUTIDO (output), SOPORTADO (input), or
            INVERSION_SUJETO_PASIVO (self-assessed reverse charge).
        settlement_sides: Pre-computed frozen set of the
            :class:`IvaSettlementSide` cornerstones the line
            contributes to. Derived from ``flow_direction`` at
            construction time via
            :func:`settlement_sides_for_flow` so consumers don't
            recompute it.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    category: IvaCategory
    rate_kind: IvaRateKind | None
    flow_direction: IvaFlowDirection
    settlement_sides: frozenset[IvaSettlementSide]

    @model_validator(mode="after")
    def _validate_settlement_sides_match_flow(self) -> IvaInvoiceClassification:
        expected = settlement_sides_for_flow(self.flow_direction)
        if self.settlement_sides != expected:
            raise InvoiceValidationError(
                f"settlement_sides {sorted(s.value for s in self.settlement_sides)!r} "
                f"does not match flow_direction {self.flow_direction.value!r} "
                f"(expected {sorted(s.value for s in expected)!r})"
            )
        return self

    @property
    def contributes_to_devengada(self) -> bool:
        """Return ``True`` iff this line owes IVA to the Treasury."""
        return is_devengada_flow(self.flow_direction)

    @property
    def contributes_to_deducible(self) -> bool:
        """Return ``True`` iff this line reclaims IVA from the Treasury."""
        return is_deducible_flow(self.flow_direction)

    @property
    def is_reverse_charge(self) -> bool:
        """Return ``True`` iff the line is self-assessed reverse charge.

        INVERSION_SUJETO_PASIVO is the only flow that contributes to BOTH
        settlement sides on the same operation (LIVA art. 84.Uno.2).
        """
        return self.flow_direction is IvaFlowDirection.INVERSION_SUJETO_PASIVO


def classify_invoice_line_for_iva(
    *,
    iva_rate: IvaRate,
    invoice_kind: InvoiceKind,
) -> IvaInvoiceClassification:
    """Build a classification record for the standard domestic-IVA case.

    Covers the most common autónomo operation: a domestic invoice
    issued to a Spanish customer or received from a Spanish supplier
    at one of the four IVA rate slots (or EXEMPT). The record's
    flow direction is derived from ``invoice_kind``:

    - :attr:`InvoiceKind.ISSUED` → :attr:`IvaFlowDirection.REPERCUTIDO`
      (the autónomo charged output IVA on a sale).
    - :attr:`InvoiceKind.RECEIVED` →
      :attr:`IvaFlowDirection.SOPORTADO` (the autónomo bore input
      IVA on a purchase).

    For reverse-charge, intra-community, export, import, recargo de
    equivalencia, and OSS / IOSS cases, callers construct
    :class:`IvaInvoiceClassification` directly with the appropriate
    :class:`IvaCategory` from the substrate classifier
    (:func:`aeat.domain.iva.classify_iva`).

    Args:
        iva_rate: One of the closed :class:`IvaRate` slots.
            :attr:`IvaRate.NOT_SUBJECT` is rejected — see module
            docstring for the rationale.
        invoice_kind: Whether the invoice was issued (sale) or
            received (purchase).

    Returns:
        A frozen :class:`IvaInvoiceClassification` with the derived
        substrate triple and pre-computed settlement-side set.

    Raises:
        InvoiceValidationError: If ``iva_rate`` is :attr:`IvaRate.NOT_SUBJECT`,
            which has no rate-tier classification and cannot be
            handled by the standard-case helper.
    """
    if iva_rate is IvaRate.NOT_SUBJECT:
        raise InvoiceValidationError(
            "classify_invoice_line_for_iva does not handle IvaRate.NOT_SUBJECT — "
            "operations outside the scope of IVA must construct "
            "IvaInvoiceClassification directly with IvaCategory.OPERACION_NO_SUJETA"
        )

    category = _IVA_RATE_TO_DOMESTIC_CATEGORY[iva_rate]
    rate_kind = _IVA_RATE_TO_VAT_KIND[iva_rate]
    flow_direction = IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO
    return IvaInvoiceClassification(
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        settlement_sides=settlement_sides_for_flow(flow_direction),
    )


def invoice_line_to_iva_observation(
    *,
    invoice_id: str,
    issued_at: date,
    invoice_kind: InvoiceKind,
    iva_rate: IvaRate,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> IvaLedgerObservation:
    """Build an :class:`IvaLedgerObservation` from invoice line metadata.

    The runtime resolver for the substrate's ``ledger_iva_aggregation``
    binding source kind consumes
    :class:`aeat.domain.calculations.registry.IvaLedgerObservation`
    records. This helper turns invoice-line metadata into the
    observation shape the modelo registry expects, applying the
    standard-case classification (domestic IVA, REPERCUTIDO for issued
    invoices, SOPORTADO for received). Reverse-charge and
    intra-community lines must construct the observation directly.

    The function is the canonical ledger → modelo bridge for the
    standard-case IVA flows. Callers iterate the invoice's lines,
    call this helper for each, and pass the resulting tuple to
    :func:`resolve_ledger_iva_aggregation_binding_values` to populate
    the modelo's binding values.

    Args:
        invoice_id: Stable id of the source invoice (becomes
            ``ledger_id`` on the observation).
        issued_at: Invoice issue date (becomes ``transaction_date``).
        invoice_kind: Whether the invoice was issued or received.
        iva_rate: IvaRate slot for the line. NOT_SUBJECT raises
            (substrate-NULL category needs explicit construction).
        base_amount: Taxable base in EUR.
        iva_amount: VAT amount in EUR.

    Returns:
        An :class:`IvaLedgerObservation` with the full classification
        triple ready for binding-resolver consumption.
    """
    from ..calculations.registry import IvaLedgerObservation

    classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=invoice_kind)
    if classification.rate_kind is None:
        raise InvoiceValidationError("standard IVA invoice observations require a rate_kind")
    return IvaLedgerObservation(
        ledger_id=invoice_id,
        transaction_date=issued_at,
        category=classification.category,
        rate_kind=classification.rate_kind,
        flow_direction=classification.flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
    )


__all__ = [
    "IvaInvoiceClassification",
    "classify_invoice_line_for_iva",
    "invoice_line_to_iva_observation",
]

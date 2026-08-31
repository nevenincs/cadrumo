"""IVA classification record for the invoice-import bridge to the ledger.

Bridges the substrate's three IVA classification axes
(:class:`IvaCategory`, :class:`IvaRateKind`, :class:`IvaFlowDirection`)
into one frozen pydantic record. The record captures:

- The operation kind (domestic / intra-community / recargo / OSS / etc.).
- The applicable rate tier (general / reduced / super-reduced / zero / exempt).
- The flow direction (output / input / self-assessed reverse charge).
- The derived settlement-side classification (devengada and / or
  deducible) — pre-computed at construction time so consumers don't
  have to call :func:`settlement_sides_for_flow` repeatedly.

Scope: this record is the standard-case construction path for
**invoice lines** specifically — :func:`classify_invoice_line_for_iva`
derives it from an :class:`IvaRate` plus the invoice direction (issued /
received), and :func:`invoice_line_to_iva_observation` is the sole
production caller, feeding the invoice-derived Modelo 303 observations in
:mod:`cadrumo.application.aggregation._modelo_bindings`. For
reverse-charge, intra-community, OSS / IOSS, and other non-domestic
invoice cases, callers construct the record directly with the appropriate
:class:`IvaCategory` from the substrate's classifier output
(:func:`classify_iva`).

This is NOT the construction path for the general ledger-transaction
pipeline. Bank-transaction-derived IVA observations (payment splits,
expense-report lines, OSS / IOSS observations, recargo de equivalencia
entries resolved from already-classified ledger rows) are built directly
as :class:`~cadrumo.domain.calculations.registry.IvaLedgerObservation` in
:mod:`cadrumo.application.aggregation._iva_ledger`, whose category, rate,
and flow axes are resolved upstream (manual or LLM classification) rather
than re-derived from an :class:`IvaRate` + direction pair — that pipeline
never constructs an :class:`IvaInvoiceClassification`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG

# IvaRate (and the public ``iva_rate_kind`` accessor) are imported lazily
# inside ``classify_invoice_line_for_iva``
# to break a circular initialisation without violating the sibling-domain
# ``_enums`` ban (clause 5 of the structural enum-import placement check).
# At runtime the helpers are called only after the invoices package init
# finishes, so the public-package import resolves cleanly.
from .classification import InvoiceKind, domestic_categories_by_rate_kind
from .deduction_facts import IvaDeductionClassificationProvenance
from .flow import (
    IvaFlowDirection,
    IvaSettlementSide,
    flow_direction_for_invoice_kind,
    is_deducible_flow,
    is_devengada_flow,
    settlement_sides_for_flow,
)
from .schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind

if TYPE_CHECKING:
    from ..calculations.registry.ledger_iva_bindings import IvaLedgerObservation
    from ..invoices.enums import IvaRate
else:
    IvaRate = object


def _invoice_validation_error(message: str) -> Exception:
    """Build the invoice-domain validation error without importing invoices at module load."""
    from ..invoices.errors import InvoiceValidationError

    return InvoiceValidationError(message)


class IvaInvoiceClassification(BaseModel):
    """Frozen pydantic record bundling the IVA classification triple and derived settlement sides.

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

    model_config = STRICT_FROZEN_CONFIG

    category: IvaCategory
    rate_kind: IvaRateKind | None
    flow_direction: IvaFlowDirection
    settlement_sides: frozenset[IvaSettlementSide]

    @model_validator(mode="after")
    def _validate_settlement_sides_match_flow(self) -> IvaInvoiceClassification:
        expected = settlement_sides_for_flow(self.flow_direction)
        if self.settlement_sides != expected:
            raise _invoice_validation_error(
                f"settlement_sides {sorted(s.value for s in self.settlement_sides)!r} "
                f"does not match flow_direction {self.flow_direction.value!r} "
                f"(expected {sorted(s.value for s in expected)!r})",
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
    (:func:`cadrumo.domain.iva.classify_iva`).

    ``recargo_amount`` defaults to zero because most lines carry none. It is a
    parameter here rather than something a caller sets on the returned
    observation, so this stays the ONE bridge from invoice metadata into the
    observation shape: a caller that constructed the record itself to add a
    recargo would be a second construction path for the same concept, free to
    drift from this one's classification rules.

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
    from ..invoices.enums import IvaRate as _IvaRate
    from ..invoices.enums import iva_rate_kind

    if iva_rate is _IvaRate.NOT_SUBJECT:
        raise _invoice_validation_error(
            "classify_invoice_line_for_iva does not handle IvaRate.NOT_SUBJECT — "
            "operations outside the scope of IVA must construct "
            "IvaInvoiceClassification directly with IvaCategory.OPERACION_NO_SUJETA",
        )

    rate_kind = iva_rate_kind(iva_rate)
    if rate_kind is None:  # unreachable: NOT_SUBJECT (the only keyless rate) is rejected above
        raise _invoice_validation_error(f"IvaRate {iva_rate!r} has no rate-tier classification")
    # One canonical rate-kind to domestic-category table, composed with the
    # public rate-kind accessor. A local IvaRate-keyed copy used to live here
    # and was exactly this composition, so it could drift without any symbol
    # search relating the two.
    category = domestic_categories_by_rate_kind()[rate_kind]
    flow_direction = flow_direction_for_invoice_kind(invoice_kind)
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
    deduction_fact_kind: IvaDeductionFactKind | None,
    deduction_provenance: IvaDeductionClassificationProvenance | None,
    recargo_amount: Decimal = Decimal("0"),
    investment_asset_id: str | None = None,
    rectifies_ledger_id: str | None = None,
) -> IvaLedgerObservation:
    """Build an :class:`IvaLedgerObservation` from invoice line metadata.

    The runtime resolver for the substrate's ``ledger_iva_aggregation``
    binding source kind consumes
    :class:`cadrumo.domain.calculations.registry.IvaLedgerObservation`
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
        iva_amount: IVA amount in EUR.
        deduction_fact_kind: Exact statutory deduction family for a received
            IVA input, or ``None`` for an issued output.
        deduction_provenance: Immutable evidence provenance for a received
            IVA input, or ``None`` for an issued output.
        recargo_amount: Recargo de equivalencia charged on this line in EUR
            (LIVA art. 161), or zero when none was. Routed to the Modelo 303
            recargo cuota casilla for the line's rate tier via the
            ``recargo_amount_sum`` fact.
        deduction_fact_kind: Exact evidence-grounded deduction family for a
            received line. Output lines must leave it unset.
        deduction_provenance: Immutable authority for the received line's
            deduction family. Output lines must leave it unset.
        investment_asset_id: Reciprocal investment-register identity when the
            deduction family is an investment acquisition.
        rectifies_ledger_id: Corrected ledger identity for a rectification.

    Returns:
        An :class:`IvaLedgerObservation` with the full classification
        triple ready for binding-resolver consumption.

    Raises:
        InvoiceValidationError: If the classification produces a ``None``
            rate_kind (e.g. when ``iva_rate`` is ``NOT_SUBJECT``).
        IvaRateNotFoundError: If ``iva_rate`` names a rate that was not in
            force for its tier on ``issued_at`` -- a transitional food slot
            used outside its statutory window. The line asserts a rate the
            statute did not offer that day, so it is refused rather than
            recorded at whatever the tier happened to mean.
    """
    from ..calculations.registry.ledger_iva_bindings import IvaLedgerObservation
    from ..invoices.enums import iva_rate_percentage

    classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=invoice_kind)
    if classification.rate_kind is None:
        raise _invoice_validation_error("standard IVA invoice observations require a rate_kind")
    return IvaLedgerObservation(
        ledger_id=invoice_id,
        transaction_date=issued_at,
        category=classification.category,
        rate_kind=classification.rate_kind,
        flow_direction=classification.flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=deduction_provenance,
        investment_asset_id=investment_asset_id,
        rectifies_ledger_id=rectifies_ledger_id,
        # applied_rate was previously left unset, on the reasoning that an
        # invoice line carries a rate SLOT rather than a number, so filling it
        # would mean re-deriving the rate from the TIER -- answering "what does
        # this tier mean" instead of "what was this line charged", and inventing
        # agreement with a tier default the line may not have carried.
        #
        # That reasoning does not survive slots that name their own rate. The
        # RD-ley 4/2024 food slots exist precisely because 2 % and 4 % were both
        # correct super-reducido rates at once, so RATE_2 states a number the
        # tier cannot supply, and iva_rate_percentage now reads it off the slot
        # and confirms it was in force on issued_at rather than consulting the
        # tier. The rate is measured, not inferred, so withholding it would drop
        # the line out of every rate-specific box on the annual return -- the
        # 2 % foodstuffs line silently missing from the 2 % box it belongs in.
        applied_rate=iva_rate_percentage(iva_rate, issued_at),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


__all__ = [
    "IvaInvoiceClassification",
    "classify_invoice_line_for_iva",
    "invoice_line_to_iva_observation",
]

"""Inventory ledgers for actividad economica stock valuation.

Defines strict pydantic v2 records for tracking opening stock,
period movements (purchases, COGS, counts), and closing stock per
activity / year, plus the FIFO and weighted-average (PMP / coste
medio) valuation engines required by LIS art. 17.1. LIFO is rejected
explicitly via :class:`LIFOForbiddenError`.

Public functions:
    :func:`parse_valuation_method` — coerce user input into a
    :class:`ValuationMethod`, refusing LIFO.
    The valuation and Anexo D projection engines live in :mod:`.valuation`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, NamedTuple

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ....core.decimal.constants import HUNDRED, MONEY_ZERO, ONE
from ....core.errors.hierarchy import CadrumoError as _CadrumoError
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.identity.digest import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ....core.money.rounding import round_to_cents as _quantize
from ....core.percentage import Percentage
from ....core.time.utc import UtcInstant
from ....core.unit_proportion import UnitProportion
from ...buckets.event import BUCKET_ACTOR_LABEL_MAX_LENGTH
from ...filing_evidence import FilingEvidenceReference
from .closing_authority_records import InventoryClosingAuthorityRecord
from .closing_foundations import (
    InventoryLedgerError,
    InventoryValidationError,
    require_inventory_cents,
)


class AmortizacionLedgerError(_CadrumoError):
    """Raised when an amortizacion ledger operation is invalid."""


class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation.

    LIS art. 17.1 does not admit LIFO for tax-purpose stock valuation
    in this regime; the message routes the operator to FIFO, PMP, or
    coste medio.
    """

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """
        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )


class BasisCapExceededError(AmortizacionLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""


INVENTORY_SCHEMA_VERSION = "3"
"""Forward-compatible schema version stamped onto every record in this module."""


class MovementKind(StrEnum):
    """Supported inventory movement kinds.

    Attributes:
        OPENING: Stock present at the start of the period.
        PURCHASE: Inbound inventory acquisition.
        COGS: Cost-of-goods-sold consumption.
        COUNT: Adjustment to the physical count, modelled as a
            synthetic COGS movement against the discrepancy.
    """

    OPENING = "opening"
    PURCHASE = "purchase"
    COGS = "cogs"
    COUNT = "count"


class InventoryAcquisitionEvidenceKind(StrEnum):
    """Closed evidence authorities admitted for inventory acquisition facts."""

    PURCHASE_INVOICE = "purchase_invoice"
    TRANSPORT_DOCUMENT = "transport_document"
    INSURANCE_DOCUMENT = "insurance_document"
    CUSTOMS_DECLARATION = "customs_declaration"
    CONTRACT = "contract"
    OTHER_ACQUISITION_EVIDENCE = "other_acquisition_evidence"
    ATTRIBUTABLE_COST_REVIEW = "attributable_cost_review"
    IVA_RECOVERABILITY_REVIEW = "iva_recoverability_review"


class InventoryAttributableCostKind(StrEnum):
    """Closed directly-attributable cost vocabulary for inventory purchases."""

    FREIGHT = "freight"
    INSURANCE = "insurance"
    CUSTOMS_DUTY = "customs_duty"
    HANDLING = "handling"
    PROFESSIONAL_FEE = "professional_fee"
    OTHER_DIRECTLY_ATTRIBUTABLE = "other_directly_attributable"


class InventoryAcquisitionEvidence(BaseModel):
    """Nominal evidence reference plus its immutable content digest."""

    model_config = _STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    evidence_kind: InventoryAcquisitionEvidenceKind
    content_digest: ContentDigest


class InventoryAttributableCostComponent(BaseModel):
    """One evidenced cost directly attributable to an inventory purchase."""

    model_config = _STRICT_FROZEN_CONFIG

    component_id: str = Field(min_length=1, max_length=128)
    kind: InventoryAttributableCostKind
    taxable_base: Decimal = Field(gt=MONEY_ZERO)
    iva_amount: Decimal = Field(ge=MONEY_ZERO)
    deductible_iva_ratio: Decimal = Field(ge=MONEY_ZERO, le=ONE)
    evidence_references: tuple[FilingEvidenceReference, ...] = Field(min_length=1)

    @field_validator("component_id")
    @classmethod
    @pydantic_validation_boundary
    def _trim_component_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise InventoryValidationError("component_id must not be blank")
        return trimmed

    @field_validator("taxable_base", "iva_amount")
    @classmethod
    @pydantic_validation_boundary
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return require_inventory_cents(value, field_name=info.field_name or "amount")

    @field_validator("evidence_references")
    @classmethod
    @pydantic_validation_boundary
    def _evidence_references_are_distinct(
        cls,
        value: tuple[FilingEvidenceReference, ...],
    ) -> tuple[FilingEvidenceReference, ...]:
        identities = tuple(item.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("component evidence references must be unique")
        return value

    @property
    def recoverable_iva(self) -> Decimal:
        """Return IVA excluded from inventory acquisition cost."""
        return _quantize(self.iva_amount * self.deductible_iva_ratio)


class InventoryAcquisitionCompleteness(BaseModel):
    """Evidence-backed attestations that all three cost reviews occurred."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_evidence: FilingEvidenceReference
    attributable_cost_review_evidence: FilingEvidenceReference
    iva_recoverability_review_evidence: FilingEvidenceReference


class InventoryAcquisitionCost(BaseModel):
    """Complete, evidenced acquisition-cost decomposition for one purchase."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_excluding_iva: Decimal = Field(ge=MONEY_ZERO)
    consideration_iva_amount: Decimal = Field(ge=MONEY_ZERO)
    consideration_deductible_iva_ratio: Decimal = Field(ge=MONEY_ZERO, le=ONE)
    attributable_cost_components: tuple[InventoryAttributableCostComponent, ...]
    evidence: tuple[InventoryAcquisitionEvidence, ...] = Field(min_length=1)
    completeness: InventoryAcquisitionCompleteness
    directly_attributable_cost_total: Decimal = Field(ge=MONEY_ZERO)
    nonrecoverable_iva_included: Decimal = Field(ge=MONEY_ZERO)
    recoverable_iva_excluded: Decimal = Field(ge=MONEY_ZERO)
    total_acquisition_cost: Decimal = Field(ge=MONEY_ZERO)

    @field_validator(
        "consideration_excluding_iva",
        "consideration_iva_amount",
        "directly_attributable_cost_total",
        "nonrecoverable_iva_included",
        "recoverable_iva_excluded",
        "total_acquisition_cost",
    )
    @classmethod
    @pydantic_validation_boundary
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return require_inventory_cents(value, field_name=info.field_name or "amount")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_complete_decomposition(self) -> InventoryAcquisitionCost:
        evidence_ids = tuple(item.reference.reference for item in self.evidence)
        evidence_by_reference = _validate_acquisition_evidence_links(self, evidence_ids)
        _validate_acquisition_evidence_roles(self, evidence_by_reference)
        _validate_acquisition_amount_decomposition(self)
        return self


def _validate_acquisition_evidence_links(
    acquisition: InventoryAcquisitionCost,
    evidence_ids: tuple[str, ...],
) -> dict[str, InventoryAcquisitionEvidenceKind]:
    if len(set(evidence_ids)) != len(evidence_ids):
        raise InventoryValidationError("inventory acquisition evidence references must be unique")
    component_ids = tuple(item.component_id for item in acquisition.attributable_cost_components)
    if len(set(component_ids)) != len(component_ids):
        raise InventoryValidationError("inventory acquisition component identities must be unique")
    declared_refs = {
        acquisition.completeness.consideration_evidence.reference,
        acquisition.completeness.attributable_cost_review_evidence.reference,
        acquisition.completeness.iva_recoverability_review_evidence.reference,
        *(
            reference.reference
            for component in acquisition.attributable_cost_components
            for reference in component.evidence_references
        ),
    }
    missing = sorted(declared_refs - set(evidence_ids))
    if missing:
        raise InventoryValidationError(f"inventory acquisition evidence references are unresolved: {missing!r}")
    return {item.reference.reference: item.evidence_kind for item in acquisition.evidence}


def _validate_acquisition_evidence_roles(
    acquisition: InventoryAcquisitionCost,
    evidence_by_reference: dict[str, InventoryAcquisitionEvidenceKind],
) -> None:
    if (
        evidence_by_reference[acquisition.completeness.attributable_cost_review_evidence.reference]
        is not InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW
    ):
        raise InventoryValidationError("attributable-cost completeness requires attributable-cost review evidence")
    if (
        evidence_by_reference[acquisition.completeness.iva_recoverability_review_evidence.reference]
        is not InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW
    ):
        raise InventoryValidationError("IVA completeness requires IVA-recoverability review evidence")
    consideration_kind = evidence_by_reference[acquisition.completeness.consideration_evidence.reference]
    if consideration_kind in {
        InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
        InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
    }:
        raise InventoryValidationError("purchase consideration requires acquisition evidence, not review evidence")


class InventoryAcquisitionTotals(NamedTuple):
    """What a purchase's components add up to."""

    directly_attributable_cost_total: Decimal
    recoverable_iva_excluded: Decimal
    nonrecoverable_iva_included: Decimal
    total_acquisition_cost: Decimal


def derive_inventory_acquisition_totals(
    *,
    consideration_excluding_iva: Decimal,
    consideration_iva_amount: Decimal,
    consideration_deductible_iva_ratio: Decimal,
    attributable_cost_components: tuple[InventoryAttributableCostComponent, ...],
) -> InventoryAcquisitionTotals:
    """Add up one purchase: cost holds the price, attributable costs and the IVA that cannot be recovered."""
    attributable = sum((item.taxable_base for item in attributable_cost_components), MONEY_ZERO)
    recoverable = _quantize(
        consideration_iva_amount * consideration_deductible_iva_ratio,
    ) + sum((item.recoverable_iva for item in attributable_cost_components), MONEY_ZERO)
    total_iva = consideration_iva_amount + sum(
        (item.iva_amount for item in attributable_cost_components),
        MONEY_ZERO,
    )
    nonrecoverable = total_iva - recoverable
    total = consideration_excluding_iva + attributable + nonrecoverable
    return InventoryAcquisitionTotals(
        directly_attributable_cost_total=_quantize(attributable),
        recoverable_iva_excluded=_quantize(recoverable),
        nonrecoverable_iva_included=_quantize(nonrecoverable),
        total_acquisition_cost=_quantize(total),
    )


def _validate_acquisition_amount_decomposition(acquisition: InventoryAcquisitionCost) -> None:
    totals = derive_inventory_acquisition_totals(
        consideration_excluding_iva=acquisition.consideration_excluding_iva,
        consideration_iva_amount=acquisition.consideration_iva_amount,
        consideration_deductible_iva_ratio=acquisition.consideration_deductible_iva_ratio,
        attributable_cost_components=acquisition.attributable_cost_components,
    )
    for field_name, expected_value in totals._asdict().items():
        if getattr(acquisition, field_name) != expected_value:
            raise InventoryValidationError(f"{field_name} does not match the acquisition decomposition")


class InventoryAcquisitionFacts(BaseModel):
    """A purchase as an operator states it; :meth:`to_cost` adds up the totals left out."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_excluding_iva: Decimal = Field(ge=MONEY_ZERO)
    consideration_iva_amount: Decimal = Field(ge=MONEY_ZERO)
    consideration_deductible_iva_ratio: Decimal = Field(ge=MONEY_ZERO, le=ONE)
    attributable_cost_components: tuple[InventoryAttributableCostComponent, ...]
    evidence: tuple[InventoryAcquisitionEvidence, ...] = Field(min_length=1)
    completeness: InventoryAcquisitionCompleteness
    directly_attributable_cost_total: Decimal | None = None
    nonrecoverable_iva_included: Decimal | None = None
    recoverable_iva_excluded: Decimal | None = None
    total_acquisition_cost: Decimal | None = None

    def to_cost(self) -> InventoryAcquisitionCost:
        """Build the complete cost; a stated total stays stated, so the cost's validators can refuse it."""
        totals = derive_inventory_acquisition_totals(
            consideration_excluding_iva=self.consideration_excluding_iva,
            consideration_iva_amount=self.consideration_iva_amount,
            consideration_deductible_iva_ratio=self.consideration_deductible_iva_ratio,
            attributable_cost_components=self.attributable_cost_components,
        )
        return InventoryAcquisitionCost(
            consideration_excluding_iva=self.consideration_excluding_iva,
            consideration_iva_amount=self.consideration_iva_amount,
            consideration_deductible_iva_ratio=self.consideration_deductible_iva_ratio,
            attributable_cost_components=self.attributable_cost_components,
            evidence=self.evidence,
            completeness=self.completeness,
            directly_attributable_cost_total=(
                totals.directly_attributable_cost_total
                if self.directly_attributable_cost_total is None
                else self.directly_attributable_cost_total
            ),
            nonrecoverable_iva_included=(
                totals.nonrecoverable_iva_included
                if self.nonrecoverable_iva_included is None
                else self.nonrecoverable_iva_included
            ),
            recoverable_iva_excluded=(
                totals.recoverable_iva_excluded
                if self.recoverable_iva_excluded is None
                else self.recoverable_iva_excluded
            ),
            total_acquisition_cost=(
                totals.total_acquisition_cost if self.total_acquisition_cost is None else self.total_acquisition_cost
            ),
        )


def load_inventory_acquisition_cost(text: str) -> InventoryAcquisitionCost:
    """Read a purchase-cost JSON document: totals it states are checked, totals it omits are derived."""
    return InventoryAcquisitionFacts.model_validate_json(text).to_cost()


class ValuationMethod(StrEnum):
    """Supported inventory valuation methods."""

    FIFO = "fifo"
    PMP = "pmp"
    COSTE_MEDIO = "coste_medio"


class MovementRecord(BaseModel):
    """One inventory movement for an activity/year.

    Attributes:
        movement_id: Stable natural key for the movement.
        movement_date: Date the movement applies on.
        kind: :class:`MovementKind`.
        sku: SKU / item identifier; defaults to ``"default"`` for
            single-SKU ledgers.
        quantity: Movement quantity (strictly positive).
        unit_cost: IVA-exclusive per-unit cost.
        taxable_base: Invoice taxable base (IVA-exclusive).
        iva_rate: IVA rate percentage (0-100).
        iva_amount: Optional explicit IVA amount; when set must equal
            ``taxable_base * iva_rate / 100``.
        deductible_iva_ratio: Fraction of input IVA the contribuyente
            may deduct (0-1).
        schema_version: Forward-compatible schema version. ``"3"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    movement_id: str = Field(min_length=1)
    movement_date: date
    kind: MovementKind = MovementKind.PURCHASE
    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, ge=Decimal("0"))
    iva_rate: Percentage = Field(default=None, validate_default=True)
    iva_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_iva_ratio: UnitProportion = Decimal("1.00")
    acquisition_cost: InventoryAcquisitionCost | None = None
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @field_validator("iva_rate", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _default_iva_rate_from_movement_devengo(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        """Resolve an omitted rate through the dated Spanish IVA facade."""
        if isinstance(value, str) and info.mode == "json":
            # A before-validator hands JSON text through unparsed, and the strict
            # Decimal schema behind it accepts only an instance.
            return Decimal(value)
        if value is not None:
            return value
        movement_date = info.data.get("movement_date")
        if not isinstance(movement_date, date):
            raise InventoryValidationError("inventory IVA default requires a valid movement_date")
        from ...calculations.registry.authority import PinnedAuthorityOperation
        from ...calculations.registry.governed_fact_scope import governed_facts_in_scope
        from ...calculations.registry.iva_category_catalogue import require_iva_category
        from ...calculations.registry.iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
        from ...iva.lookup import lookup_rate
        from ...iva.schema import spanish_eu_member_state

        operation = governed_facts_in_scope()
        if not isinstance(operation, PinnedAuthorityOperation):
            raise InventoryValidationError(
                "inventory IVA default requires a generation-pinned authority operation",
            )
        rate_kind = resolve_iva_rate_kind_catalogue(
            effective_date=movement_date,
            authority=operation,
        ).for_category(
            require_iva_category(
                "domestic_general",
                effective_date=movement_date,
                authority=operation,
            ),
        )
        return lookup_rate(
            spanish_eu_member_state(effective_date=movement_date, authority=operation),
            rate_kind,
            movement_date,
            operation=operation,
        ).pct

    @classmethod
    def from_purchase_acquisition(
        cls,
        *,
        movement_id: str,
        movement_date: date,
        quantity: Decimal,
        acquisition_cost: InventoryAcquisitionCost,
        sku: str = "default",
    ) -> MovementRecord:
        """Project one complete acquisition into its canonical purchase movement."""
        consideration = acquisition_cost.consideration_excluding_iva
        iva_amount = acquisition_cost.consideration_iva_amount
        iva_rate = MONEY_ZERO if consideration == MONEY_ZERO else iva_amount * HUNDRED / consideration
        return cls(
            movement_id=movement_id,
            movement_date=movement_date,
            kind=MovementKind.PURCHASE,
            sku=sku,
            quantity=quantity,
            taxable_base=consideration,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            deductible_iva_ratio=acquisition_cost.consideration_deductible_iva_ratio,
            acquisition_cost=acquisition_cost,
        )

    @property
    def value(self) -> Decimal:
        """Return the IVA-exclusive movement value."""
        if self.taxable_base is not None:
            return self.taxable_base
        if self.unit_cost is None:
            return MONEY_ZERO
        return self.quantity * self.unit_cost

    @property
    def capitalized_value(self) -> Decimal:
        """Return the sole value capitalized by inventory valuation."""
        if self.kind is MovementKind.PURCHASE:
            acquisition_cost = self.acquisition_cost
            if acquisition_cost is None:
                raise InventoryValidationError("a purchase movement capitalizes its acquisition cost and declares none")
            return acquisition_cost.total_acquisition_cost
        return self.value

    @property
    def resolved_unit_cost(self) -> Decimal:
        """Return capitalized unit cost, falling back to consideration for openings."""
        if self.kind is MovementKind.PURCHASE:
            return self.capitalized_value / self.quantity
        if self.unit_cost is not None:
            return self.unit_cost
        if self.taxable_base is None:
            return MONEY_ZERO
        return self.taxable_base / self.quantity

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported MovementRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_movement_amounts(self) -> MovementRecord:
        """Enforce that opening / purchase movements carry a cost and IVA decomposes consistently."""
        _require_movement_cost(self)
        _validate_movement_taxable_amount(self)
        _validate_purchase_movement_acquisition(self)
        _validate_non_purchase_movement_acquisition(self)
        return self


def _require_movement_cost(movement: MovementRecord) -> None:
    needs_cost = movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}
    if needs_cost and movement.unit_cost is None and movement.taxable_base is None:
        raise InventoryValidationError("opening and purchase movements require unit_cost or taxable_base")


def _validate_movement_taxable_amount(movement: MovementRecord) -> None:
    if movement.taxable_base is not None:
        computed_iva = _quantize(movement.taxable_base * movement.iva_rate / HUNDRED)
        if movement.iva_amount is not None and movement.iva_amount != computed_iva:
            raise InventoryValidationError("iva_amount must equal taxable_base * iva_rate")
    if (
        movement.unit_cost is not None
        and movement.taxable_base is not None
        and _quantize(movement.quantity * movement.unit_cost) != movement.taxable_base
    ):
        raise InventoryValidationError("taxable_base must equal quantity * unit_cost")


def _validate_purchase_movement_acquisition(movement: MovementRecord) -> None:
    if movement.kind is not MovementKind.PURCHASE:
        return
    acquisition_cost = movement.acquisition_cost
    if acquisition_cost is None:
        raise InventoryValidationError("purchase movements require complete acquisition_cost")
    if acquisition_cost.consideration_excluding_iva != _quantize(movement.value):
        raise InventoryValidationError("acquisition consideration must equal the purchase consideration")
    expected_iva = movement.iva_amount
    if expected_iva is None:
        expected_iva = _quantize(movement.value * movement.iva_rate / HUNDRED)
    if acquisition_cost.consideration_iva_amount != expected_iva:
        raise InventoryValidationError("acquisition consideration IVA must equal the purchase IVA")
    if acquisition_cost.consideration_deductible_iva_ratio != movement.deductible_iva_ratio:
        raise InventoryValidationError("acquisition IVA recoverability must equal the purchase ratio")


def _validate_non_purchase_movement_acquisition(movement: MovementRecord) -> None:
    if movement.kind is not MovementKind.PURCHASE and movement.acquisition_cost is not None:
        raise InventoryValidationError("acquisition_cost is permitted only for purchase movements")


class StockLayer(BaseModel):
    """Remaining inventory quantity at one IVA-exclusive unit cost.

    Attributes:
        sku: SKU / item identifier.
        quantity: Layer quantity (strictly positive).
        unit_cost: Per-unit cost the layer was acquired at.
        source_movement_id: Stable id of the originating
            :class:`MovementRecord` (or a synthetic id for opening
            stock and weighted-average pools).
    """

    model_config = _STRICT_FROZEN_CONFIG

    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal = Field(ge=Decimal("0"))
    source_movement_id: str = Field(min_length=1)


class InventoryHistoryKind(StrEnum):
    """What one retained inventory history entry did to its ledger."""

    DESCRIBED = "described"
    OPENING_CORRECTED = "opening_corrected"
    MOVEMENT_CORRECTED = "movement_corrected"
    MOVEMENT_REVERSED = "movement_reversed"
    RETIRED = "retired"
    RESTORED = "restored"


class InventoryCorrectionReason(StrEnum):
    """Why a stock or opening fact was rectified."""

    KEYING_ERROR = "keying_error"
    SOURCE_DOCUMENT_CORRECTED = "source_document_corrected"
    DUPLICATE_ENTRY = "duplicate_entry"
    OPERATION_DID_NOT_OCCUR = "operation_did_not_occur"


class InventoryRetirementReason(StrEnum):
    """Why an inventory left the active register."""

    CREATED_IN_ERROR = "created_in_error"
    ACTIVITY_CEASED = "activity_ceased"
    NO_STOCK_HELD = "no_stock_held"


class InventoryLedgerDescriptor(BaseModel):
    """Descriptive facts of an inventory; they never enter its valuation or fingerprints."""

    model_config = _STRICT_FROZEN_CONFIG

    label: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("label", "description")
    @classmethod
    @pydantic_validation_boundary
    def _text_is_trimmed(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise InventoryValidationError("inventory descriptor text must be trimmed")
        return value


class InventoryLedgerHistoryEntry(BaseModel):
    """One retained change to a ledger, carrying the prior fact it displaced.

    Attributes:
        correction_id: Caller-chosen identity; repeating it with the same request
            is an exact replay.
        kind: :class:`InventoryHistoryKind`.
        recorded_at: When the change was recorded.
        actor: Who recorded it.
        request_fingerprint: Identity of the request, excluding actor and time.
        correction_reason: Why a stock or opening fact was rectified.
        retirement_reason: Why the inventory left the active register.
        superseded_movement: The movement taken out of the effective set.
        replacement_movement_id: The movement that replaced it, absent on a reversal.
        prior_opening_stock: The opening value the correction displaced.
        prior_valuation_method: The valuation method the correction displaced.
        prior_descriptor: The descriptor the change displaced, absent on the first.
    """

    model_config = _STRICT_FROZEN_CONFIG

    correction_id: str = Field(min_length=1, max_length=64)
    kind: InventoryHistoryKind
    recorded_at: UtcInstant
    actor: str = Field(min_length=1, max_length=BUCKET_ACTOR_LABEL_MAX_LENGTH)
    request_fingerprint: ContentDigest
    correction_reason: InventoryCorrectionReason | None = None
    retirement_reason: InventoryRetirementReason | None = None
    superseded_movement: MovementRecord | None = None
    replacement_movement_id: str | None = Field(default=None, min_length=1)
    prior_opening_stock: Decimal | None = Field(default=None, ge=Decimal("0"))
    prior_valuation_method: ValuationMethod | None = None
    prior_descriptor: InventoryLedgerDescriptor | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _facts_match_kind(self) -> InventoryLedgerHistoryEntry:
        """Hold each kind to exactly the facts it displaces."""
        kind = self.kind
        rectifies = kind in {
            InventoryHistoryKind.OPENING_CORRECTED,
            InventoryHistoryKind.MOVEMENT_CORRECTED,
            InventoryHistoryKind.MOVEMENT_REVERSED,
        }
        supersedes = kind in {InventoryHistoryKind.MOVEMENT_CORRECTED, InventoryHistoryKind.MOVEMENT_REVERSED}
        is_opening = kind is InventoryHistoryKind.OPENING_CORRECTED
        if (
            rectifies != (self.correction_reason is not None)
            or (kind is InventoryHistoryKind.RETIRED) != (self.retirement_reason is not None)
            or supersedes != (self.superseded_movement is not None)
            or (kind is InventoryHistoryKind.MOVEMENT_CORRECTED) != (self.replacement_movement_id is not None)
            or is_opening != (self.prior_opening_stock is not None)
            or is_opening != (self.prior_valuation_method is not None)
            or (self.prior_descriptor is not None and kind is not InventoryHistoryKind.DESCRIBED)
        ):
            raise InventoryValidationError("inventory history entry facts do not match its kind")
        return self


InventoryYear = Annotated[int, Field(ge=1900, le=9999)]
"""The calendar year an inventory ledger or movement covers.

Deliberately NOT the filing-year window. An inventory record may reach back
further than the registry has authored revisions for, so it carries its own
floor and no ceiling.
"""


class InventoryLedger(BaseModel):
    """Per-activity inventory ledger for one tax year.

    Attributes:
        actividad_id: Activity identifier the ledger is keyed by.
        year: Calendar year the ledger covers.
        valuation_method: FIFO, PMP, or coste medio; LIFO is forbidden.
        opening_stock: Aggregate IVA-exclusive opening valuation.
        opening_layers: Per-layer breakdown of opening stock; when
            non-empty must value-balance with ``opening_stock``.
        period_movements: Tuple of :class:`MovementRecord` rows
            covering the period.
        closing_authority_record: Required nullable persisted authority bundle;
            ``None`` states that no operator authority decision is recorded.
        schema_version: Forward-compatible schema version. ``"3"``.
        descriptor: Current descriptive facts; absent until described.
        history: Append-only record of every change, retaining what it displaced.
            ``period_movements`` stays the effective set, so every valuation and
            projection reads corrected facts without filtering.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str = Field(min_length=1)
    year: InventoryYear
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    opening_layers: tuple[StockLayer, ...] = ()
    period_movements: tuple[MovementRecord, ...] = ()
    closing_authority_record: InventoryClosingAuthorityRecord | None
    schema_version: str = INVENTORY_SCHEMA_VERSION
    descriptor: InventoryLedgerDescriptor | None = None
    history: tuple[InventoryLedgerHistoryEntry, ...] = ()

    @property
    def is_retired(self) -> bool:
        """Whether the latest retirement or restoration left it out of the active register."""
        return self.retirement_reason is not None

    @property
    def retirement_reason(self) -> InventoryRetirementReason | None:
        """The reason of the standing retirement, absent while active."""
        for entry in reversed(self.history):
            if entry.kind is InventoryHistoryKind.RETIRED:
                return entry.retirement_reason
            if entry.kind is InventoryHistoryKind.RESTORED:
                return None
        return None

    @property
    def has_economic_facts(self) -> bool:
        """Whether any effective movement or a nonzero opening value states a tax fact."""
        return bool(self.period_movements) or self.opening_stock != MONEY_ZERO

    @property
    def leaves_year_unresolved(self) -> bool:
        """Whether this retired book's facts stop its year's Anexo D from being resolved.

        Retirement is not proof that the stock never existed, so the facts are neither
        declared nor dropped.
        """
        return self.is_retired and self.has_economic_facts

    @property
    def known_movement_ids(self) -> frozenset[str]:
        """Every movement identity ever used here; a superseded one is never reissued."""
        return frozenset(
            (
                *(movement.movement_id for movement in self.period_movements),
                *(
                    entry.superseded_movement.movement_id
                    for entry in self.history
                    if entry.superseded_movement is not None
                ),
            )
        )

    @field_validator("actividad_id")
    @classmethod
    @pydantic_validation_boundary
    def _actividad_id_is_canonical(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise InventoryValidationError("inventory actividad_id is not canonical")
        return value

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedger schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _opening_stock_matches_layers(self) -> InventoryLedger:
        """Enforce that ``opening_layers`` value-balances with ``opening_stock``."""
        from ._anexo_d_records import resolve_inventory_authoritative_closing
        from .valuation import layers_value

        self._validate_movement_history()
        if self.opening_layers and _quantize(layers_value(self.opening_layers)) != _quantize(self.opening_stock):
            raise InventoryValidationError("opening_stock must equal the value of opening_layers")
        if self.closing_authority_record is not None:
            record = self.closing_authority_record
            if (record.decision.actividad_id, record.decision.filing_year) != (self.actividad_id, self.year):
                raise InventoryValidationError("closing authority record must match the inventory ledger coordinate")
            resolve_inventory_authoritative_closing(
                self,
                decision=record.decision,
                physical_observation=record.physical_observation,
                prior_closing_link=record.prior_closing_link,
            )
        return self

    def _validate_movement_history(self) -> None:
        movement_ids = tuple(movement.movement_id for movement in self.period_movements)
        if len(set(movement_ids)) != len(movement_ids):
            raise InventoryValidationError("inventory ledger movement_id values must be unique")
        correction_ids = tuple(entry.correction_id for entry in self.history)
        superseded_ids = tuple(
            entry.superseded_movement.movement_id for entry in self.history if entry.superseded_movement is not None
        )
        if len(set(correction_ids)) != len(correction_ids) or len(set(superseded_ids)) != len(superseded_ids):
            raise InventoryValidationError("inventory history identities must be unique")
        if set(superseded_ids) & set(movement_ids):
            raise InventoryValidationError("a superseded inventory movement cannot stay effective")


class InventoryLedgerDocument(BaseModel):
    """JSON document containing inventory ledgers.

    ``(actividad_id, year)`` is the natural key: creation, movement recording,
    and lookup all assume one canonical ledger per activity per year. The
    uniqueness invariant lives here, on the document, because the repository
    had two competing versions of it -- ``create`` and the application service
    refused a second ledger for a pair, while the public
    ``InventoryLedgerRepository.save`` path accepted any document and wrote it without
    validating, so a replacement could persist two ledgers for one pair while
    every reader still assumed one.

    Attributes:
        schema_version: Forward-compatible schema version. ``"3"``.
        ledgers: Tuple of :class:`InventoryLedger` rows, each with a distinct
            ``(actividad_id, year)`` pair.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = INVENTORY_SCHEMA_VERSION
    ledgers: tuple[InventoryLedger, ...] = ()

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedgerDocument schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _reject_duplicate_actividad_year(self) -> InventoryLedgerDocument:
        """Refuse a document carrying two ledgers for one activity and year.

        Enforced on the document rather than at a write method so creation,
        bulk replacement, and the read boundary answer the same way. Applying
        at the read boundary is deliberate: a stored document that already
        holds a duplicate pair has no canonical ledger for it, and surfacing it
        silently is what the repository used to do.
        """
        keys = [(ledger.actividad_id, ledger.year) for ledger in self.ledgers]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            rendered = ", ".join(f"{actividad_id}/{year}" for actividad_id, year in duplicates)
            raise InventoryValidationError(
                f"InventoryLedgerDocument carries duplicate actividad/year ledgers: {rendered}",
            )
        return self


def parse_valuation_method(raw: str) -> ValuationMethod:
    """Parse a user-supplied valuation method and refuse LIFO explicitly.

    Args:
        raw: User input (case- and separator-insensitive).

    Returns:
        The matching :class:`ValuationMethod` member.

    Raises:
        LIFOForbiddenError: When the input normalises to ``"lifo"``.
        InventoryLedgerError: When the input matches no known method.
    """
    normalized = raw.strip().lower().replace("-", "_")
    if normalized == "lifo":
        raise LIFOForbiddenError(raw)
    try:
        return ValuationMethod(normalized)
    except ValueError as exc:
        raise InventoryLedgerError(
            f"unknown valuation method {raw!r}; use fifo, pmp, or coste_medio",
            context={"method": raw},
        ) from exc


class InventoryValuationResult(BaseModel):
    """Computed valuation outcome for an inventory ledger.

    Attributes:
        closing_layers: Tuple of :class:`StockLayer` rows surviving
            after period movements were applied.
        closing_value: Aggregate closing valuation.
        cogs_value: Cost-of-goods-sold for the period.
        purchase_value: Aggregate value of PURCHASE movements during
            the period.
    """

    model_config = _STRICT_FROZEN_CONFIG

    closing_layers: tuple[StockLayer, ...]
    closing_value: Decimal
    cogs_value: Decimal
    purchase_value: Decimal

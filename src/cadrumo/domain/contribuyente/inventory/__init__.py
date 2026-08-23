"""Inventory ledgers for actividad economica stock valuation.

Defines strict pydantic v2 records for tracking opening stock,
period movements (purchases, COGS, counts), and closing stock per
activity / year, plus the FIFO and weighted-average (PMP / coste
medio) valuation engines required by LIS art. 17.1. LIFO is rejected
explicitly via :class:`LIFOForbiddenError`.

Public functions:
    :func:`parse_valuation_method` — coerce user input into a
    :class:`ValuationMethod`, refusing LIFO.
    :func:`compute_inventory_valuation` — value closing stock and
    COGS for one ledger.
    :func:`compute_inventory_anexo_d_projection` — split the 2025
    stock variation between casillas ``0177`` and ``0182``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.errors import CadrumoError as _CadrumoError
from ....core.errors import CoreValidationError as _CoreValidationError
from ....core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT as _DEFAULT_IVA_GENERAL_RATE_PCT
from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity import ContentDigest
from ....core.money import round_to_cents as _quantize
from ...filing_evidence import FilingEvidenceReference


class AmortizacionLedgerError(_CadrumoError):
    """Raised when an amortizacion ledger operation is invalid."""


class InventoryLedgerError(_CadrumoError):
    """Raised when an inventory ledger operation is invalid."""


class InventoryValidationError(InventoryLedgerError, _CoreValidationError):
    """Raised when an inventory ledger fails Pydantic validation.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """


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


INVENTORY_SCHEMA_VERSION = "2"
"""Forward-compatible schema version stamped onto every record in this module."""

_ZERO = Decimal("0.00")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


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


class InventoryAttributableCostKind(StrEnum):
    """Closed directly-attributable cost vocabulary for inventory purchases."""

    FREIGHT = "freight"
    INSURANCE = "insurance"
    CUSTOMS_DUTY = "customs_duty"
    HANDLING = "handling"
    PROFESSIONAL_FEE = "professional_fee"
    OTHER_DIRECTLY_ATTRIBUTABLE = "other_directly_attributable"


def _require_cents(value: Decimal, *, field_name: str) -> Decimal:
    if value != _quantize(value):
        raise InventoryValidationError(f"{field_name} must be quantised to cents")
    return value


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
    taxable_base: Decimal = Field(gt=_ZERO)
    iva_amount: Decimal = Field(ge=_ZERO)
    deductible_iva_ratio: Decimal = Field(ge=_ZERO, le=_ONE)
    evidence_references: tuple[FilingEvidenceReference, ...] = Field(min_length=1)

    @field_validator("component_id")
    @classmethod
    def _trim_component_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise InventoryValidationError("component_id must not be blank")
        return trimmed

    @field_validator("taxable_base", "iva_amount")
    @classmethod
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name)

    @field_validator("evidence_references")
    @classmethod
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

    @property
    def nonrecoverable_iva(self) -> Decimal:
        """Return IVA capitalized without independent rounding drift."""
        return self.iva_amount - self.recoverable_iva


class InventoryAcquisitionCompleteness(BaseModel):
    """Evidence-backed attestations that all three cost reviews occurred."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_evidence: FilingEvidenceReference
    attributable_cost_review_evidence: FilingEvidenceReference
    iva_recoverability_review_evidence: FilingEvidenceReference


class InventoryAcquisitionCost(BaseModel):
    """Complete, evidenced acquisition-cost decomposition for one purchase."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_excluding_iva: Decimal = Field(ge=_ZERO)
    consideration_iva_amount: Decimal = Field(ge=_ZERO)
    consideration_deductible_iva_ratio: Decimal = Field(ge=_ZERO, le=_ONE)
    attributable_cost_components: tuple[InventoryAttributableCostComponent, ...]
    evidence: tuple[InventoryAcquisitionEvidence, ...] = Field(min_length=1)
    completeness: InventoryAcquisitionCompleteness
    directly_attributable_cost_total: Decimal = Field(ge=_ZERO)
    nonrecoverable_iva_included: Decimal = Field(ge=_ZERO)
    recoverable_iva_excluded: Decimal = Field(ge=_ZERO)
    total_acquisition_cost: Decimal = Field(ge=_ZERO)

    @field_validator(
        "consideration_excluding_iva",
        "consideration_iva_amount",
        "directly_attributable_cost_total",
        "nonrecoverable_iva_included",
        "recoverable_iva_excluded",
        "total_acquisition_cost",
    )
    @classmethod
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_complete_decomposition(self) -> InventoryAcquisitionCost:
        evidence_ids = tuple(item.reference.reference for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InventoryValidationError("inventory acquisition evidence references must be unique")
        component_ids = tuple(item.component_id for item in self.attributable_cost_components)
        if len(set(component_ids)) != len(component_ids):
            raise InventoryValidationError("inventory acquisition component identities must be unique")
        declared_refs = {
            self.completeness.consideration_evidence.reference,
            self.completeness.attributable_cost_review_evidence.reference,
            self.completeness.iva_recoverability_review_evidence.reference,
            *(
                reference.reference
                for component in self.attributable_cost_components
                for reference in component.evidence_references
            ),
        }
        missing = sorted(declared_refs - set(evidence_ids))
        if missing:
            raise InventoryValidationError(f"inventory acquisition evidence references are unresolved: {missing!r}")

        attributable = sum((item.taxable_base for item in self.attributable_cost_components), _ZERO)
        recoverable = _quantize(
            self.consideration_iva_amount * self.consideration_deductible_iva_ratio,
        ) + sum((item.recoverable_iva for item in self.attributable_cost_components), _ZERO)
        total_iva = self.consideration_iva_amount + sum(
            (item.iva_amount for item in self.attributable_cost_components),
            _ZERO,
        )
        nonrecoverable = total_iva - recoverable
        total = self.consideration_excluding_iva + attributable + nonrecoverable
        expected = {
            "directly_attributable_cost_total": _quantize(attributable),
            "recoverable_iva_excluded": _quantize(recoverable),
            "nonrecoverable_iva_included": _quantize(nonrecoverable),
            "total_acquisition_cost": _quantize(total),
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise InventoryValidationError(f"{field_name} does not match the acquisition decomposition")
        return self


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
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    movement_id: str = Field(min_length=1)
    movement_date: date
    kind: MovementKind = MovementKind.PURCHASE
    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, ge=Decimal("0"))
    iva_rate: Decimal = Field(default=_DEFAULT_IVA_GENERAL_RATE_PCT, ge=Decimal("0"), le=Decimal("100"))
    iva_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_iva_ratio: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"), le=Decimal("1"))
    acquisition_cost: InventoryAcquisitionCost | None = None
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @property
    def value(self) -> Decimal:
        """Return the IVA-exclusive movement value."""
        if self.taxable_base is not None:
            return self.taxable_base
        if self.unit_cost is None:
            return _ZERO
        return self.quantity * self.unit_cost

    @property
    def capitalized_value(self) -> Decimal:
        """Return the sole value capitalized by inventory valuation."""
        if self.kind is MovementKind.PURCHASE:
            assert self.acquisition_cost is not None
            return self.acquisition_cost.total_acquisition_cost
        return self.value

    @property
    def resolved_unit_cost(self) -> Decimal:
        """Return capitalized unit cost, falling back to consideration for openings."""
        if self.kind is MovementKind.PURCHASE:
            return self.capitalized_value / self.quantity
        if self.unit_cost is not None:
            return self.unit_cost
        if self.taxable_base is None:
            return _ZERO
        return self.taxable_base / self.quantity

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported MovementRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_movement_amounts(self) -> MovementRecord:
        """Enforce that opening / purchase movements carry a cost and IVA decomposes consistently."""
        needs_cost = self.kind in {MovementKind.OPENING, MovementKind.PURCHASE}
        if needs_cost and self.unit_cost is None and self.taxable_base is None:
            raise InventoryValidationError("opening and purchase movements require unit_cost or taxable_base")
        if self.taxable_base is not None:
            computed_iva = _quantize(self.taxable_base * self.iva_rate / _HUNDRED)
            if self.iva_amount is not None and self.iva_amount != computed_iva:
                raise InventoryValidationError("iva_amount must equal taxable_base * iva_rate")
        if (
            self.unit_cost is not None
            and self.taxable_base is not None
            and _quantize(self.quantity * self.unit_cost) != self.taxable_base
        ):
            raise InventoryValidationError("taxable_base must equal quantity * unit_cost")
        if self.kind is MovementKind.PURCHASE:
            if self.acquisition_cost is None:
                raise InventoryValidationError("purchase movements require complete acquisition_cost")
            if self.acquisition_cost.consideration_excluding_iva != _quantize(self.value):
                raise InventoryValidationError("acquisition consideration must equal the purchase consideration")
            expected_iva = self.iva_amount
            if expected_iva is None:
                expected_iva = _quantize(self.value * self.iva_rate / _HUNDRED)
            if self.acquisition_cost.consideration_iva_amount != expected_iva:
                raise InventoryValidationError("acquisition consideration IVA must equal the purchase IVA")
            if self.acquisition_cost.consideration_deductible_iva_ratio != self.deductible_iva_ratio:
                raise InventoryValidationError("acquisition IVA recoverability must equal the purchase ratio")
        elif self.acquisition_cost is not None:
            raise InventoryValidationError("acquisition_cost is permitted only for purchase movements")
        return self


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


class InventoryLedger(BaseModel):
    """Per-activity inventory ledger for one tax year.

    Attributes:
        actividad_id: Activity identifier the ledger is keyed by.
        year: Calendar year the ledger covers.
        valuation_method: FIFO, PMP, or coste medio; LIFO is forbidden.
        opening_stock: Aggregate IVA-exclusive opening valuation.
        opening_layers: Per-layer breakdown of opening stock; when
            non-empty must value-balance with ``opening_stock``.
        closing_stock: Optional explicit closing valuation; when
            ``None`` it is derived from movements at compute time.
        period_movements: Tuple of :class:`MovementRecord` rows
            covering the period.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    opening_layers: tuple[StockLayer, ...] = ()
    closing_stock: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_movements: tuple[MovementRecord, ...] = ()
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedger schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _opening_stock_matches_layers(self) -> InventoryLedger:
        """Enforce that ``opening_layers`` value-balances with ``opening_stock``."""
        if self.opening_layers and _quantize(_layers_value(self.opening_layers)) != _quantize(self.opening_stock):
            raise InventoryValidationError("opening_stock must equal the value of opening_layers")
        return self


class InventoryLedgerDocument(BaseModel):
    """JSON document containing inventory ledgers.

    ``(actividad_id, year)`` is the natural key: creation, movement recording,
    and lookup all assume one canonical ledger per activity per year. The
    uniqueness invariant lives here, on the document, because the repository
    had two competing versions of it -- ``create`` and the application service
    refused a second ledger for a pair, while the public
    ``save``/``save_inventory`` path accepted any document and wrote it without
    validating, so a replacement could persist two ledgers for one pair while
    every reader still assumed one.

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        ledgers: Tuple of :class:`InventoryLedger` rows, each with a distinct
            ``(actividad_id, year)`` pair.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = INVENTORY_SCHEMA_VERSION
    ledgers: tuple[InventoryLedger, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedgerDocument schema_version {value!r}")
        return value

    @model_validator(mode="after")
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


class InventoryAnexoDResult(BaseModel):
    """Auditable 2025 stock-variation projection for one activity.

    ``casilla_0177`` carries a closing-over-opening increase and
    ``casilla_0182`` carries an opening-over-closing decrease. The source
    opening and closing values remain on the result so the split can be
    reviewed without reconstructing its basis. Purchase acquisition cost for
    casilla ``0181`` is deliberately absent until the inventory source can
    prove the complete acquisition-cost fact.
    """

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    filing_year: Literal[2025]
    opening_value: Decimal = Field(ge=_ZERO)
    closing_value: Decimal = Field(ge=_ZERO)
    casilla_0177: Decimal = Field(ge=_ZERO)
    casilla_0182: Decimal = Field(ge=_ZERO)

    @model_validator(mode="after")
    def _variation_split_matches_audited_values(self) -> InventoryAnexoDResult:
        """Require an exact, mutually exclusive split of the audited basis."""
        monetary_values = (self.opening_value, self.closing_value, self.casilla_0177, self.casilla_0182)
        if any(value != _quantize(value) for value in monetary_values):
            raise InventoryValidationError("inventory Anexo D values must be quantised to cents")
        signed_variation = _quantize(self.closing_value - self.opening_value)
        expected_increase = max(signed_variation, _ZERO)
        expected_decrease = max(-signed_variation, _ZERO)
        if self.casilla_0177 != expected_increase or self.casilla_0182 != expected_decrease:
            raise InventoryValidationError(
                "inventory Anexo D outputs must be the mutually exclusive split of closing minus opening",
            )
        return self


def compute_inventory_anexo_d_projection(ledger: InventoryLedger) -> InventoryAnexoDResult:
    """Project one 2025 activity ledger to inventory variation casillas.

    The canonical valuation engine supplies closing value. An explicit
    physical closing value may confirm that result, but this pre-authority
    projection refuses a conflict because the current ledger carries no
    provenance capable of adjudicating an override.

    Args:
        ledger: The single activity/year inventory coordinate to project.

    Returns:
        Audited values split between casillas ``0177`` and ``0182``.

    Raises:
        InventoryLedgerError: If the ledger is outside the grounded 2025
            revision or an explicit closing conflicts with derived valuation.
    """
    if ledger.year != 2025:
        raise InventoryLedgerError(
            "inventory Anexo D projection is grounded only for filing year 2025",
            context={"actividad_id": ledger.actividad_id, "filing_year": ledger.year},
        )
    out_of_period_movements = tuple(
        movement.movement_id for movement in ledger.period_movements if movement.movement_date.year != ledger.year
    )
    if out_of_period_movements:
        raise InventoryLedgerError(
            "inventory Anexo D projection contains movements outside its filing year",
            context={
                "actividad_id": ledger.actividad_id,
                "filing_year": ledger.year,
                "movement_ids": out_of_period_movements,
            },
        )
    derived_closing = compute_inventory_valuation(ledger).closing_value
    if ledger.closing_stock is not None and _quantize(ledger.closing_stock) != derived_closing:
        raise InventoryLedgerError(
            "explicit inventory closing conflicts with movement-derived valuation",
            context={
                "actividad_id": ledger.actividad_id,
                "filing_year": ledger.year,
                "explicit_closing": str(_quantize(ledger.closing_stock)),
                "derived_closing": str(derived_closing),
            },
        )
    opening = _quantize(ledger.opening_stock)
    signed_variation = _quantize(derived_closing - opening)
    return InventoryAnexoDResult(
        actividad_id=ledger.actividad_id,
        filing_year=2025,
        opening_value=opening,
        closing_value=derived_closing,
        casilla_0177=max(signed_variation, _ZERO),
        casilla_0182=max(-signed_variation, _ZERO),
    )


def compute_inventory_valuation(ledger: InventoryLedger) -> InventoryValuationResult:
    """Value closing stock and COGS using the ledger's valuation method.

    Dispatches to the FIFO or weighted-average implementation per
    :attr:`InventoryLedger.valuation_method`.

    Args:
        ledger: Ledger to value.

    Returns:
        :class:`InventoryValuationResult` carrying the closing layers,
        closing valuation, COGS, and purchase totals.

    Raises:
        InventoryLedgerError: When ``valuation_method`` is not
            supported (defence-in-depth — should be unreachable as
            LIFO is rejected at parse time).
    """
    if ledger.valuation_method is ValuationMethod.FIFO:
        return _compute_fifo(ledger)
    if ledger.valuation_method in {ValuationMethod.PMP, ValuationMethod.COSTE_MEDIO}:
        return _compute_weighted_average(ledger)
    raise InventoryLedgerError(f"unsupported valuation method {ledger.valuation_method.value}")


def _compute_fifo(ledger: InventoryLedger) -> InventoryValuationResult:
    layers = list(_opening_layers(ledger))
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
            unit_cost = movement.resolved_unit_cost
            layers.append(
                StockLayer(
                    sku=movement.sku,
                    quantity=movement.quantity,
                    unit_cost=unit_cost,
                    source_movement_id=movement.movement_id,
                ),
            )
            if movement.kind is MovementKind.PURCHASE:
                purchase_value += movement.quantity * unit_cost
            continue
        if movement.kind is MovementKind.COGS:
            consumed, layers = _consume_fifo(layers, movement)
            cogs_value += consumed
            continue
        if movement.kind is MovementKind.COUNT:
            layers = _apply_count(layers, movement)
    closing = _layers_value(layers)
    return InventoryValuationResult(
        closing_layers=tuple(layers),
        closing_value=_quantize(closing),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _compute_weighted_average(ledger: InventoryLedger) -> InventoryValuationResult:
    pools = _weighted_average_opening_pools(ledger)
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        purchase_delta, cogs_delta = _apply_weighted_average_movement(ledger, movement, pools)
        purchase_value += purchase_delta
        cogs_value += cogs_delta
    layers = _weighted_average_layers(ledger, pools)
    return InventoryValuationResult(
        closing_layers=layers,
        closing_value=_quantize(sum((quantity_value[1] for quantity_value in pools.values()), _ZERO)),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _weighted_average_opening_pools(ledger: InventoryLedger) -> dict[str, tuple[Decimal, Decimal]]:
    pools: dict[str, tuple[Decimal, Decimal]] = {}
    for layer in _opening_layers(ledger):
        quantity, value = pools.get(layer.sku, (_ZERO, _ZERO))
        pools[layer.sku] = (quantity + layer.quantity, value + layer.quantity * layer.unit_cost)
    return pools


def _apply_weighted_average_movement(
    ledger: InventoryLedger,
    movement: MovementRecord,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    quantity, value = pools.get(movement.sku, (_ZERO, _ZERO))
    if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
        unit_cost = movement.resolved_unit_cost
        movement_value = movement.quantity * unit_cost
        pools[movement.sku] = (quantity + movement.quantity, value + movement_value)
        purchase_delta = movement_value if movement.kind is MovementKind.PURCHASE else _ZERO
        return purchase_delta, _ZERO
    if movement.kind is MovementKind.COGS:
        return _apply_weighted_average_cogs(ledger, movement, quantity, value, pools)
    if movement.kind is MovementKind.COUNT:
        average = _ZERO if quantity == _ZERO else value / quantity
        pools[movement.sku] = (movement.quantity, movement.quantity * average)
    return _ZERO, _ZERO


def _apply_weighted_average_cogs(
    ledger: InventoryLedger,
    movement: MovementRecord,
    quantity: Decimal,
    value: Decimal,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    if movement.quantity > quantity:
        raise InventoryLedgerError(
            "inventory movement would consume more stock than available",
            context={
                "actividad_id": ledger.actividad_id,
                "movement_id": movement.movement_id,
                "available_quantity": str(quantity),
                "requested_quantity": str(movement.quantity),
            },
        )
    average = _ZERO if quantity == _ZERO else value / quantity
    consumed = movement.quantity * average
    pools[movement.sku] = (quantity - movement.quantity, value - consumed)
    return _ZERO, consumed


def _weighted_average_layers(
    ledger: InventoryLedger,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[StockLayer, ...]:
    return tuple(
        StockLayer(
            sku=sku,
            quantity=quantity,
            unit_cost=_quantize(_ZERO if quantity == _ZERO else value / quantity),
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-{sku}-weighted-average",
        )
        for sku, (quantity, value) in sorted(pools.items())
        if quantity > _ZERO
    )


def _consume_fifo(layers: list[StockLayer], movement: MovementRecord) -> tuple[Decimal, list[StockLayer]]:
    remaining = movement.quantity
    consumed = _ZERO
    updated: list[StockLayer] = []
    for layer in layers:
        if layer.sku != movement.sku or remaining <= _ZERO:
            updated.append(layer)
            continue
        take = min(layer.quantity, remaining)
        consumed += take * layer.unit_cost
        remaining -= take
        leftover = layer.quantity - take
        if leftover > _ZERO:
            updated.append(layer.model_copy(update={"quantity": leftover}))
    if remaining > _ZERO:
        raise InventoryLedgerError(
            "inventory movement would consume more stock than available",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "missing_quantity": str(remaining),
            },
        )
    return consumed, updated


def _apply_count(layers: list[StockLayer], movement: MovementRecord) -> list[StockLayer]:
    current_quantity = sum((layer.quantity for layer in layers if layer.sku == movement.sku), _ZERO)
    if movement.quantity > current_quantity:
        raise InventoryLedgerError(
            "inventory count cannot increase stock without a purchase movement",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "available_quantity": str(current_quantity),
                "counted_quantity": str(movement.quantity),
            },
        )
    to_remove = current_quantity - movement.quantity
    synthetic_cogs = movement.model_copy(update={"kind": MovementKind.COGS, "quantity": to_remove})
    _, updated = _consume_fifo(layers, synthetic_cogs)
    return updated


def _opening_layers(ledger: InventoryLedger) -> tuple[StockLayer, ...]:
    if ledger.opening_layers:
        return ledger.opening_layers
    if ledger.opening_stock == _ZERO:
        return ()
    return (
        StockLayer(
            sku="default",
            quantity=Decimal("1"),
            unit_cost=ledger.opening_stock,
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-opening",
        ),
    )


def _sorted_movements(ledger: InventoryLedger) -> tuple[MovementRecord, ...]:
    return tuple(sorted(ledger.period_movements, key=lambda item: (item.movement_date, item.movement_id)))


def _layers_value(layers: tuple[StockLayer, ...] | list[StockLayer]) -> Decimal:
    return sum((layer.quantity * layer.unit_cost for layer in layers), _ZERO)


def inventory_acquisition_fingerprint(movement: MovementRecord) -> ContentDigest:
    """Return a deterministic versioned economic/evidence purchase fingerprint."""
    if movement.kind is not MovementKind.PURCHASE or movement.acquisition_cost is None:
        raise InventoryValidationError("only a complete purchase acquisition can be fingerprinted")
    acquisition = movement.acquisition_cost
    payload = {
        "fingerprint_schema_version": "1",
        "movement_id": movement.movement_id,
        "movement_date": movement.movement_date.isoformat(),
        "kind": movement.kind.value,
        "sku": movement.sku,
        "quantity": format(movement.quantity, "f"),
        "consideration_excluding_iva": format(acquisition.consideration_excluding_iva, "f"),
        "consideration_iva_amount": format(acquisition.consideration_iva_amount, "f"),
        "consideration_deductible_iva_ratio": format(acquisition.consideration_deductible_iva_ratio, "f"),
        "components": [
            {
                "component_id": item.component_id,
                "kind": item.kind.value,
                "taxable_base": format(item.taxable_base, "f"),
                "iva_amount": format(item.iva_amount, "f"),
                "deductible_iva_ratio": format(item.deductible_iva_ratio, "f"),
                "evidence_references": sorted(ref.reference for ref in item.evidence_references),
            }
            for item in sorted(acquisition.attributable_cost_components, key=lambda value: value.component_id)
        ],
        "evidence": [
            {
                "reference": item.reference.reference,
                "evidence_kind": item.evidence_kind.value,
                "content_digest": item.content_digest,
            }
            for item in sorted(acquisition.evidence, key=lambda value: value.reference.reference)
        ],
        "completeness": acquisition.completeness.model_dump(mode="json"),
        "totals": {
            "directly_attributable_cost_total": format(acquisition.directly_attributable_cost_total, "f"),
            "nonrecoverable_iva_included": format(acquisition.nonrecoverable_iva_included, "f"),
            "recoverable_iva_excluded": format(acquisition.recoverable_iva_excluded, "f"),
            "total_acquisition_cost": format(acquisition.total_acquisition_cost, "f"),
        },
    }
    return _content_hash_hex(payload)


__all__ = [
    "AmortizacionLedgerError",
    "BasisCapExceededError",
    "InventoryAcquisitionCompleteness",
    "InventoryAcquisitionCost",
    "InventoryAcquisitionEvidence",
    "InventoryAcquisitionEvidenceKind",
    "InventoryAnexoDResult",
    "InventoryAttributableCostComponent",
    "InventoryAttributableCostKind",
    "InventoryLedger",
    "InventoryLedgerError",
    "InventoryValidationError",
    "LIFOForbiddenError",
    "MovementKind",
    "MovementRecord",
    "StockLayer",
    "ValuationMethod",
    "compute_inventory_anexo_d_projection",
    "compute_inventory_valuation",
    "inventory_acquisition_fingerprint",
    "parse_valuation_method",
]

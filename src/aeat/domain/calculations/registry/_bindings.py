"""Data binding helpers for registry-backed factual inputs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, Period
from ....core.aggregation import BindingAggregationOp, BindingSourceKind, CounterpartSourceKind, RowSetGroupingKind
from ._binding_aggregation import binding_aggregation_op, default_binding_aggregation_op
from ._binding_selector_utils import selector_against_model, selector_as_dict
from ._bindings_previous_filing import (
    _PreviousModeloSelector,
    previous_filing_observation_requirements,
    previous_filing_source_reference,
    resolve_previous_filing_binding_values,
    validate_previous_filing_binding,
)
from ._counterpart_bindings import (
    CounterpartAggregationObservation,
    CounterpartObservationRequirement,
    counterpart_binding_requirements,
    resolve_counterpart_binding_row_values,
    resolve_counterpart_binding_values,
    validate_counterpart_binding,
)
from ._detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
    _AtributionSelector,
    _build_foreign_asset_rows,
    _build_related_party_rows,
    _ForeignAssetSelector,
    _RefundSelector,
    _RelatedPartySelector,
    resolve_atribucion_binding_row_values,
    resolve_foreign_asset_binding_row_values,
    resolve_refund_binding_row_values,
    resolve_related_party_binding_row_values,
    validate_atribucion_binding,
    validate_foreign_asset_binding,
    validate_refund_binding,
    validate_related_party_binding,
)
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, FormulaId, LegalRefId, OracleId, SourceRefId
from ._invoice_bindings import (
    INVOICE_BINDING_SOURCE_KINDS,
    InvoiceObservation,
    InvoiceObservationRequirement,
    _InvoiceSelector,
    invoice_binding_requirements,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
    validate_invoice_binding,
    validate_invoice_binding_definition,
)
from ._ledger_bindings import (
    LEDGER_BINDING_SOURCE_KINDS,
    IvaLedgerObservation,
    OssIossLedgerObservation,
    RentaExpenseObservationProtocol,
    RentaGastoObservationProtocol,
    RentaIncomeObservationProtocol,
    _IvaLedgerSelector,
    _OssIossLedgerSelector,
    _RentaLedgerExpenseSelector,
    _RentaLedgerGastoSelector,
    _RentaLedgerIncomeSelector,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_oss_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
    resolve_ledger_renta_gasto_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    unsupported_ledger_oss_observations,
    unsupported_ledger_renta_expense_observations,
    unsupported_ledger_renta_gasto_observations,
    unsupported_ledger_renta_income_observations,
    validate_ledger_iva_aggregation_binding,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding,
    validate_ledger_oss_aggregation_binding_definition,
    validate_ledger_renta_expense_aggregation_binding,
    validate_ledger_renta_expense_aggregation_binding_definition,
    validate_ledger_renta_gasto_aggregation_binding,
    validate_ledger_renta_gasto_aggregation_binding_definition,
    validate_ledger_renta_income_aggregation_binding,
    validate_ledger_renta_income_aggregation_binding_definition,
)
from ._retenciones_bindings import (
    resolve_retenciones_aggregation_binding_values,
    validate_retenciones_aggregation_binding,
)
from ._schema import DataBindingDefinition, InputKind, ModeloRevision
from ._withholding_bindings import (
    WithholdingObservation,
    WithholdingObservationRequirement,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
    validate_withholding_binding_selector_shape,
    withholding_binding_requirements,
)

__all__ = [
    "INVOICE_BINDING_SOURCE_KINDS",
    "LEDGER_BINDING_SOURCE_KINDS",
    "AtributionMemberObservation",
    "BindingAggregationOp",
    "CasillaObservation",
    "CounterpartAggregationObservation",
    "CounterpartObservationRequirement",
    "CounterpartSourceKind",
    "DataBindingDefinition",
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "IvaLedgerObservation",
    "Modelo720RowObservation",
    "OracleModeloObservation",
    "OssIossLedgerObservation",
    "RefundOperationObservation",
    "RegistryModeloObservation",
    "RelatedPartyOperationObservation",
    "RentaExpenseObservationProtocol",
    "RentaGastoObservationProtocol",
    "RentaIncomeObservationProtocol",
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "_build_foreign_asset_rows",
    "_build_related_party_rows",
    "binding_aggregation_op",
    "binding_source_casilla_ids",
    "counterpart_binding_requirements",
    "default_binding_aggregation_op",
    "invoice_binding_requirements",
    "previous_filing_observation_requirements",
    "previous_filing_source_reference",
    "resolve_atribucion_binding_row_values",
    "resolve_bound_inputs_by_casilla_id",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
    "resolve_foreign_asset_binding_row_values",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_expense_aggregation_binding_values",
    "resolve_ledger_renta_gasto_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "resolve_previous_filing_binding_values",
    "resolve_refund_binding_row_values",
    "resolve_related_party_binding_row_values",
    "resolve_retenciones_aggregation_binding_values",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "selector_model_for_source",
    "unsupported_ledger_iva_observations",
    "unsupported_ledger_oss_observations",
    "unsupported_ledger_renta_expense_observations",
    "unsupported_ledger_renta_gasto_observations",
    "unsupported_ledger_renta_income_observations",
    "validate_invoice_binding_definition",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_expense_aggregation_binding_definition",
    "validate_ledger_renta_gasto_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding_definition",
    "validate_retenciones_aggregation_binding",
    "withholding_binding_requirements",
]

#: One per-family ``validate(binding) -> list[str]`` accumulating validator. Every
#: source family registers exactly one in :data:`_BINDING_VALIDATOR_REGISTRY`.
_BindingFamilyValidator = Callable[[DataBindingDefinition], list[str]]


def _tuple_from_json_array(value: object) -> object:
    if isinstance(value, list):
        return tuple(value)
    return value


def _decimal_from_json_string(value: object) -> object:
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise RegistryValidationError("casilla observation decimal JSON value must be numeric") from exc
    return value


def _decimal_tuple_from_json_array(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decimal_from_json_string(item) for item in value)
    return value


class CasillaObservation(BaseModel):
    """One typed casilla observation emitted by the formula runtime.

    Carries the casilla id + final Decimal value plus optional formula
    provenance: when ``formula_id`` is set, the runtime computed this
    casilla and ``operand_refs`` / ``operand_values`` trace its inputs
    while ``operand_casilla_refs`` carries the casilla-id-only projection;
    when ``formula_id`` is ``None`` the casilla was supplied as input
    (manual / bound) and the trace fields are empty.

    Used as the primary storage for :class:`RegistryCalculationResult`;
    legacy ``values`` and ``entries`` views derive from it.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value: Decimal
    formula_id: FormulaId | None = None
    # ``op`` is the formula's top-level operator label (``add``, ``multiply``,
    # ``lookup_bracket_by_ccaa`` …). Carried alongside ``formula_id`` so the
    # full :class:`RegistryCalculationEntry` shape projects back from a typed
    # observation tuple without losing the dispatch label. ``None`` for
    # input / bound casillas where no formula ran.
    op: str | None = None
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[Decimal, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    # Set ``True`` when the casilla's declared binding produced no
    # source anchor for the target period (e.g. Modelo 130 casilla 15
    # at 1T — the prior-quarter carry-forward selector with
    # ``max_year_delta = 0`` suppresses the cross-ejercicio anchor).
    # The value is ``Decimal("0")`` materialised through an explicit
    # constructor, not the silent ``inputs.get(..., _ZERO)`` fallback
    # that the runtime previously used for missing bound values.
    # Downstream audit and review surfaces should distinguish
    # absent-by-design zeros from value-bearing observations.
    absent_by_design: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def _decimal_value_from_json_string(cls, value: object) -> object:
        return _decimal_from_json_string(value)

    @field_validator("value")
    @classmethod
    def _decimal_value(cls, value: Decimal) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError("casilla observation value must be Decimal")
        return value

    @field_validator("operand_refs", "operand_casilla_refs", "legal_refs", "source_refs", mode="before")
    @classmethod
    def _tuple_fields_from_json_arrays(cls, value: object) -> object:
        return _tuple_from_json_array(value)

    @field_validator("operand_values", mode="before")
    @classmethod
    def _decimal_tuple_field_from_json_array(cls, value: object) -> object:
        return _decimal_tuple_from_json_array(value)

    @model_validator(mode="after")
    def _operand_casilla_refs_are_traced(self) -> CasillaObservation:
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise RegistryValidationError(
                f"casilla observation for {self.casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class RegistryModeloObservation(BaseModel):
    """Observed casilla values from a filed declaration.

    Storage is ``observations`` — a typed tuple of :class:`CasillaObservation`
    carrying full formula provenance. The ``casilla_values`` computed field
    provides a read-only mapping view for downstream consumers.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=32)
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        if not isinstance(data, Mapping) or "filing_period" in data:
            return data
        filing_year = data.get("filing_year")
        period = data.get("period")
        if not isinstance(filing_year, int) or not isinstance(period, str):
            return data
        try:
            filing_period = Period.from_year_and_code(filing_year, period)
        except ValueError as exc:
            raise RegistryValidationError("observation period must be a bare registry period token") from exc
        return {**data, "filing_period": filing_period}

    @field_validator("observations", mode="before")
    @classmethod
    def _observations_from_json_array(cls, value: object) -> object:
        return _tuple_from_json_array(value)

    @model_validator(mode="after")
    def _validate_filing_period_consistency(self) -> RegistryModeloObservation:
        if self.filing_period is None:
            return self
        if self.filing_period.filing_year != self.filing_year:
            raise RegistryValidationError("observation filing_period year must match filing_year")
        if self.filing_period.registry_token != self.period:
            raise RegistryValidationError("observation filing_period code must match period")
        return self

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]:
        """Read-only mapping view: casilla_id -> Decimal derived from typed observations.

        Deliberately a plain ``@property`` and NOT a pydantic
        ``computed_field``: the typed envelope (``observations``) is
        canonical storage. Exposing this derived view in JSON would
        round-trip self-incompatibly under ``extra='forbid'`` because
        the loader would refuse the duplicate field on the way back in.
        """
        return {obs.casilla_id: obs.value for obs in self.observations}


class OracleModeloObservation(RegistryModeloObservation):
    """Observed casilla values whose source is a live AEAT oracle adapter.

    A subtype of :class:`RegistryModeloObservation` that marks the
    observation tuple as oracle-originated rather than locally computed.
    The ``oracle_id`` field anchors the observation to the
    ``LiveCrossReferenceDecision`` that produced it, so the application
    layer can route oracle-originated values through the
    cross-reference policy (synthetic-payload verification, replay
    quarantine, etc.) without ambiguity about provenance.

    Distinct from the parent only by the typed ``oracle_id`` field;
    every other invariant is inherited unchanged.
    """

    oracle_id: OracleId


def resolve_bound_inputs_by_casilla_id(
    revision: ModeloRevision,
    facts: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Resolve factual binding values into input values keyed by canonical ``casilla.id``.

    ``facts`` is keyed by registry binding id. The binding layer only selects
    factual values; it does not own legal rates, thresholds, or casilla meaning.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve against.
        facts: Mapping of binding id to the factual Decimal value.
    """
    for key, value in facts.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"binding fact {key!r} must be a Decimal")
    binding_ids = {binding.id for binding in revision.bindings}
    unknown = sorted(set(facts).difference(binding_ids))
    if unknown:
        raise RegistryValidationError(f"unknown binding fact ids: {unknown!r}")
    resolved: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND:
            continue
        if casilla.binding is None:
            raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
        if casilla.binding not in facts:
            raise RegistryValidationError(f"missing binding fact for casilla {casilla.id!r}: {casilla.binding!r}")
        resolved[casilla.id] = facts[casilla.binding]
    return resolved


# Binding-family implementations are split by source family. This module keeps
# the historical registry import surface and owns cross-family selector-shape
# dispatch only.
_ManualInputDataType = Literal["boolean", "integer", "text", "decimal", "money"]


class _RelationPrefillSelector(BaseModel):
    """Strict validator for a ``relation_prefill`` slot-binding selector.

    A ``relation_prefill`` binding is a materialisation SLOT for a registry
    relation's ``target_binding``: the cross-modelo (or period-variant)
    fold-in value is produced by :class:`RelationPrefillSourceResolver`
    folding prior filed observations through the relation's aggregation op,
    and written into this binding's slot. The selector therefore mirrors the
    relation's source descriptor (``source_modelo`` plus the source casilla id it pulls)
    rather than carrying its own resolution logic — the relation is the
    authority for periods, year alignment, and aggregation. The slot exists
    only so a bound casilla can consume the materialised Decimal.

    This is the canonical declared replacement for the mis-stamped
    ``previous_filing`` non-direct slots (aggregation-taxonomy ADR ruling 3):
    a slot binding declares ``source = "relation_prefill"``, never
    ``previous_filing``.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=8)
    source_casilla_id: CasillaId | None = Field(default=None, min_length=1)
    source_casilla_ids: tuple[CasillaId, ...] = ()
    source_periods: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_source_shape(self) -> _RelationPrefillSelector:
        if self.source_casilla_id is not None and self.source_casilla_ids:
            raise RegistryValidationError(
                "relation_prefill selector cannot declare both source_casilla_id and source_casilla_ids",
            )
        if self.source_casilla_id is None and not self.source_casilla_ids:
            raise RegistryValidationError(
                "relation_prefill selector must declare source_casilla_id or source_casilla_ids",
            )
        return self


def _relation_prefill_selector(binding: DataBindingDefinition) -> _RelationPrefillSelector:
    selector = selector_as_dict(binding)
    try:
        return _RelationPrefillSelector.model_validate(selector)
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed relation_prefill selector: {exc}",
        ) from exc


def _relation_prefill_source_ids(selector: _RelationPrefillSelector) -> tuple[CasillaId, ...]:
    if selector.source_casilla_ids:
        return selector.source_casilla_ids
    if selector.source_casilla_id is not None:
        return (selector.source_casilla_id,)
    return ()


def binding_source_casilla_ids(binding: DataBindingDefinition) -> tuple[CasillaId, ...]:
    """Return typed source casilla ids declared by binding families that have them."""
    if binding.source == "previous_filing":
        return previous_filing_source_reference(binding).source_casilla_ids
    if binding.source == "relation_prefill":
        return _relation_prefill_source_ids(_relation_prefill_selector(binding))
    return ()


class _ProfileSelector(BaseModel):
    """Strict validator for the selector mapping of a profile-source binding.

    Profile-source bindings read values from the taxpayer profile substrate
    (declarante, conyuge, hijos, ascendientes, ...). They land on the
    fichero-BOE record either as a typed scalar (single ``profile_key``)
    or via a composite projection (``profile_keys`` with a ``format``
    rendering function), and optionally as a sub-collection field of a
    typed profile model (``profile_model`` + ``collection`` + ``field``).

    Two cross-cutting fields apply to every shape:

    * ``xsd_path`` / ``xsd_attribute`` / ``dictionary_field``: how the
      value is addressed on the on-wire record.
    * ``required_when_profile_key`` / ``required_when_value``: a
      conditional applicability gate; only certain profile shapes set
      these.
    """

    model_config = STRICT_FROZEN_CONFIG

    # Scalar shape
    profile_key: str | None = Field(default=None, min_length=1, max_length=128)
    # Composite shape
    profile_keys: tuple[str, ...] = ()
    # Collection shape (typed sub-models on the profile)
    profile_model: str | None = Field(default=None, min_length=1, max_length=128)
    collection: str | None = Field(default=None, min_length=1, max_length=64)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    repeating: bool = False
    # On-wire addressing
    xsd_path: str | None = Field(default=None, min_length=1, max_length=512)
    xsd_attribute: str | None = Field(default=None, min_length=1, max_length=128)
    dictionary_field: str | None = Field(default=None, min_length=1, max_length=128)
    # Rendering / formatting
    format: str | None = Field(default=None, min_length=1, max_length=64)
    valid_at: str | None = Field(default=None, min_length=1, max_length=32)
    # Conditional applicability
    required_when_profile_key: str | None = Field(default=None, min_length=1, max_length=128)
    required_when_value: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _validate_profile_shape(self) -> _ProfileSelector:
        has_scalar = self.profile_key is not None
        has_composite = bool(self.profile_keys)
        has_collection = self.profile_model is not None
        shape_count = sum((has_scalar, has_composite, has_collection))
        if shape_count != 1:
            raise RegistryValidationError(
                "profile selector must declare exactly one of profile_key (scalar), "
                "profile_keys (composite), or profile_model (collection)",
            )
        if has_composite and self.format is None:
            raise RegistryValidationError("profile composite selector (profile_keys) requires a format renderer")
        if has_collection:
            if self.field is None:
                raise RegistryValidationError("profile model selector must declare field")
            # ``collection`` is only required when the profile model
            # selector targets a repeating sub-collection
            # (``repeating = true`` plus a named ``collection``). Scalar
            # fields on a typed profile model (e.g. ``profile_model =
            # "TaxResidenceProfile"`` + ``field = "ccaa"``) omit
            # ``collection`` because the field IS at the model root.
            if self.repeating and self.collection is None:
                raise RegistryValidationError("profile collection selector with repeating=true must declare collection")
        # required_when_* must be paired
        if (self.required_when_profile_key is None) != (self.required_when_value is None):
            raise RegistryValidationError(
                "profile selector required_when_profile_key and required_when_value must be declared together",
            )
        return self


_MANUAL_INPUT_RECORD_SHAPE_KEYS: frozenset[str] = frozenset(("record", "field", "offset", "length"))
"""Canonical record-field shape keys on the manual_input selector.

Single source of truth for both the typed validator in
:class:`_ManualInputSelector` and the layout-binding predicate at
:func:`aeat.domain.calculations.registry._validate._is_layout_binding`.
"""


def is_layout_binding_selector(selector: Mapping[str, object]) -> bool:
    """Return True when ``selector`` carries the record-field layout shape.

    The predicate intentionally mirrors the record-shape keys declared
    on :class:`_ManualInputSelector` rather than re-implementing the
    check via raw key inspection. Validate gate behaviour stays
    coupled to the typed model: if the manual_input record-shape key
    set is ever extended or renamed, the layout predicate follows
    automatically.
    """
    if "data_type" not in selector:
        return False
    return _MANUAL_INPUT_RECORD_SHAPE_KEYS.issubset(selector)


class _ManualInputSelector(BaseModel):
    """Strict validator for the selector mapping of a manual_input binding.

    Two shapes are accepted, gated by ``_validate_manual_input_shape``:

    * **Casilla shape** ``{casilla_id, data_type, true_value?, false_value?}``:
      The operator types the value directly into a registry casilla; the
      ``casilla_id`` names the canonical ``casilla.id`` and ``data_type``
      declares how the typed enum / boolean maps to the on-wire payload
      string. Used for boolean casillas like M100/0168
      (estimacion-directa modality flag).
    * **Record-field shape** ``{record, field, offset, length, data_type}``:
      The operator types a value that lands in a fichero-BOE record field
      at a specific byte offset / length. Used by M131 and other modelos
      whose bindings inject operator-typed metadata into fixed-width
      records.

    The two shapes are exclusive at the validator level.
    """

    model_config = STRICT_FROZEN_CONFIG

    # casilla shape
    casilla_id: CasillaId | None = Field(default=None, min_length=1, max_length=64)
    true_value: str | None = Field(default=None, min_length=1, max_length=64)
    false_value: str | None = Field(default=None, min_length=1, max_length=64)
    # record-field shape
    record: str | None = Field(default=None, min_length=1, max_length=64)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    offset: int | None = Field(default=None, ge=1)
    length: int | None = Field(default=None, ge=1)
    # both shapes
    data_type: _ManualInputDataType

    @model_validator(mode="after")
    def _validate_manual_input_shape(self) -> _ManualInputSelector:
        record_shape_keys = _MANUAL_INPUT_RECORD_SHAPE_KEYS
        has_casilla = self.casilla_id is not None
        has_record_shape = any(getattr(self, key) is not None for key in record_shape_keys)
        if has_casilla and has_record_shape:
            raise RegistryValidationError(
                "manual_input selector must declare either the casilla shape or the record-field shape, not both",
            )
        if not has_casilla and not has_record_shape:
            raise RegistryValidationError("manual_input selector must declare a casilla_id or a record-field shape")
        if has_record_shape:
            missing = [key for key in record_shape_keys if getattr(self, key) is None]
            if missing:
                raise RegistryValidationError(
                    f"manual_input record-field selector is missing required keys: {sorted(missing)!r}",
                )
        # Boolean casilla shape always pairs the data_type with explicit
        # true_value / false_value strings so the on-wire encoding is
        # deterministic.
        if has_casilla and self.data_type == "boolean" and (self.true_value is None or self.false_value is None):
            raise RegistryValidationError(
                "manual_input boolean-casilla_id selector must declare true_value and false_value",
            )
        return self


# ---------------------------------------------------------------------------
# Discriminated-selector registry
#
# Each entry pairs a ``DataBindingDefinition.source`` literal with the strict
# pydantic model that the binding's selector must validate against. Sources
# absent from this map are intentionally free-form for now: their selector
# shape varies across legacy registries or is consumed by ad-hoc validators
# elsewhere. As new typed selectors land, they should be registered here so
# the snapshot-build gate validates them automatically.
# ---------------------------------------------------------------------------


_BINDING_SELECTOR_REGISTRY: dict[str, type[BaseModel]] = {
    "previous_filing": _PreviousModeloSelector,
    "relation_prefill": _RelationPrefillSelector,
    # Counterpart-aggregation family: every source whose selector shape
    # mirrors the invoice family (fact + claves + rectification_scope +
    # optional row_field / grouping / record) is validated against
    # ``_InvoiceSelector``. The ``_validated_counterpart_selector``
    # helper adds counterpart-specific fact / op invariants on top
    # of the shared schema at handler-call time.
    BindingSourceKind.LEDGER_TRANSACTION: _InvoiceSelector,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: _InvoiceSelector,
    BindingSourceKind.PAYABLE_INVOICE: _InvoiceSelector,
    BindingSourceKind.COLLECTIBLE_INVOICE: _InvoiceSelector,
    "ledger_oss_aggregation": _OssIossLedgerSelector,
    "ledger_iva_aggregation": _IvaLedgerSelector,
    "ledger_renta_expense_aggregation": _RentaLedgerExpenseSelector,
    "ledger_renta_income_aggregation": _RentaLedgerIncomeSelector,
    "ledger_renta_gasto_aggregation": _RentaLedgerGastoSelector,
    "related_party_operation": _RelatedPartySelector,
    RowSetGroupingKind.FOREIGN_ASSET: _ForeignAssetSelector,
    "atribucion_member": _AtributionSelector,
    "refund_operation": _RefundSelector,
    "manual_input": _ManualInputSelector,
    "profile": _ProfileSelector,
}


def selector_model_for_source(source: object) -> type[BaseModel] | None:
    """Return the strict selector model a binding ``source`` validates against.

    Read-only accessor over :data:`_BINDING_SELECTOR_REGISTRY`, the
    discriminated-union table keyed by :class:`~aeat.core.BindingSourceKind`
    (the canonical ``DataBindingDefinition.source`` axis). Returns the
    per-family selector model when the source carries a typed selector schema,
    or ``None`` when the source is intentionally free-form (absent from the
    table) — so callers can short-circuit selector-shape validation for
    free-form sources exactly as the snapshot-build gate does.

    The model-level selector validator on
    :class:`~aeat.domain.calculations.registry.DataBindingDefinition` consumes
    this accessor to promote selector-shape typing to model-construction time
    without re-deriving the table; the op/fact cross-invariants stay owned by
    :func:`validate_binding_selector_shape` at snapshot build.
    """
    return _BINDING_SELECTOR_REGISTRY.get(source)


def _validate_selector_only(selector_model: type[BaseModel]) -> _BindingFamilyValidator:
    """Build a family validator that only validates the selector shape.

    For families with no op/fact cross-invariant beyond the strict selector
    model (``manual_input``, ``profile``, ``relation_prefill``), the family
    validator is simply :func:`selector_against_model` against the registered
    model. The underlying pydantic field error is preserved in the diagnostic.
    """

    def _validate(binding: DataBindingDefinition) -> list[str]:
        return selector_against_model(binding, selector_model)

    return _validate


# ---------------------------------------------------------------------------
# Single binding validator-dispatch table
#
# One ``validate(binding) -> list[str]`` accumulating validator per source
# family, keyed by the canonical ``BindingSourceKind``. Every entry returns a
# list of diagnostic strings (empty when the binding is well formed) so the
# registry-build section validator can run one path for every family and
# accumulate every failure across a revision in one pass — replacing the prior
# split between the raise-style per-source validators and the list-returning
# selector-shape gate. Each family validator validates the selector shape
# (preserving the underlying pydantic field error) and lifts that family's
# op/fact invariants to build time; the raise-style resolve-time helpers remain
# as defence-in-depth re-checks.
# ---------------------------------------------------------------------------


_BINDING_VALIDATOR_REGISTRY: dict[str, _BindingFamilyValidator] = {
    "previous_filing": validate_previous_filing_binding,
    "relation_prefill": _validate_selector_only(_RelationPrefillSelector),
    # The three invoice-shaped sources run the stricter invoice validator (the
    # union of the prior dual path: selector-shape + counterpart fact/op
    # invariants + the two invoice-only scalar-shape guards). ledger_transaction
    # is a counterpart-only source (never an invoice source) and keeps the
    # counterpart validator.
    BindingSourceKind.LEDGER_TRANSACTION: validate_counterpart_binding,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: validate_invoice_binding,
    BindingSourceKind.PAYABLE_INVOICE: validate_invoice_binding,
    BindingSourceKind.COLLECTIBLE_INVOICE: validate_invoice_binding,
    "ledger_oss_aggregation": validate_ledger_oss_aggregation_binding,
    "ledger_iva_aggregation": validate_ledger_iva_aggregation_binding,
    "ledger_renta_expense_aggregation": validate_ledger_renta_expense_aggregation_binding,
    "ledger_renta_income_aggregation": validate_ledger_renta_income_aggregation_binding,
    "ledger_renta_gasto_aggregation": validate_ledger_renta_gasto_aggregation_binding,
    "retenciones_aggregation": validate_retenciones_aggregation_binding,
    "related_party_operation": validate_related_party_binding,
    RowSetGroupingKind.FOREIGN_ASSET: validate_foreign_asset_binding,
    "atribucion_member": validate_atribucion_binding,
    "refund_operation": validate_refund_binding,
    RowSetGroupingKind.WITHHOLDING: validate_withholding_binding_selector_shape,
    "manual_input": _validate_selector_only(_ManualInputSelector),
    "profile": _validate_selector_only(_ProfileSelector),
}


def validate_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate a binding against its source family's single build-time validator.

    Routes the binding through the one per-family ``validate(binding) ->
    list[str]`` validator registered in :data:`_BINDING_VALIDATOR_REGISTRY`,
    keyed by :class:`~aeat.core.BindingSourceKind`. Each family validator
    validates the selector shape (projected through :func:`_selector_as_dict`
    inside :func:`selector_against_model`, so the gate sees the SAME normalised
    mapping the resolve-time helpers see and is never stricter than runtime) and
    lifts that family's op/fact cross-invariants to build time. Failures are
    accumulated as diagnostic strings rather than raised, preserving the
    underlying pydantic field error, so the snapshot-build gate can collect every
    failure across a revision in one pass.

    For every family — including the four detail-record families
    (``related_party_operation``, ``foreign_asset``, ``atribucion_member``,
    ``refund_operation``) and ``previous_filing`` whose op/fact invariants
    previously ran only at resolve time — a malformed binding is now rejected at
    snapshot build rather than only when a taxpayer calculation invokes the
    resolver.

    Sources NOT in the dispatch table are intentionally free-form today; those
    bindings short-circuit with an empty failure list.
    """
    validator = _BINDING_VALIDATOR_REGISTRY.get(binding.source)
    if validator is None:
        return []
    return validator(binding)

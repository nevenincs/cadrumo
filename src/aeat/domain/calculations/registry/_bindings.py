"""Data binding helpers for registry-backed factual inputs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, Period
from ....core.aggregation import AggregationSourceKind, CounterpartSourceKind, RowSetGroupingKind
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._bindings_previous_filing import (
    RegistryModeloObservationRequirement,
    _PreviousModeloSelector,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ._counterpart_bindings import (
    COUNTERPART_BINDING_SOURCE_KINDS,
    CounterpartAggregationObservation,
    CounterpartObservationRequirement,
    _validated_counterpart_selector,
    counterpart_binding_requirements,
    resolve_counterpart_binding_row_values,
    resolve_counterpart_binding_values,
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
)
from ._errors import RegistryValidationError
from ._ids import CasillaId, FormulaId, OracleId
from ._invoice_bindings import (
    INVOICE_BINDING_SOURCE_KINDS,
    InvoiceObservation,
    InvoiceObservationRequirement,
    _InvoiceSelector,
    invoice_binding_requirements,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
    validate_invoice_binding_definition,
)
from ._ledger_bindings import (
    LEDGER_BINDING_SOURCE_KINDS,
    IvaLedgerObservation,
    OssIossLedgerObservation,
    RentaExpenseObservationProtocol,
    RentaIncomeObservationProtocol,
    _IvaLedgerSelector,
    _OssIossLedgerSelector,
    _RentaLedgerExpenseSelector,
    _RentaLedgerIncomeSelector,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_oss_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding_definition,
    validate_ledger_renta_expense_aggregation_binding_definition,
    validate_ledger_renta_income_aggregation_binding_definition,
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
    "RegistryModeloObservationRequirement",
    "RelatedPartyOperationObservation",
    "RentaExpenseObservationProtocol",
    "RentaIncomeObservationProtocol",
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "_build_foreign_asset_rows",
    "_build_related_party_rows",
    "counterpart_binding_requirements",
    "invoice_binding_requirements",
    "previous_filing_observation_requirements",
    "resolve_atribucion_binding_row_values",
    "resolve_bound_casilla_inputs",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
    "resolve_foreign_asset_binding_row_values",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_expense_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "resolve_previous_filing_binding_values",
    "resolve_refund_binding_row_values",
    "resolve_related_party_binding_row_values",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "unsupported_ledger_iva_observations",
    "validate_invoice_binding_definition",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_expense_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding_definition",
    "withholding_binding_requirements",
]


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
    casilla and ``operand_refs`` / ``operand_values`` trace its inputs;
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
    operand_values: tuple[Decimal, ...] = ()
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
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

    @field_validator("operand_refs", "legal_refs", "source_refs", mode="before")
    @classmethod
    def _tuple_fields_from_json_arrays(cls, value: object) -> object:
        return _tuple_from_json_array(value)

    @field_validator("operand_values", mode="before")
    @classmethod
    def _decimal_tuple_field_from_json_array(cls, value: object) -> object:
        return _decimal_tuple_from_json_array(value)


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
    period: str = Field(min_length=1, max_length=8)
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
    def casilla_values(self) -> Mapping[str, Decimal]:
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


def resolve_bound_casilla_inputs(
    revision: ModeloRevision,
    facts: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Resolve factual binding values into casilla input values.

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
    resolved: dict[str, Decimal] = {}
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
    relation's source descriptor (``source_modelo`` plus the output it pulls)
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
    source_output: str | None = Field(default=None, min_length=1)
    source_casillas: tuple[str, ...] = ()
    source_periods: tuple[str, ...] = ()


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

    * **Casilla shape** ``{casilla, data_type, true_value?, false_value?}``:
      The operator types the value directly into a registry casilla; the
      ``data_type`` declares how the typed enum / boolean maps to the
      on-wire payload string. Used for boolean casillas like M100/0168
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
    casilla: str | None = Field(default=None, min_length=1, max_length=64)
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
        has_casilla = self.casilla is not None
        has_record_shape = any(getattr(self, key) is not None for key in record_shape_keys)
        if has_casilla and has_record_shape:
            raise RegistryValidationError(
                "manual_input selector must declare either the casilla shape or the record-field shape, not both",
            )
        if not has_casilla and not has_record_shape:
            raise RegistryValidationError("manual_input selector must declare a casilla or a record-field shape")
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
                "manual_input boolean-casilla selector must declare true_value and false_value",
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
    AggregationSourceKind.LEDGER_TRANSACTION: _InvoiceSelector,
    AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE: _InvoiceSelector,
    AggregationSourceKind.PAYABLE_INVOICE: _InvoiceSelector,
    AggregationSourceKind.COLLECTIBLE_INVOICE: _InvoiceSelector,
    "ledger_oss_aggregation": _OssIossLedgerSelector,
    "ledger_iva_aggregation": _IvaLedgerSelector,
    "ledger_renta_expense_aggregation": _RentaLedgerExpenseSelector,
    "ledger_renta_income_aggregation": _RentaLedgerIncomeSelector,
    "related_party_operation": _RelatedPartySelector,
    RowSetGroupingKind.FOREIGN_ASSET: _ForeignAssetSelector,
    "atribucion_member": _AtributionSelector,
    "refund_operation": _RefundSelector,
    "manual_input": _ManualInputSelector,
    "profile": _ProfileSelector,
}


def validate_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate ``binding.selector`` against the source's typed selector model.

    Sources registered in :data:`_BINDING_SELECTOR_REGISTRY` get their
    selector mapping piped through the strict pydantic model that owns
    the per-source key set. Failures are returned as a list of
    diagnostic strings rather than raised so the snapshot-build gate
    can accumulate every failure across a revision in one pass.

    The selector is projected through :func:`_selector_as_dict` before
    validation so the gate sees the SAME normalised mapping the
    handler-call-time helpers see. Without this projection the gate
    would reject any registry binding whose loaded selector still
    carries the (test-injected or legacy) ``source`` key, while the
    handler would accept it — a stricter-than-runtime drift that
    must not land in production.

    Counterpart-source bindings (``ledger_transaction``,
    ``purchase_invoice_evidence``, ``payable_invoice``,
    ``collectible_invoice``) additionally run the fact/op cross-check
    invariants that the handler-call-time ``_validated_counterpart_selector``
    enforces — so a snapshot whose binding declared
    ``fact = "operator_count"`` paired with ``aggregation.op = "sum"``
    (a real cross-shape error) is caught at registry-build time
    rather than only when the resolver is invoked.

    Sources NOT in the registry are intentionally free-form today;
    those bindings short-circuit with an empty failure list.
    """
    selector_model = _BINDING_SELECTOR_REGISTRY.get(binding.source)
    if binding.source == RowSetGroupingKind.WITHHOLDING:
        return validate_withholding_binding_selector_shape(binding)
    if selector_model is None:
        return []
    try:
        selector_model.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {selector_model.__name__}: {exc}",
        ]
    # Counterpart-source bindings get the additional fact/op
    # invariants that ``_validated_counterpart_selector`` runs at
    # handler-call time, lifted up here so registry-build catches
    # them too. Audit selector-drift F3.
    if binding.source in COUNTERPART_BINDING_SOURCE_KINDS:
        try:
            _validated_counterpart_selector(binding)
        except RegistryValidationError as exc:
            return [f"binding {binding.id!r} (source={binding.source!r}) counterpart invariants violated: {exc}"]
    return []

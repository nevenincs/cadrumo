"""Data binding helpers for registry-backed factual inputs.

This module owns the
:class:`~domain.calculations.registry.CasillaObservation` envelope emitted
by the formula runtime and the
:class:`~domain.calculations.registry.DataBindingDefinition` helper
surface that turns factual binding values into bound casilla inputs.

See Also:
    :mod:`domain.calculations.registry._formula_runtime`
        Runtime that emits typed observations and consumes resolved bound
        casilla inputs.
    :mod:`domain.calculations.registry._formula_initial_values`
        Initial-value assembler that calls the bound-casilla helpers here.
    :mod:`domain.calculations.registry._schema`
        Registry schema definitions for casillas, bindings, and revisions.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Literal, TypeGuard

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ....core import (
    OBJECT_TUPLE_ADAPTER,
    STRICT_FROZEN_CONFIG,
    CasillaId,
    FilingPeriodCode,
    Period,
    RegistryPeriodCode,
)
from ....core.aggregation import BindingAggregationOp, BindingSourceKind, CounterpartSourceKind
from ...iva_compensation import (
    M303_COMPENSATION_APLICADA_CASILLA,
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
)
from ._binding_aggregation import binding_aggregation_op, default_binding_aggregation_op
from ._binding_selector_utils import selector_against_model, selector_as_dict
from ._bindings_previous_filing import (
    PreviousModeloSelector,
    previous_filing_binding_source_casilla_ids,
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
    foreign_asset_binding_row_field,
    resolve_atribucion_binding_row_values,
    resolve_foreign_asset_binding_row_values,
    resolve_refund_binding_row_values,
    resolve_related_party_binding_row_values,
    validate_atribucion_binding,
    validate_foreign_asset_binding,
    validate_refund_binding,
    validate_related_party_binding,
)
from ._detail_record_bindings import (
    AtributionSelector as _AtributionSelector,
)
from ._detail_record_bindings import (
    ForeignAssetSelector as _ForeignAssetSelector,
)
from ._detail_record_bindings import (
    RefundSelector as _RefundSelector,
)
from ._detail_record_bindings import (
    RelatedPartySelector as _RelatedPartySelector,
)
from ._detail_record_bindings import (
    build_foreign_asset_rows as _build_foreign_asset_rows,
)
from ._detail_record_bindings import (
    build_related_party_rows as _build_related_party_rows,
)
from ._donativo_bindings import (
    DonativoDonorObservation,
    resolve_donativo_binding_row_values,
    validate_donativo_binding,
)
from ._donativo_bindings import (
    DonativoSelector as _DonativoSelector,
)
from ._errors import RegistryValidationError
from ._gasto193_bindings import (
    Gasto193Observation,
    _Gasto193Selector,
    resolve_gasto193_binding_row_values,
    resolve_gasto193_binding_values,
    validate_gasto193_binding_selector_shape,
)
from ._ids import BindingId, FormulaId, LegalRefId, ModeloId, OracleId, SourceRefId
from ._inventory_bindings import (
    InventoryProjectionOperation,
    InventorySelector,
    validate_inventory_binding,
)
from ._invoice_bindings import (
    INVOICE_BINDING_SOURCE_KINDS,
    InvoiceObservation,
    InvoiceObservationRequirement,
    Modelo349OperadorClaveTotal,
    Modelo349OperadorTotalsParity,
    compute_modelo_349_operador_totals_parity,
    invoice_binding_requirements,
    is_m347_declarante_summary_invoice_binding,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
    validate_invoice_binding,
    validate_invoice_binding_definition,
)
from ._invoice_bindings import (
    InvoiceSelector as _InvoiceSelector,
)
from ._irnr_ledger_bindings import (
    IrnrIncomeObservationProtocol,
    _IrnrLedgerIncomeSelector,
    resolve_ledger_irnr_income_aggregation_binding_values,
    unsupported_ledger_irnr_income_observations,
    validate_ledger_irnr_income_aggregation_binding,
    validate_ledger_irnr_income_aggregation_binding_definition,
)
from ._ledger_binding_resolution import UnroutedLedgerQuantity
from ._ledger_bindings import (
    LEDGER_BINDING_SOURCE_KINDS,
    IvaLedgerObservation,
    OssIossLedgerObservation,
    RentaGastosEstimacionDirectaObservationProtocol,
    RentaGastosPagoFraccionadoObservationProtocol,
    RentaIncomeObservationProtocol,
    UngroundedRentaIncome,
    renta_first_slice_binding_target_casillas,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_oss_aggregation_binding_values,
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    structurally_unroutable_iva_base_categories,
    ungrounded_ledger_renta_income_observations,
    unrouted_ledger_iva_quantities,
    unrouted_ledger_renta_income_quantities,
    unsupported_ledger_iva_observations,
    unsupported_ledger_oss_observations,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
    unsupported_ledger_renta_income_observations,
    validate_ledger_iva_aggregation_binding,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding,
    validate_ledger_oss_aggregation_binding_definition,
    validate_ledger_renta_gastos_estimacion_directa_aggregation_binding,
    validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding,
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
    validate_ledger_renta_income_aggregation_binding,
    validate_ledger_renta_income_aggregation_binding_definition,
)
from ._ledger_bindings import (
    IvaLedgerSelector as _IvaLedgerSelector,
)
from ._ledger_bindings import (
    OssIossLedgerSelector as _OssIossLedgerSelector,
)
from ._ledger_bindings import (
    RentaLedgerGastosEstimacionDirectaSelector as _RentaLedgerGastosEstimacionDirectaSelector,
)
from ._ledger_bindings import (
    RentaLedgerGastosPagoFraccionadoSelector as _RentaLedgerGastosPagoFraccionadoSelector,
)
from ._ledger_bindings import (
    RentaLedgerIncomeSelector as _RentaLedgerIncomeSelector,
)
from ._ledger_impatriado_bindings import (
    ImpatriadoIncomeObservationProtocol,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    unsupported_ledger_impatriado_income_observations,
    validate_ledger_impatriado_income_aggregation_binding,
    validate_ledger_impatriado_income_aggregation_binding_definition,
)
from ._ledger_impatriado_bindings import (
    ImpatriadoLedgerIncomeSelector as _ImpatriadoLedgerIncomeSelector,
)
from ._period_selector_match import selector_period_matches_request
from ._retenciones_bindings import (
    RetencionesAggregationSelector as _RetencionesAggregationSelector,
)
from ._retenciones_bindings import (
    resolve_retenciones_aggregation_binding_values,
    validate_retenciones_aggregation_binding,
)
from ._schema import CasillaDefinition, DataBindingDefinition, InputKind, ModeloRevision
from ._withholding296_bindings import (
    Withholding296Observation,
    _Withholding296Selector,
    resolve_withholding296_binding_row_values,
    validate_withholding296_binding_selector_shape,
)
from ._withholding_bindings import (
    WithholdingClaveBreakdown,
    WithholdingObservation,
    WithholdingObservationRequirement,
    WithholdingTotalsParity,
    aggregate_withholding_by_clave,
    compute_withholding_totals_parity,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
    validate_withholding_binding_selector_shape,
    withholding_binding_requirements,
)
from ._withholding_bindings import (
    WithholdingSelector as _WithholdingSelector,
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
    "DonativoDonorObservation",
    "Gasto193Observation",
    "ImpatriadoIncomeObservationProtocol",
    "InventoryProjectionOperation",
    "InventorySelector",
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "IrnrIncomeObservationProtocol",
    "IvaCompensationAnnualPartitionRequirement",
    "IvaLedgerObservation",
    "M303RegimenSimplificadoAnnualSummaryRequirement",
    "Modelo349OperadorClaveTotal",
    "Modelo349OperadorTotalsParity",
    "Modelo720RowObservation",
    "OracleModeloObservation",
    "OssIossLedgerObservation",
    "ProfileSelector",
    "RefundOperationObservation",
    "RegistryModeloObservation",
    "RelatedPartyOperationObservation",
    "RentaGastosEstimacionDirectaObservationProtocol",
    "RentaGastosPagoFraccionadoObservationProtocol",
    "RentaIncomeObservationProtocol",
    "UngroundedRentaIncome",
    "UnroutedLedgerQuantity",
    "Withholding296Observation",
    "WithholdingClaveBreakdown",
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "WithholdingTotalsParity",
    "_build_foreign_asset_rows",
    "_build_related_party_rows",
    "aggregate_withholding_by_clave",
    "binding_aggregation_op",
    "binding_source_casilla_ids",
    "binding_source_modelo",
    "bound_casilla_binding_ids",
    "casillas_by_binding",
    "compute_modelo_349_operador_totals_parity",
    "compute_withholding_totals_parity",
    "counterpart_binding_requirements",
    "default_binding_aggregation_op",
    "foreign_asset_binding_row_field",
    "invoice_binding_requirements",
    "is_m347_declarante_summary_invoice_binding",
    "iva_compensation_annual_partition_requirement",
    "m303_regimen_simplificado_annual_summary_requirement",
    "previous_filing_binding_source_casilla_ids",
    "previous_filing_observation_requirements",
    "previous_filing_source_reference",
    "renta_first_slice_binding_target_casillas",
    "resolve_atribucion_binding_row_values",
    "resolve_available_bound_inputs_by_casilla_id",
    "resolve_bound_casilla_binding_value",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
    "resolve_donativo_binding_row_values",
    "resolve_foreign_asset_binding_row_values",
    "resolve_gasto193_binding_row_values",
    "resolve_gasto193_binding_values",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "resolve_ledger_impatriado_income_aggregation_binding_values",
    "resolve_ledger_irnr_income_aggregation_binding_values",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values",
    "resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "resolve_previous_filing_binding_values",
    "resolve_refund_binding_row_values",
    "resolve_related_party_binding_row_values",
    "resolve_retenciones_aggregation_binding_values",
    "resolve_withholding296_binding_row_values",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "selector_model_for_source",
    "structurally_unroutable_iva_base_categories",
    "ungrounded_ledger_renta_income_observations",
    "unrouted_ledger_iva_quantities",
    "unrouted_ledger_renta_income_quantities",
    "unsupported_ledger_impatriado_income_observations",
    "unsupported_ledger_irnr_income_observations",
    "unsupported_ledger_iva_observations",
    "unsupported_ledger_oss_observations",
    "unsupported_ledger_renta_gastos_estimacion_directa_observations",
    "unsupported_ledger_renta_gastos_pago_fraccionado_observations",
    "unsupported_ledger_renta_income_observations",
    "validate_invoice_binding_definition",
    "validate_ledger_impatriado_income_aggregation_binding_definition",
    "validate_ledger_irnr_income_aggregation_binding_definition",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition",
    "validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding_definition",
    "validate_m303_regimen_simplificado_annual_summary_revision",
    "validate_retenciones_aggregation_binding",
    "withholding_binding_requirements",
]

#: One per-family ``validate(binding) -> list[str]`` accumulating validator. Every
#: source family registers exactly one in :data:`_BINDING_VALIDATOR_REGISTRY`.
_BindingFamilyValidator = Callable[[DataBindingDefinition], list[str]]


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """Narrow an unparameterized runtime mapping to untrusted object entries."""
    return isinstance(value, Mapping)


def _tuple_from_json_array(value: object) -> object:
    if isinstance(value, list):
        return OBJECT_TUPLE_ADAPTER.validate_python(value)
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
        return tuple(_decimal_from_json_string(item) for item in OBJECT_TUPLE_ADAPTER.validate_python(value))
    return value


class CasillaObservation(BaseModel):
    """One typed casilla observation emitted by the formula runtime.

    Carries a :class:`~core.CasillaId`, final
    scalar value (numeric :class:`decimal.Decimal` or validated text), required
    legal/source provenance, and
    optional formula lineage. When ``formula_id`` is set, the runtime computed
    this casilla and ``operand_refs`` / ``operand_values`` trace its inputs
    while ``operand_casilla_refs`` carries the casilla-id-only projection; when
    ``formula_id`` is ``None`` the casilla was supplied as input (manual /
    bound) and the trace fields are empty.

    Used as the primary storage for
    :class:`~domain.calculations.registry.RegistryCalculationResult`;
    derived ``values`` and ``entries`` views project from it.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value_kind: Literal["decimal", "text"] = Field(default="decimal", exclude_if=lambda value: value == "decimal")
    value: Decimal | str
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
    # constructor rather than through a generic missing-input default.
    # Downstream audit and review surfaces should distinguish
    # absent-by-design zeros from value-bearing observations.
    absent_by_design: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def _value_from_json_string(cls, value: object, info: ValidationInfo) -> object:
        if info.data.get("value_kind", "decimal") == "decimal":
            return _decimal_from_json_string(value)
        return value

    @field_validator("value")
    @classmethod
    def _scalar_value(cls, value: Decimal | str) -> Decimal | str:
        return value

    @model_validator(mode="after")
    def _value_matches_kind(self) -> CasillaObservation:
        if self.value_kind == "decimal" and not isinstance(self.value, Decimal):
            raise RegistryValidationError("decimal casilla observation must carry a Decimal value")
        if self.value_kind == "text" and not isinstance(self.value, str):
            raise RegistryValidationError("text casilla observation must carry a string value")
        return self

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

    Storage is ``observations``: a typed tuple of
    :class:`~domain.calculations.registry.CasillaObservation` carrying full
    formula provenance. The :attr:`casilla_values` property provides a read-only
    mapping view for downstream consumers.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    #: A registry coordinate, not necessarily a period a taxpayer files in:
    #: a non-filing modelo such as the censal 036 is addressed by its event
    #: (alta, modificacion, baja) rather than by a calendar period. The
    #: span-capable ``filing_period`` above stays ``None`` for those.
    period: RegistryPeriodCode
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        if not _is_object_mapping(data) or "filing_period" in data:
            return data
        payload: dict[str, object] = {}
        for key, value in data.items():
            if not isinstance(key, str):
                return data
            payload[key] = value
        filing_year = payload.get("filing_year")
        period = payload.get("period")
        if not isinstance(filing_year, int) or not isinstance(period, str):
            return data
        try:
            filing_period = Period.from_year_and_code(filing_year, period)
        except ValueError:
            # An administrative coordinate has no calendar span, so a
            # non-filing modelo simply carries no filing_period. A token that
            # is not a registry period at all is still refused, by the field
            # validator that runs after this one.
            return data
        return {**payload, "filing_period": filing_period}

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
        if not selector_period_matches_request(self.period, self.filing_period.registry_token):
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
        return {obs.casilla_id: obs.value for obs in self.observations if isinstance(obs.value, Decimal)}


class OracleModeloObservation(RegistryModeloObservation):
    """Observed casilla values whose source is a live AEAT oracle adapter.

    A subtype of :class:`RegistryModeloObservation` that marks the observation
    tuple as oracle-originated rather than locally computed. The
    :class:`~domain.calculations.registry.OracleId` field anchors the
    observation to the
    ``LiveCrossReferenceDecision`` that produced it, so the application
    layer can route oracle-originated values through the
    cross-reference policy (synthetic-payload verification, replay
    quarantine, etc.) without ambiguity about provenance.

    Distinct from the parent only by the typed ``oracle_id`` field;
    every other invariant is inherited unchanged.
    """

    oracle_id: OracleId


def bound_casilla_binding_ids(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    """Return primary plus reviewed equivalent bindings for one bound casilla.

    The :class:`~domain.calculations.registry.CasillaDefinition` must be a
    bound casilla; the returned :class:`~domain.calculations.registry.BindingId`
    tuple drives bound-value resolution and equivalent-source conflict checks.
    """
    if casilla.input_kind != InputKind.BOUND:
        return ()
    if casilla.binding is None:
        raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
    return (casilla.binding, *casilla.alternate_bindings)


def casillas_by_binding(revision: ModeloRevision) -> Mapping[BindingId, tuple[CasillaId, ...]]:
    """Return each binding id mapped to the casillas that may populate it.

    The exact dual of :func:`bound_casilla_binding_ids`. That function answers
    "which bindings feed this casilla"; this one answers "which casillas does
    this binding feed". Both read the same predicate, so the two directions
    cannot disagree about which pairs exist.

    Every consequence is inherited from the forward primitive rather than
    decided again here: schema construction refuses a BOUND
    :class:`~domain.calculations.registry.CasillaDefinition` with no binding
    (and the forward primitive retains the same defensive refusal), while a
    non-BOUND casilla carrying a binding contributes nothing.
    Casilla ids keep the revision's declaration order and are de-duplicated, so
    a casilla naming one binding as both primary and alternate appears once.
    """
    mapping: dict[BindingId, list[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            populated_by = mapping.setdefault(binding_id, [])
            if casilla.id not in populated_by:
                populated_by.append(casilla.id)
    return {binding_id: tuple(casilla_ids) for binding_id, casilla_ids in mapping.items()}


def resolve_bound_casilla_binding_value(
    casilla: CasillaDefinition,
    facts: Mapping[BindingId, Decimal],
) -> tuple[Decimal | None, tuple[BindingId, ...]]:
    """Resolve equivalent binding facts for one casilla, rejecting disagreements.

    A bound :class:`~domain.calculations.registry.CasillaDefinition` can
    declare reviewed alternate bindings when multiple registry source paths
    represent the same factual amount. Supplying two equivalent source values is
    legal only if they agree exactly; otherwise accepting either one would
    silently over- or under-declare the downstream calculation.
    """
    binding_ids = bound_casilla_binding_ids(casilla)
    present = tuple((binding_id, facts[binding_id]) for binding_id in binding_ids if binding_id in facts)
    if not present:
        return None, ()
    first_value = present[0][1]
    disagreeing = tuple((binding_id, value) for binding_id, value in present if value != first_value)
    if disagreeing:
        values_by_binding = ", ".join(f"{binding_id!r}={value!r}" for binding_id, value in present)
        raise RegistryValidationError(
            f"bound casilla {casilla.id!r} received conflicting equivalent binding values: {values_by_binding}",
            context={
                "casilla_id": casilla.id,
                "binding_ids": ",".join(binding_id for binding_id, _value in present),
            },
        )
    return first_value, tuple(binding_id for binding_id, _value in present)


def resolve_available_bound_inputs_by_casilla_id(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project available binding values into input values keyed by bound ``casilla.id``.

    The :class:`ModeloRevision` supplies the
    bound casilla-to-binding mapping; only values already present in
    ``binding_values`` are projected. Missing optional bindings are skipped
    rather than treated as registry errors, which lets calculate paths combine
    partial source mesh output with caller overrides before the engine runs.

    Args:
        revision: The :class:`ModeloRevision`
            whose bound casillas are inspected.
        binding_values: Decimal values keyed by
            :class:`~domain.calculations.registry.BindingId`.

    Returns:
        A ``dict`` keyed by
        :class:`~cadrumo.core.CasillaId` for every bound
        casilla whose binding value is currently available.

    See Also:
        :func:`resolve_bound_casilla_binding_value`:
            Per-casilla primitive this projection folds over, including its
            refusal of disagreeing equivalent alternate bindings.
    """
    resolved: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        value, _binding_ids = resolve_bound_casilla_binding_value(casilla, binding_values)
        if value is not None:
            resolved[casilla.id] = value
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

    A relation-targeted slot binding always declares
    ``source = "relation_prefill"``, never ``previous_filing``.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
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


_IVA_COMPENSATION_ANNUAL_PARTITION_SOURCE_IDS: tuple[CasillaId, ...] = (
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_APLICADA_CASILLA,
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
)
_IVA_COMPENSATION_ANNUAL_PARTITION_PERIODS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_PRORRATA_REGULARIZACION_SOURCE_IDS: tuple[CasillaId, ...] = (
    "iva.cuota-deducible-total",
    "iva.prorrata-volumen-con-derecho",
    "iva.prorrata-volumen-total",
    "iva.prorrata-porcentaje",
)
_PRORRATA_REGULARIZACION_SOURCE_PERIODS: tuple[str, ...] = ("1T", "2T", "3T", "4T")


class _BienesInversionRegularizacionSelector(BaseModel):
    """Selector for capital-goods regularisation filing targets."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: Literal["303"]
    regularizacion_output: Literal["modelo_303_casilla_43", "modelo_390_casilla_63"]


class _IvaCompensationAnnualPartitionSelector(BaseModel):
    """Selector for Modelo 390 AEAT boxes 97 / 662 as one FIFO partition."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: Literal["303"]
    source_casilla_ids: tuple[CasillaId, ...]
    source_periods: tuple[str, ...]
    partition_output: Literal["last_period_amount", "generated_not_in_last_amount"]

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_match_fifo_state(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if value != _IVA_COMPENSATION_ANNUAL_PARTITION_SOURCE_IDS:
            raise RegistryValidationError(
                "iva_compensation_annual_partition selector must declare the current Modelo 303 "
                "compensation state casilla ids in canonical order",
            )
        return value

    @field_validator("source_periods")
    @classmethod
    def _source_periods_are_full_year(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != _IVA_COMPENSATION_ANNUAL_PARTITION_PERIODS:
            raise RegistryValidationError(
                "iva_compensation_annual_partition selector must declare source_periods ('1T', '2T', '3T', '4T')",
            )
        return value


class IvaCompensationAnnualPartitionRequirement(BaseModel):
    """One typed annual Modelo 303 compensation-partition projection.

    The annual partition is a distinct FIFO resolution family, rather than a
    relation fold. Its bindings nevertheless share one source fact: four
    Modelo 303 state observations and the target revision's declared treatment
    of that source. This projection is the only interpretation of the binding
    selectors consumers may use; it retains each target slot and the complete
    source/provenance contract without exposing raw selector mappings.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    source_periods: tuple[str, ...] = Field(min_length=1)
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    last_period_amount_binding_id: BindingId | None = None
    generated_not_in_last_amount_binding_id: BindingId | None = None
    dependency_treatment: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


def _iva_compensation_annual_partition_selector(
    binding: DataBindingDefinition,
) -> _IvaCompensationAnnualPartitionSelector:
    try:
        return _IvaCompensationAnnualPartitionSelector.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed iva_compensation_annual_partition selector: {exc}",
        ) from exc


def iva_compensation_annual_partition_requirement(
    revision: ModeloRevision,
) -> IvaCompensationAnnualPartitionRequirement | None:
    """Project the revision's annual compensation-partition bindings once.

    Returns ``None`` when the revision declares no partition bindings. When it
    does, every binding must name the same typed source selector and each of
    the two partition outputs may be targeted at most once. The source's
    dependency treatment comes directly from the revision classification and
    stays empty only when that classification is absent; consumers must not
    reconstruct or default it.
    """
    bindings = _iva_compensation_annual_partition_bindings(revision)
    if not bindings:
        return None

    first_selector = _iva_compensation_annual_partition_selector(bindings[0])
    (
        last_period_amount_binding_id,
        generated_not_in_last_amount_binding_id,
        legal_refs,
        source_refs,
    ) = _collect_iva_compensation_partition_bindings(bindings, first_selector)
    return IvaCompensationAnnualPartitionRequirement(
        source_modelo=first_selector.source_modelo,
        source_periods=first_selector.source_periods,
        source_casilla_ids=first_selector.source_casilla_ids,
        binding_ids=tuple(sorted(binding.id for binding in bindings)),
        last_period_amount_binding_id=last_period_amount_binding_id,
        generated_not_in_last_amount_binding_id=generated_not_in_last_amount_binding_id,
        dependency_treatment=_iva_compensation_dependency_treatment(revision, first_selector.source_modelo),
        legal_refs=tuple(sorted(legal_refs)),
        source_refs=tuple(sorted(source_refs)),
    )


def _iva_compensation_annual_partition_bindings(
    revision: ModeloRevision,
) -> tuple[DataBindingDefinition, ...]:
    """Collect the annual compensation-partition bindings in revision order."""
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source == BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    )


def _collect_iva_compensation_partition_bindings(
    bindings: tuple[DataBindingDefinition, ...],
    first_selector: _IvaCompensationAnnualPartitionSelector,
) -> tuple[
    BindingId | None,
    BindingId | None,
    set[LegalRefId],
    set[SourceRefId],
]:
    """Validate shared selectors and collect target ids plus provenance refs."""
    last_period_amount_binding_id: BindingId | None = None
    generated_not_in_last_amount_binding_id: BindingId | None = None
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = _iva_compensation_annual_partition_selector(binding)
        _require_shared_iva_compensation_selector(selector, first_selector)
        if selector.partition_output == "last_period_amount":
            last_period_amount_binding_id = _unique_partition_binding_id(
                last_period_amount_binding_id,
                binding.id,
                "last_period_amount",
            )
        else:
            generated_not_in_last_amount_binding_id = _unique_partition_binding_id(
                generated_not_in_last_amount_binding_id,
                binding.id,
                "generated_not_in_last_amount",
            )
        legal_refs.update(binding.legal_refs)
        source_refs.update(binding.source_refs)
    return last_period_amount_binding_id, generated_not_in_last_amount_binding_id, legal_refs, source_refs


def _require_shared_iva_compensation_selector(
    selector: _IvaCompensationAnnualPartitionSelector,
    first_selector: _IvaCompensationAnnualPartitionSelector,
) -> None:
    """Require every annual partition binding to use one source selector."""
    if (
        selector.source_modelo != first_selector.source_modelo
        or selector.source_casilla_ids != first_selector.source_casilla_ids
        or selector.source_periods != first_selector.source_periods
    ):
        raise RegistryValidationError(
            "iva_compensation_annual_partition bindings must share one source selector",
        )


def _unique_partition_binding_id(
    existing: BindingId | None,
    binding_id: BindingId,
    output: Literal["last_period_amount", "generated_not_in_last_amount"],
) -> BindingId:
    """Return one partition target id, refusing duplicate target declarations."""
    if existing is not None:
        raise RegistryValidationError(
            f"iva_compensation_annual_partition declares multiple {output} bindings",
        )
    return binding_id


def _iva_compensation_dependency_treatment(revision: ModeloRevision, source_modelo: ModeloId) -> str:
    """Read the revision-owned dependency treatment for the partition source."""
    classification = next(
        (candidate for candidate in revision.dependency_classifications if candidate.source_modelo == source_modelo),
        None,
    )
    return "" if classification is None else str(classification.treatment)


_M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_SOURCE_IDS: tuple[CasillaId, ...] = (
    "51",
    "53",
    "52",
    "54",
    "55",
    "56",
    "57",
    "58",
)


class _M303RegimenSimplificadoAnnualSummarySelector(BaseModel):
    """Strict selector for one immutable Modelo 303 4T annual-summary endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: Literal["303"]
    source_period: Literal["4T"]
    source_casilla_ids: tuple[CasillaId, ...]
    summary_casilla_id: CasillaId

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_are_exact_annual_summary_inputs(
        cls,
        value: tuple[CasillaId, ...],
    ) -> tuple[CasillaId, ...]:
        if value != _M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_SOURCE_IDS:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary selector must declare Modelo 303 "
                "casillas 51, 53, 52, 54, 55, 56, 57, 58 in official semantic order",
            )
        return value


class M303RegimenSimplificadoAnnualSummaryRequirement(BaseModel):
    """Revision-owned target map for the one persisted 303 4T handoff.

    This model is the registry's only interpretation of the ten endpoint
    selectors.  The application assembler validates the result against the
    canonical handoff carrier; it does not read raw binding selector mappings.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    source_period: FilingPeriodCode
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId] = Field(min_length=1)
    dependency_treatment: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @field_validator("binding_ids_by_summary_casilla_id")
    @classmethod
    def _freeze_endpoint_bindings(
        cls,
        value: Mapping[CasillaId, BindingId],
    ) -> Mapping[CasillaId, BindingId]:
        return dict(sorted(value.items()))


def _m303_regimen_simplificado_annual_summary_selector(
    binding: DataBindingDefinition,
) -> _M303RegimenSimplificadoAnnualSummarySelector:
    try:
        return _M303RegimenSimplificadoAnnualSummarySelector.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed m303_regimen_simplificado_annual_summary selector: {exc}",
        ) from exc


def _m303_regimen_simplificado_annual_summary_bindings(
    revision: ModeloRevision,
) -> tuple[DataBindingDefinition, ...]:
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )


def _collect_m303_regimen_simplificado_annual_summary_bindings(
    bindings: tuple[DataBindingDefinition, ...],
    first_selector: _M303RegimenSimplificadoAnnualSummarySelector,
) -> tuple[dict[CasillaId, BindingId], set[LegalRefId], set[SourceRefId]]:
    binding_ids_by_summary_casilla_id: dict[CasillaId, BindingId] = {}
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = _m303_regimen_simplificado_annual_summary_selector(binding)
        if (
            selector.source_modelo != first_selector.source_modelo
            or selector.source_period != first_selector.source_period
            or selector.source_casilla_ids != first_selector.source_casilla_ids
        ):
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary bindings must share one exact source selector",
            )
        existing = binding_ids_by_summary_casilla_id.get(selector.summary_casilla_id)
        if existing is not None:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary declares multiple bindings for "
                f"summary casilla {selector.summary_casilla_id!r}: {existing!r}, {binding.id!r}",
            )
        binding_ids_by_summary_casilla_id[selector.summary_casilla_id] = binding.id
        legal_refs.update(binding.legal_refs)
        source_refs.update(binding.source_refs)
    return binding_ids_by_summary_casilla_id, legal_refs, source_refs


def _m303_regimen_simplificado_annual_summary_dependency_treatment(
    revision: ModeloRevision,
    source_modelo: ModeloId,
) -> str:
    classification = next(
        (candidate for candidate in revision.dependency_classifications if candidate.source_modelo == source_modelo),
        None,
    )
    return "" if classification is None else str(classification.treatment)


def m303_regimen_simplificado_annual_summary_requirement(
    revision: ModeloRevision,
) -> M303RegimenSimplificadoAnnualSummaryRequirement | None:
    """Project the revision's typed Modelo 303 4T annual-summary bindings once."""
    bindings = _m303_regimen_simplificado_annual_summary_bindings(revision)
    if not bindings:
        return None
    first_selector = _m303_regimen_simplificado_annual_summary_selector(bindings[0])
    binding_ids_by_summary_casilla_id, legal_refs, source_refs = (
        _collect_m303_regimen_simplificado_annual_summary_bindings(bindings, first_selector)
    )
    return M303RegimenSimplificadoAnnualSummaryRequirement(
        source_modelo=first_selector.source_modelo,
        source_period=first_selector.source_period,
        source_casilla_ids=first_selector.source_casilla_ids,
        binding_ids_by_summary_casilla_id=binding_ids_by_summary_casilla_id,
        dependency_treatment=_m303_regimen_simplificado_annual_summary_dependency_treatment(
            revision,
            first_selector.source_modelo,
        ),
        legal_refs=tuple(sorted(legal_refs)),
        source_refs=tuple(sorted(source_refs)),
    )


def validate_m303_regimen_simplificado_annual_summary_revision(
    revision: ModeloRevision,
) -> list[str]:
    """Return build-time failures for the complete 303/4T -> 390/0A target map.

    Selector shape is already validated per binding.  This revision-level gate
    owns the complementary invariant: a declared handoff family has precisely
    the canonical ten endpoints, and every endpoint is one bound casilla fed
    only by its corresponding handoff binding.  The lazy import avoids making
    the calculation-revision carrier a registry import-time dependency.
    """
    try:
        requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    except RegistryValidationError as exc:
        return [str(exc)]
    if requirement is None:
        return []

    from ...modelos import M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS

    expected_casilla_ids = M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
    expected_set = set(expected_casilla_ids)
    declared_set = set(requirement.binding_ids_by_summary_casilla_id)
    failures = _m303_regimen_simplificado_annual_summary_target_failures(expected_set, declared_set)
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    failures.extend(
        _m303_regimen_simplificado_annual_summary_endpoint_failures(
            expected_casilla_ids,
            requirement.binding_ids_by_summary_casilla_id,
            casillas_by_id,
        )
    )
    return failures


def _m303_regimen_simplificado_annual_summary_target_failures(
    expected_set: set[CasillaId],
    declared_set: set[CasillaId],
) -> list[str]:
    if declared_set == expected_set:
        return []
    return [
        "m303_regimen_simplificado_annual_summary bindings must target exactly "
        f"the canonical Modelo 390 74-83 endpoints; missing={sorted(expected_set - declared_set)!r}, "
        f"unexpected={sorted(declared_set - expected_set)!r}",
    ]


def _m303_regimen_simplificado_annual_summary_endpoint_failures(
    expected_casilla_ids: tuple[CasillaId, ...],
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    failures: list[str] = []
    for ordinal, casilla_id in enumerate(expected_casilla_ids, start=74):
        casilla = casillas_by_id.get(casilla_id)
        binding_id = binding_ids_by_summary_casilla_id.get(casilla_id)
        if casilla is None:
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} is not declared as Modelo 390 casilla {ordinal}",
            )
            continue
        if casilla.number != str(ordinal):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must retain official Modelo 390 casilla number {ordinal}",
            )
        if binding_id is not None and (
            casilla.input_kind is not InputKind.BOUND or bound_casilla_binding_ids(casilla) != (binding_id,)
        ):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must be bound only by {binding_id!r}",
            )
    return failures


class _ProrrataRegularizacionSelector(BaseModel):
    """Selector for annual prorrata regularisation filing targets."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: Literal["303"]
    source_casilla_ids: tuple[CasillaId, ...]
    source_periods: tuple[str, ...]
    regularizacion_output: Literal["modelo_303_casilla_44", "modelo_390_regularizacion_anual"]

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_match_prorrata_inputs(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if value != _PRORRATA_REGULARIZACION_SOURCE_IDS:
            raise RegistryValidationError(
                "prorrata_regularizacion selector must declare the Modelo 303 deductible-total, "
                "annual prorrata volume, and definitive-percentage casilla ids in canonical order",
            )
        return value

    @field_validator("source_periods")
    @classmethod
    def _source_periods_are_full_year(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != _PRORRATA_REGULARIZACION_SOURCE_PERIODS:
            raise RegistryValidationError(
                "prorrata_regularizacion selector must declare source_periods ('1T', '2T', '3T', '4T')",
            )
        return value


def binding_source_casilla_ids(binding: DataBindingDefinition) -> tuple[CasillaId, ...]:
    """Return typed source casilla ids declared by binding families that have them."""
    if binding.source == BindingSourceKind.PREVIOUS_FILING:
        return previous_filing_source_reference(binding).source_casilla_ids
    if binding.source == BindingSourceKind.RELATION_PREFILL:
        return _relation_prefill_source_ids(_relation_prefill_selector(binding))
    if binding.source == BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION:
        return _iva_compensation_annual_partition_selector(binding).source_casilla_ids
    if binding.source == BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY:
        return _m303_regimen_simplificado_annual_summary_selector(binding).source_casilla_ids
    if binding.source == BindingSourceKind.PRORRATA_REGULARIZACION:
        return _ProrrataRegularizacionSelector.model_validate(selector_as_dict(binding)).source_casilla_ids
    if binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION:
        _BienesInversionRegularizacionSelector.model_validate(selector_as_dict(binding))
        return ()
    return ()


def binding_source_modelo(binding: DataBindingDefinition) -> ModeloId | None:
    """Return the typed source modelo declared by binding families that have one."""
    if binding.source == BindingSourceKind.PREVIOUS_FILING:
        return previous_filing_source_reference(binding).source_modelo
    if binding.source == BindingSourceKind.RELATION_PREFILL:
        return _relation_prefill_selector(binding).source_modelo
    if binding.source == BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION:
        return _iva_compensation_annual_partition_selector(binding).source_modelo
    if binding.source == BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY:
        return _m303_regimen_simplificado_annual_summary_selector(binding).source_modelo
    if binding.source == BindingSourceKind.PRORRATA_REGULARIZACION:
        return _ProrrataRegularizacionSelector.model_validate(selector_as_dict(binding)).source_modelo
    if binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION:
        return _BienesInversionRegularizacionSelector.model_validate(selector_as_dict(binding)).source_modelo
    return None


class ProfileSelector(BaseModel):
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
    # Conditional applicability
    required_when_profile_key: str | None = Field(default=None, min_length=1, max_length=128)
    required_when_value: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _validate_profile_shape(self) -> ProfileSelector:
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
:func:`domain.calculations.registry._validate_record_sections._is_layout_binding`.
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
    # implicit-decimal scale of a record-field slot, declared per the diseno de
    # registro because the width alone does not imply it
    decimals: int | None = Field(default=None, ge=0)
    # Whether the record-field slot carries AEAT's sign marker in position 1,
    # declared per the diseno de registro: a row AEAT types ``N`` reserves that
    # byte and a row typed ``Num`` does not, and the width alone cannot say
    # which. Only meaningful for the record-field shape.
    signed: bool | None = None
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
        if self.signed is not None:
            # The sign marker is a byte of the fixed-width slot, so it is only
            # meaningful where the selector names one.
            if has_casilla:
                raise RegistryValidationError(
                    "manual_input casilla-shape selector cannot declare signed: the sign marker is a "
                    "byte of a fixed-width record slot, which the casilla shape does not name",
                )
            if self.signed and self.data_type != "money":
                raise RegistryValidationError(
                    f"manual_input record-field selector can declare signed only for money data, "
                    f"not {self.data_type!r}",
                )
        return self


# ---------------------------------------------------------------------------
# Discriminated-selector registry
#
# Each entry pairs a registry-declared ``DataBindingDefinition.source`` literal
# with the strict pydantic model that the binding's selector must validate
# against. Mesh-only ``BindingSourceKind`` members stay absent because they are
# not legal registry binding sources.
# ---------------------------------------------------------------------------


_BINDING_SELECTOR_REGISTRY: dict[BindingSourceKind, type[BaseModel]] = {
    BindingSourceKind.PREVIOUS_FILING: PreviousModeloSelector,
    BindingSourceKind.RELATION_PREFILL: _RelationPrefillSelector,
    BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION: _IvaCompensationAnnualPartitionSelector,
    BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY: _M303RegimenSimplificadoAnnualSummarySelector,
    BindingSourceKind.PRORRATA_REGULARIZACION: _ProrrataRegularizacionSelector,
    BindingSourceKind.BIENES_INVERSION_REGULARIZACION: _BienesInversionRegularizacionSelector,
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
    BindingSourceKind.LEDGER_OSS_AGGREGATION: _OssIossLedgerSelector,
    BindingSourceKind.LEDGER_IVA_AGGREGATION: _IvaLedgerSelector,
    BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: _RentaLedgerGastosEstimacionDirectaSelector,
    BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION: _RentaLedgerIncomeSelector,
    BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION: _RentaLedgerGastosPagoFraccionadoSelector,
    BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION: _ImpatriadoLedgerIncomeSelector,
    BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION: _IrnrLedgerIncomeSelector,
    BindingSourceKind.RETENCIONES_AGGREGATION: _RetencionesAggregationSelector,
    BindingSourceKind.WITHHOLDING: _WithholdingSelector,
    BindingSourceKind.RELATED_PARTY_OPERATION: _RelatedPartySelector,
    BindingSourceKind.FOREIGN_ASSET: _ForeignAssetSelector,
    BindingSourceKind.ATRIBUCION_MEMBER: _AtributionSelector,
    BindingSourceKind.REFUND_OPERATION: _RefundSelector,
    BindingSourceKind.DONATIVO_DONOR: _DonativoSelector,
    BindingSourceKind.GASTO193_CONTRIBUTOR: _Gasto193Selector,
    BindingSourceKind.WITHHOLDING296: _Withholding296Selector,
    BindingSourceKind.INVENTORY: InventorySelector,
    BindingSourceKind.MANUAL_INPUT: _ManualInputSelector,
    BindingSourceKind.PROFILE: ProfileSelector,
}


def selector_model_for_source(source: object) -> type[BaseModel] | None:
    """Return the strict selector model a binding ``source`` validates against.

    Read-only accessor over :data:`_BINDING_SELECTOR_REGISTRY`, the
    discriminated-union table keyed by :class:`~core.BindingSourceKind`
    (the canonical ``DataBindingDefinition.source`` axis). Returns the
    per-family selector model when the source is a registry-declared binding
    source, or ``None`` for mesh-only source kinds that are not legal
    ``DataBindingDefinition.source`` values.

    The model-level selector validator on
    :class:`~domain.calculations.registry.DataBindingDefinition` consumes
    this accessor to promote selector-shape typing to model-construction time
    without re-deriving the table; the op/fact cross-invariants stay owned by
    :func:`validate_binding_selector_shape` at snapshot build.
    """
    if not isinstance(source, BindingSourceKind):
        return None
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
# (preserving the underlying pydantic field error) and runs that family's
# op/fact invariants, whose raise-style bodies it reaches through
# ``invariant_diagnostics``. Those bodies have no other caller, so a family's
# op/fact invariants are enforced at registry-build time only; the resolvers
# re-parse their selectors independently through their own private selector
# helpers, which raise on a malformed selector but re-check no op/fact
# invariant.
# ---------------------------------------------------------------------------


_BINDING_VALIDATOR_REGISTRY: dict[BindingSourceKind, _BindingFamilyValidator] = {
    BindingSourceKind.PREVIOUS_FILING: validate_previous_filing_binding,
    BindingSourceKind.RELATION_PREFILL: _validate_selector_only(_RelationPrefillSelector),
    BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION: _validate_selector_only(
        _IvaCompensationAnnualPartitionSelector,
    ),
    BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY: _validate_selector_only(
        _M303RegimenSimplificadoAnnualSummarySelector,
    ),
    BindingSourceKind.PRORRATA_REGULARIZACION: _validate_selector_only(_ProrrataRegularizacionSelector),
    BindingSourceKind.BIENES_INVERSION_REGULARIZACION: _validate_selector_only(
        _BienesInversionRegularizacionSelector,
    ),
    # The three invoice-shaped sources run the stricter invoice validator (the
    # union of the prior dual path: selector-shape + counterpart fact/op
    # invariants + the two invoice-only scalar-shape guards). ledger_transaction
    # is a counterpart-only source (never an invoice source) and keeps the
    # counterpart validator.
    BindingSourceKind.LEDGER_TRANSACTION: validate_counterpart_binding,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: validate_invoice_binding,
    BindingSourceKind.PAYABLE_INVOICE: validate_invoice_binding,
    BindingSourceKind.COLLECTIBLE_INVOICE: validate_invoice_binding,
    BindingSourceKind.LEDGER_OSS_AGGREGATION: validate_ledger_oss_aggregation_binding,
    BindingSourceKind.LEDGER_IVA_AGGREGATION: validate_ledger_iva_aggregation_binding,
    BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding
    ),
    BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION: validate_ledger_renta_income_aggregation_binding,
    BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION: (
        validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding
    ),
    BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION: validate_ledger_impatriado_income_aggregation_binding,
    BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION: validate_ledger_irnr_income_aggregation_binding,
    BindingSourceKind.RETENCIONES_AGGREGATION: validate_retenciones_aggregation_binding,
    BindingSourceKind.RELATED_PARTY_OPERATION: validate_related_party_binding,
    BindingSourceKind.FOREIGN_ASSET: validate_foreign_asset_binding,
    BindingSourceKind.ATRIBUCION_MEMBER: validate_atribucion_binding,
    BindingSourceKind.REFUND_OPERATION: validate_refund_binding,
    BindingSourceKind.DONATIVO_DONOR: validate_donativo_binding,
    BindingSourceKind.GASTO193_CONTRIBUTOR: validate_gasto193_binding_selector_shape,
    BindingSourceKind.WITHHOLDING296: validate_withholding296_binding_selector_shape,
    BindingSourceKind.WITHHOLDING: validate_withholding_binding_selector_shape,
    BindingSourceKind.INVENTORY: validate_inventory_binding,
    BindingSourceKind.MANUAL_INPUT: _validate_selector_only(_ManualInputSelector),
    BindingSourceKind.PROFILE: _validate_selector_only(ProfileSelector),
}


def validate_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate a binding against its source family's single build-time validator.

    Routes the binding through the one per-family ``validate(binding) ->
    list[str]`` validator registered in :data:`_BINDING_VALIDATOR_REGISTRY`,
    keyed by :class:`~core.BindingSourceKind`. Each family validator
    validates the selector shape (projected through :func:`_selector_as_dict`
    inside :func:`selector_against_model`, so the gate sees the SAME normalised
    mapping the resolve-time helpers see and is never stricter than runtime) and
    lifts that family's op/fact cross-invariants to build time. Failures are
    accumulated as diagnostic strings rather than raised, preserving the
    underlying pydantic field error, so the snapshot-build gate can collect every
    failure across a revision in one pass.

    For every family — including the five detail-record families
    (``related_party_operation``, ``foreign_asset``, ``atribucion_member``,
    ``refund_operation``, ``donativo_donor``) and ``previous_filing`` whose
    op/fact invariants previously ran only at resolve time — a malformed
    binding is now rejected at snapshot build rather than only when a
    taxpayer calculation invokes the resolver.

    Sources not in the dispatch table are mesh-only and should not appear on a
    registry binding; construction rejects them before this build-time validator
    runs.
    """
    validator = _BINDING_VALIDATOR_REGISTRY.get(binding.source)
    if validator is None:
        return []
    return validator(binding)

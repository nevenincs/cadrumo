"""Projection and year-comparison services for modelo calculations.

The Modelo 100 projection path reads persisted :class:`CalculationRevision`
rows from quarterly Modelo 130 work units, resolves the annual
:class:`RegistrySnapshot`, injects the latest cumulative Modelo 130 income at
the annual Renta input leaf, threads pagos fraccionados through the relation
channel, overlays decimal, enum, and date profile facts from
:func:`resolve_profile_sourced_bindings`, and runs
:func:`calculate_registry_snapshot` without persisting the synthetic result.

The comparison path selects the best draft or verified
:class:`CalculationRevision` for each requested year, grounds each delta row in
the compared registry snapshots, and returns either a
:class:`ModeloProjectServiceResult` or :class:`ModeloCompareServiceResult`.

Core types:
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from ._registry_helpers import validate_casilla_input_ids
from .calculate_input_validation import (
    ModeloCalculateBindingInputError,
    decimal_binding_value,
    validated_binding_input_channel,
)
from .calculation_action_ports import CalculationActionPorts
from .calculation_revision_queries import list_calculation_revisions
from .profile_binding import resolve_profile_sourced_bindings
from .work_lifecycle import list_work_units

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_LOG = get_logger(__name__)
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_RELATION_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(RelationId)


class ModeloProjectionError(CadrumoError):
    """Base class for application-level projection failures."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Initialize the error, falling back to the translated message or class name."""
        super().__init__(
            message or translated_message or self.__class__.__name__,
            context=dict(context or {}),
            translated_message=translated_message,
        )


class ModeloProjectNoM130UnitsError(ModeloProjectionError):
    """Raised when a year-end projection has no quarterly Modelo 130 work units."""


class ModeloProjectNoM130RevisionsError(ModeloProjectionError):
    """Raised when Modelo 130 work units exist but have no calculation revisions."""


class ModeloProjectInvalidDecimalOverrideError(ModeloProjectionError):
    """Raised when a projection override cannot be parsed as a decimal."""


class ModeloCompareNeedTwoYearsError(ModeloProjectionError):
    """Raised when comparison is not addressed to exactly two filing years."""


class ModeloCompareNoWorkUnitsError(ModeloProjectionError):
    """Raised when comparison finds no work units for a filing year."""


class ModeloCompareNoRevisionsError(ModeloProjectionError):
    """Raised when comparison finds work units but no calculation revisions."""


class ModeloCompareNoUsableRevisionsError(ModeloProjectionError):
    """Raised when comparison finds no verified or draft revisions."""


def _required_casilla_value(
    values: Mapping[CasillaId, Decimal],
    casilla_id: CasillaId,
    *,
    source: str,
) -> Decimal:
    try:
        return values[casilla_id]
    except KeyError as exc:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={"source": source, "casilla_id": casilla_id, "casilla_produced": False},
        ) from exc


class ModeloProjectionCasillaObservation(BaseModel):
    """One computed casilla emitted by a projection service."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: Decimal
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class ModeloProjectM130Accumulated(BaseModel):
    """Accumulated Modelo 130 source values for a Modelo 100 projection."""

    model_config = _STRICT_FROZEN

    ingresos: Decimal
    gastos: Decimal
    rendimiento_neto: Decimal
    pagos_fraccionados: Decimal


class ModeloProjectM100Projection(BaseModel):
    """Projected Modelo 100 output values."""

    model_config = _STRICT_FROZEN

    base_liquidable_general: Decimal
    pagos_fraccionados: Decimal
    cuota_integra_estatal: Decimal
    cuota_integra_autonomica: Decimal
    cuota_liquida_estatal: Decimal
    cuota_liquida_autonomica: Decimal
    cuota_resultante: Decimal


class ModeloProjectServiceResult(BaseModel):
    """Year-end Modelo 100 projection from quarterly Modelo 130 revisions."""

    model_config = _STRICT_FROZEN

    year: int
    ccaa: str = Field(min_length=1)
    quarters_filed: int = Field(ge=1, le=4)
    quarters_available: tuple[str, ...]
    is_extrapolated: bool
    m130_accumulated: ModeloProjectM130Accumulated
    casilla_observations: tuple[ModeloProjectionCasillaObservation, ...]
    m100_projection: ModeloProjectM100Projection


class ModeloCompareDeltaRow(BaseModel):
    """One casilla delta row in a modelo year comparison."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    label: str
    section: str
    year_a_value: Decimal
    year_b_value: Decimal
    delta: Decimal
    pct_change: Decimal | None
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class ModeloCompareSection(BaseModel):
    """One section grouping for a modelo comparison."""

    model_config = _STRICT_FROZEN

    section: str
    rows: tuple[ModeloCompareDeltaRow, ...]


class ModeloCompareServiceResult(BaseModel):
    """Year-over-year comparison result for one modelo."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    year_a: int
    year_b: int
    year_a_revision_id: RevisionId
    year_b_revision_id: RevisionId
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: tuple[ModeloCompareSection, ...]
    delta_rows: tuple[ModeloCompareDeltaRow, ...]


def _compare_row_provenance(
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    casilla_id: CasillaId,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
    observation: CasillaObservation | None,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    cdef = casilla_meta.get(casilla_id)
    if cdef is None:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={
                "modelo": modelo,
                "year_a": year_a,
                "year_b": year_b,
                "casilla_id": casilla_id,
            },
        )
    formula_id = observation.formula_id if observation is not None else None
    if formula_id is None and cdef.formula is not None:
        formula_id = cdef.formula
    legal_refs = observation.legal_refs if observation is not None else tuple(cdef.legal_refs)
    source_refs = observation.source_refs if observation is not None else tuple(cdef.source_refs)
    if not legal_refs or not source_refs:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={
                "modelo": modelo,
                "year_a": year_a,
                "year_b": year_b,
                "casilla_id": casilla_id,
            },
        )
    return formula_id, legal_refs, source_refs


def _decimal_overrides(
    raw: Mapping[CasillaId, str],
    *,
    translated_message: str,
) -> dict[CasillaId, Decimal]:
    """Validate operator-supplied ``--casilla`` overrides against the canonical grammar.

    Mirrors :func:`cadrumo.application.modelo.calculate_input_validation.decimal`: the
    fractional part is deliberately uncapped, because a casilla value may
    legitimately carry sub-cent precision that the AEAT fixed-width encoder
    rounds to cents with ``ROUND_HALF_UP`` per the AEAT Instrucciones, so a
    two-digit cap here would refuse a figure the export layer exists to accept.
    What the grammar refuses is text whose numeric meaning is not what it
    appears: scientific notation, a leading ``+``, a comma decimal separator,
    embedded whitespace, and ``NaN``/``Infinity`` — the last of which compares
    ``False`` to every threshold, so a projection advisory keyed on ``> 0`` would
    never fire for it.
    """
    values: dict[CasillaId, Decimal] = {}
    for key, value in raw.items():
        parsed = try_parse_canonical_decimal(value)
        if parsed is None:
            raise ModeloProjectInvalidDecimalOverrideError(
                context={"key": key, "value": value},
                translated_message=translated_message,
            )
        values[key] = parsed
    return values


def _binding_id(value: object, *, surface: str) -> BindingId:
    try:
        return _BINDING_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"{surface} must be a canonical binding id: {value!r}") from exc


def _relation_id(value: object, *, surface: str) -> RelationId:
    try:
        return _RELATION_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"{surface} must be a canonical relation id: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class _ProjectionDeclaration:
    """The modelos, period and boxes the dated cross-model projection fact declares."""

    source_modelo: str
    target_modelo: str
    target_period: str
    ingresos: CasillaId
    gastos: CasillaId
    rendimiento_neto: CasillaId
    resultado_final: CasillaId
    rendimiento_neto_projected: CasillaId
    base_liquidable_general: CasillaId
    cuota_integra_estatal: CasillaId
    cuota_integra_autonomica: CasillaId
    cuota_liquida_estatal: CasillaId
    cuota_liquida_autonomica: CasillaId
    cuota_resultante: CasillaId
    pagos_fraccionados: CasillaId


def _registry_projection_declaration(year: int, *, operation: PinnedAuthorityOperation) -> _ProjectionDeclaration:
    """Resolve the dated cross-model projection declaration from the registry."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-100-m130-projection-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(year, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected projection declaration must resolve as a mapping fact")
    return _projection_declaration_from(resolved)


def _projection_declaration_from(resolved: ResolvedMappingFact) -> _ProjectionDeclaration:
    """Read the declared entries, refusing a mapping that omits one."""
    entries = {entry.key: str(entry.value) for entry in resolved.payload.entries}

    def declared(key: str) -> str:
        try:
            return entries[key]
        except KeyError as exc:
            raise RegistryValidationError(f"projection mapping is missing {key!r}") from exc

    def box(key: str) -> CasillaId:
        return validated_casilla_id(declared(key), surface=f"projection mapping {key}")

    return _ProjectionDeclaration(
        source_modelo=declared("source.modelo"),
        target_modelo=declared("target.modelo"),
        target_period=declared("period.default"),
        ingresos=box("source.casilla.ingresos"),
        gastos=box("source.casilla.gastos"),
        rendimiento_neto=box("source.casilla.rendimiento_neto"),
        resultado_final=box("source.casilla.resultado_final"),
        rendimiento_neto_projected=box("target.casilla.rendimiento_neto_projected"),
        base_liquidable_general=box("target.casilla.base_liquidable_general"),
        cuota_integra_estatal=box("target.casilla.cuota_integra_estatal"),
        cuota_integra_autonomica=box("target.casilla.cuota_integra_autonomica"),
        cuota_liquida_estatal=box("target.casilla.cuota_liquida_estatal"),
        cuota_liquida_autonomica=box("target.casilla.cuota_liquida_autonomica"),
        cuota_resultante=box("target.casilla.cuota_resultante"),
        pagos_fraccionados=box("target.casilla.pagos_fraccionados"),
    )


def _source_quarter_count(
    declaration: _ProjectionDeclaration,
    *,
    year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> int:
    """Return how many periods the selected source revision serves in ``year``."""
    revision = operation.revision_for_context(
        declaration.source_modelo,
        filing_year=year,
        period=period.registry_token,
    )
    return len(revision.period_selector.periods_for_year(year))


def _m130_quarter_revisions(
    year: int,
    *,
    declaration: _ProjectionDeclaration,
    ports: CalculationActionPorts,
) -> dict[Period, CalculationRevision]:
    """Read the latest persisted draft revision for each filed M130 quarter."""
    all_units = list_work_units(ports=ports.work_lifecycle_ports)
    m130_units = [
        unit
        for unit in all_units
        if str(unit.modelo) == declaration.source_modelo
        and unit.filing_year == year
        and unit.state is WorkUnitState.BORRADOR
    ]
    if not m130_units:
        raise ModeloProjectNoM130UnitsError(
            context={"year": year},
            translated_message="cli.app.modelo.project.no_m130_units",
        )

    m130_quarters: dict[Period, CalculationRevision] = {}
    for unit in m130_units:
        revisions = list_calculation_revisions(work_unit_id=unit.work_unit_id, ports=ports)
        if revisions and unit.period.is_quarterly:
            m130_quarters[unit.period] = revisions[-1]

    if not m130_quarters:
        raise ModeloProjectNoM130RevisionsError(
            context={"year": year},
            translated_message="cli.app.modelo.project.no_m130_revisions",
        )
    return m130_quarters


@dataclass(frozen=True, slots=True)
class _M130AnnualProjection:
    """Annualised Modelo 130 aggregates that feed the Modelo 100 projection."""

    m130_quarters: dict[Period, CalculationRevision]
    quarters_filed: int
    total_rendimiento_neto: Decimal
    total_ingresos: Decimal
    total_gastos: Decimal
    total_pagos_fraccionados: Decimal
    projected_rendimiento_neto: Decimal
    is_extrapolated: bool


def _m130_annual_projection(
    year: int,
    *,
    declaration: _ProjectionDeclaration,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
) -> _M130AnnualProjection:
    """Read the stored M130 quarters and annualise the cumulative basis."""
    m130_quarters = _m130_quarter_revisions(year, declaration=declaration, ports=ports)
    quarters_filed = len(m130_quarters)
    # The ingresos, gastos and rendimiento neto boxes are year-to-date cumulative:
    # each quarter's value already aggregates Jan 1 through quarter end. The annual
    # basis is therefore the latest available quarter, not a sum of snapshots.
    latest_period = max(m130_quarters, key=lambda period: period.quarter_ordinal or 0)
    latest_ordinal = latest_period.quarter_ordinal
    if latest_ordinal is None:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={"modelo": declaration.source_modelo, "period_is_quarter": False},
        )
    latest_revision = m130_quarters[latest_period]
    latest_source = (
        f"modelo {declaration.source_modelo} {latest_period.registry_token} "
        f"revision {latest_revision.calculation_revision_id}"
    )
    total_rendimiento_neto = _required_casilla_value(
        latest_revision.casilla_values,
        declaration.rendimiento_neto,
        source=latest_source,
    )
    total_ingresos = _required_casilla_value(
        latest_revision.casilla_values,
        declaration.ingresos,
        source=latest_source,
    )
    total_gastos = _required_casilla_value(
        latest_revision.casilla_values,
        declaration.gastos,
        source=latest_source,
    )
    # The final-result box is the incremental payment of each quarter; the annual
    # credit is the sum of the available quarter results.
    total_pagos_fraccionados = sum(
        (
            _required_casilla_value(
                revision.casilla_values,
                declaration.resultado_final,
                source=(
                    f"modelo {declaration.source_modelo} {period.registry_token} "
                    f"revision {revision.calculation_revision_id}"
                ),
            )
            for period, revision in m130_quarters.items()
        ),
        Decimal("0"),
    )
    quarter_count = _source_quarter_count(declaration, year=year, period=latest_period, operation=operation)
    if latest_ordinal < quarter_count:
        projected_rendimiento_neto = round_to_cents(
            total_rendimiento_neto * Decimal(quarter_count) / Decimal(latest_ordinal)
        )
        is_extrapolated = True
    else:
        projected_rendimiento_neto = total_rendimiento_neto
        is_extrapolated = False
    return _M130AnnualProjection(
        m130_quarters=m130_quarters,
        quarters_filed=quarters_filed,
        total_rendimiento_neto=total_rendimiento_neto,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        total_pagos_fraccionados=total_pagos_fraccionados,
        projected_rendimiento_neto=projected_rendimiento_neto,
        is_extrapolated=is_extrapolated,
    )


def _parse_projection_binding_overrides(
    binding_overrides: Mapping[BindingId, str] | None,
    revision: ModeloRevision,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Split caller binding overrides into the Decimal and enum channels.

    The split is decided by the binding's REGISTRY-DECLARED channel, as carried
    on the :class:`ModeloRevision`, never by parse success. Deciding it by parse success inverted the test: a decimal
    binding whose value failed to parse was silently reclassified as an enum
    string, so a Spanish-convention operator's ``--binding <id>=1.234,56`` was
    accepted as the literal text ``"1.234,56"`` on the enum channel instead of
    refusing. Routing by the declared channel makes a malformed decimal refuse
    and leaves a genuine enum binding carrying its string verbatim.

    This shares :func:`validated_binding_input_channel` and
    :func:`decimal_binding_value` with the calculate path rather than deriving a
    second channel-resolution shape, so the two surfaces cannot drift.
    """
    extra_bindings: dict[BindingId, Decimal] = {}
    extra_enum_bindings: dict[BindingId, str] = {}
    if not (binding_overrides is not None and binding_overrides):
        return extra_bindings, extra_enum_bindings

    bindings_by_id = revision_bindings_by_id(revision)
    known_binding_ids = set(bindings_by_id)
    enum_channel_ids = enum_consumed_binding_ids(revision)
    date_channel_ids = revision_date_binding_ids(revision)
    for raw_key, value in binding_overrides.items():
        binding_id = _binding_id(raw_key, surface="project modelo 100 binding override")
        if binding_id in date_channel_ids:
            raise ModeloCalculateBindingInputError(
                f"--binding {binding_id!r} is a date-valued binding sourced from the active "
                "profile (a taxpayer date fact such as the birth date); it cannot be "
                "supplied through --binding, which carries only decimal and enum "
                "values. Set it as a profile fact (e.g. `aeat config profile create "
                "... --taxpayer-birth-date YYYY-MM-DD`) and recalculate.",
                context={"key": binding_id},
                translated_message="application.modelo.errors.calculate_binding_is_date_sourced",
            )
        key, channel = validated_binding_input_channel(binding_id, revision, known_binding_ids, enum_channel_ids)
        if channel == "enum":
            extra_enum_bindings[key] = value
        else:
            extra_bindings[key] = decimal_binding_value(value, bindings_by_id[key])
    return extra_bindings, extra_enum_bindings


def _verb_baseline_projection_bindings(
    ccaa: str,
    declared_binding_ids: set[BindingId],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str], dict[BindingId, bool]]:
    """Build the verb-supplied baseline projection bindings, filtered to declared ids."""

    def binding(value: str) -> BindingId:
        return _binding_id(value, surface="project modelo 100 baseline binding id")

    verb_baseline_bindings: dict[BindingId, Decimal] = {
        binding("renta-modelo-100-estimacion-directa-es-normal"): Decimal("1"),
        binding("renta-profile-declaration-type"): Decimal("1"),
        binding("renta-profile-family-minor-children-in-unit"): Decimal("0"),
        binding("renta-profile-cotizaciones-ss-madre"): Decimal("0"),
        binding("renta-profile-marriage-month-start"): Decimal("0"),
        binding("renta-profile-marriage-month-end"): Decimal("0"),
        binding("renta-base-liquidable-negativa-general-anterior"): Decimal("0"),
    }
    verb_baseline_enum_bindings: dict[BindingId, str] = {
        binding("renta-profile-tax-residence-ccaa"): ccaa,
    }
    verb_baseline_boolean_bindings: dict[BindingId, bool] = {
        binding("renta-profile-marriage-full-year"): False,
    }
    return (
        {key: value for key, value in verb_baseline_bindings.items() if key in declared_binding_ids},
        {key: value for key, value in verb_baseline_enum_bindings.items() if key in declared_binding_ids},
        {key: value for key, value in verb_baseline_boolean_bindings.items() if key in declared_binding_ids},
    )


def _profile_projection_bindings(
    m100_snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    m100_inputs: Mapping[CasillaId, Decimal],
    extra_bindings: Mapping[BindingId, Decimal],
    extra_enum_bindings: Mapping[BindingId, str],
    operation: PinnedAuthorityOperation,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, date], dict[BindingId, str], dict[BindingId, bool]]:
    """Resolve profile-sourced bindings for the caller's explicit bucket."""
    input_bound_binding_ids = {
        casilla.binding
        for casilla in m100_snapshot.revision.casillas
        if casilla.id in m100_inputs and casilla.binding is not None
    }
    caller_owned = set(extra_bindings) | set(extra_enum_bindings) | input_bound_binding_ids
    profile_result = resolve_profile_sourced_bindings(
        m100_snapshot,
        bucket_id=bucket_id,
        caller_binding_ids=frozenset(caller_owned),
        operation=operation,
    )
    return (
        dict(profile_result.binding_values),
        dict(profile_result.date_binding_values),
        dict(profile_result.enum_binding_values),
        dict(profile_result.boolean_binding_values),
    )


def _apply_zero_maritime_projection_default(
    declared_binding_ids: set[BindingId],
    merged_bindings: dict[BindingId, Decimal],
    merged_boolean_bindings: dict[BindingId, bool],
) -> None:
    """Supply the path only when both statutory maritime income channels are zero."""
    maritime_path = _binding_id("renta-maritime-path-rebeca", surface="project modelo 100 maritime path")
    maritime_gross = _binding_id("renta-maritime-gross-navigation-income", surface="project modelo 100 maritime gross")
    maritime_salary = _binding_id("renta-maritime-annual-salary", surface="project modelo 100 maritime salary")
    if (
        maritime_path in declared_binding_ids
        and maritime_path not in merged_boolean_bindings
        and merged_bindings.get(maritime_gross) == Decimal("0")
        and merged_bindings.get(maritime_salary) == Decimal("0")
    ):
        # Either statutory path yields zero when there is no maritime income.
        merged_boolean_bindings[maritime_path] = False


def _m100_projection_result(
    values: Mapping[CasillaId, Decimal],
    *,
    declaration: _ProjectionDeclaration,
) -> ModeloProjectM100Projection:
    source = f"modelo {declaration.target_modelo} projection engine result"
    return ModeloProjectM100Projection(
        base_liquidable_general=_required_casilla_value(values, declaration.base_liquidable_general, source=source),
        pagos_fraccionados=_required_casilla_value(values, declaration.pagos_fraccionados, source=source),
        cuota_integra_estatal=_required_casilla_value(values, declaration.cuota_integra_estatal, source=source),
        cuota_integra_autonomica=_required_casilla_value(values, declaration.cuota_integra_autonomica, source=source),
        cuota_liquida_estatal=_required_casilla_value(values, declaration.cuota_liquida_estatal, source=source),
        cuota_liquida_autonomica=_required_casilla_value(values, declaration.cuota_liquida_autonomica, source=source),
        cuota_resultante=_required_casilla_value(values, declaration.cuota_resultante, source=source),
    )


def project_modelo_100_from_m130(
    *,
    year: int,
    ccaa: str,
    bucket_id: str,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
    casilla_overrides: Mapping[CasillaId, str] | None = None,
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> ModeloProjectServiceResult:
    """Project annual Modelo 100 values from quarterly M130 revisions.

    The service reads stored :class:`CalculationRevision` rows, uses the latest
    cumulative Modelo 130 figures for annual income, sums the declared final-result
    box as the paid-instalment relation, resolves the annual registry snapshot, and returns
    a result without persisting a synthetic revision. All registry reads use the
    caller-owned operation supplied for this workflow.
    """
    declaration = _registry_projection_declaration(year, operation=operation)
    annual = _m130_annual_projection(year, declaration=declaration, ports=ports, operation=operation)

    m100_snapshot = operation.snapshot(declaration.target_modelo, filing_year=year, period=declaration.target_period)
    extra_inputs = validate_casilla_input_ids(
        m100_snapshot.revision,
        _decimal_overrides(
            casilla_overrides or {},
            translated_message="cli.app.modelo.work.casilla_not_decimal",
        ),
    )

    extra_bindings, extra_enum_bindings = _parse_projection_binding_overrides(
        binding_overrides,
        m100_snapshot.revision,
    )

    m100_inputs: dict[CasillaId, Decimal] = {
        declaration.rendimiento_neto_projected: annual.projected_rendimiento_neto,
        **extra_inputs,
    }
    m100_relations: dict[RelationId, Decimal] = {
        _relation_id(
            "renta-modelo-130-pagos-fraccionados",
            surface="project modelo 100 carried relation id",
        ): annual.total_pagos_fraccionados,
        _relation_id(
            "renta-modelo-131-pagos-fraccionados",
            surface="project modelo 100 carried relation id",
        ): Decimal("0"),
    }
    declared_binding_ids = {binding.id for binding in m100_snapshot.revision.bindings}
    verb_baseline_bindings, verb_baseline_enum_bindings, verb_baseline_boolean_bindings = (
        _verb_baseline_projection_bindings(ccaa, declared_binding_ids)
    )
    profile_decimal_bindings, profile_date_bindings, profile_enum_bindings, profile_boolean_bindings = (
        _profile_projection_bindings(
            m100_snapshot,
            bucket_id=bucket_id,
            m100_inputs=m100_inputs,
            extra_bindings=extra_bindings,
            extra_enum_bindings=extra_enum_bindings,
            operation=operation,
        )
    )

    merged_bindings = {**verb_baseline_bindings, **profile_decimal_bindings, **extra_bindings}
    merged_enum_bindings = {**verb_baseline_enum_bindings, **profile_enum_bindings, **extra_enum_bindings}
    merged_date_bindings = dict(profile_date_bindings)
    merged_boolean_bindings = {**verb_baseline_boolean_bindings, **profile_boolean_bindings}
    _apply_zero_maritime_projection_default(declared_binding_ids, merged_bindings, merged_boolean_bindings)

    try:
        engine_result = calculate_registry_snapshot(
            m100_snapshot,
            inputs=m100_inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values=merged_bindings,
            enum_binding_values=merged_enum_bindings,
            relation_values=m100_relations,
            date_binding_values=merged_date_bindings or None,
            boolean_binding_values=merged_boolean_bindings or None,
        )
    except RegistryValidationError:
        _LOG.exception(
            "modelo.project failed year=%s ccaa=%s inputs=%r bindings=%r "
            "enum_bindings=%r relations=%r date_bindings=%r",
            year,
            ccaa,
            m100_inputs,
            merged_bindings,
            merged_enum_bindings,
            m100_relations,
            merged_date_bindings,
        )
        raise

    return ModeloProjectServiceResult(
        year=year,
        ccaa=ccaa,
        quarters_filed=annual.quarters_filed,
        quarters_available=tuple(
            period.registry_token
            for period in sorted(annual.m130_quarters, key=lambda period: period.quarter_ordinal or 0)
        ),
        is_extrapolated=annual.is_extrapolated,
        m130_accumulated=ModeloProjectM130Accumulated(
            ingresos=annual.total_ingresos,
            gastos=annual.total_gastos,
            rendimiento_neto=annual.total_rendimiento_neto,
            pagos_fraccionados=annual.total_pagos_fraccionados,
        ),
        casilla_observations=tuple(
            ModeloProjectionCasillaObservation(
                casilla_id=entry.target_casilla_id,
                value=entry.value,
                formula_id=entry.formula_id,
                legal_refs=tuple(entry.legal_refs),
                source_refs=tuple(entry.source_refs),
            )
            for entry in engine_result.entries
        ),
        m100_projection=_m100_projection_result(engine_result.values, declaration=declaration),
    )


def _best_revision_for_compare(
    *,
    modelo: str,
    filing_year: int,
    ports: CalculationActionPorts,
) -> tuple[CalculationRevision, bool, str]:
    units_for_year = _comparison_work_units(modelo=modelo, filing_year=filing_year, ports=ports)
    if not units_for_year:
        raise ModeloCompareNoWorkUnitsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_work_units",
        )

    period_by_unit = {unit.work_unit_id: unit.period.registry_token for unit in units_for_year}
    all_revisions = _comparison_revisions_for_units(units_for_year, ports=ports)

    if not all_revisions:
        raise ModeloCompareNoRevisionsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_revisions",
        )

    best = _latest_comparison_revision(all_revisions, state=CalculationRevisionState.VERIFICADO_COMPLETO)
    if best is not None:
        return best, False, period_by_unit.get(best.work_unit_id, "0A")

    best = _latest_comparison_revision(all_revisions, state=CalculationRevisionState.BORRADOR)
    if best is not None:
        return best, True, period_by_unit.get(best.work_unit_id, "0A")

    raise ModeloCompareNoUsableRevisionsError(
        context={"modelo": modelo, "filing_year": filing_year},
        translated_message="cli.app.modelo.compare.no_usable_revisions",
    )


def _comparison_work_units(*, modelo: str, filing_year: int, ports: CalculationActionPorts) -> list[WorkUnit]:
    """Return persisted work units matching one comparison coordinate."""
    return [
        unit
        for unit in list_work_units(ports=ports.work_lifecycle_ports)
        if str(unit.modelo) == modelo and unit.filing_year == filing_year
    ]


def _comparison_revisions_for_units(
    units: Iterable[WorkUnit],
    *,
    ports: CalculationActionPorts,
) -> list[CalculationRevision]:
    """Flatten the revisions belonging to comparison work units in unit order."""
    revisions: list[CalculationRevision] = []
    for unit in units:
        revisions.extend(list_calculation_revisions(work_unit_id=unit.work_unit_id, ports=ports))
    return revisions


def _latest_comparison_revision(
    revisions: Iterable[CalculationRevision],
    *,
    state: CalculationRevisionState,
) -> CalculationRevision | None:
    """Return the newest revision in one state, or ``None`` when absent."""
    candidates = [revision for revision in revisions if revision.state is state]
    if not candidates:
        return None
    return max(candidates, key=lambda revision: revision.created_at)


def _comparison_year_pair(years: Iterable[int]) -> tuple[int, int]:
    """Validate and order the two filing years addressed by a comparison."""
    requested_years = sorted(years)
    try:
        year_a, year_b = requested_years
    except ValueError:
        raise ModeloCompareNeedTwoYearsError(translated_message="cli.app.modelo.compare.need_two_years") from None
    return year_a, year_b


def _comparison_static_revisions(
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    period_a: str,
    period_b: str,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloRevision, ModeloRevision]:
    """Resolve both law-version revisions in the historical comparison order."""
    rev_b_static = operation.revision_for_context(
        modelo,
        filing_year=year_b,
        period=period_b,
    )
    rev_a_static = operation.revision_for_context(
        modelo,
        filing_year=year_a,
        period=period_a,
    )
    return rev_a_static, rev_b_static


def _comparison_casilla_metadata(
    rev_a_static: ModeloRevision,
    rev_b_static: ModeloRevision,
) -> dict[CasillaId, CasillaDefinition]:
    """Index casilla metadata in the same A-then-B overwrite order."""
    casilla_meta: dict[CasillaId, CasillaDefinition] = {}
    for static_revision in (rev_a_static, rev_b_static):
        for cdef in static_revision.casillas:
            casilla_meta[cdef.id] = cdef
    return casilla_meta


def _comparison_casilla_label_section(
    casilla_id: CasillaId,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
) -> tuple[str, str]:
    """Return the static label and first section for one comparison row."""
    cdef = casilla_meta.get(casilla_id)
    if cdef is None:
        return casilla_id, ""
    sections = cdef.section
    return cdef.label, sections[0] if sections else ""


def _comparison_delta_rows(
    rev_a: CalculationRevision,
    rev_b: CalculationRevision,
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
) -> list[ModeloCompareDeltaRow]:
    """Build exact own-arithmetic deltas and retain registry provenance."""
    obs_by_id = {obs.casilla_id: obs for revision in (rev_a, rev_b) for obs in revision.observations}
    delta_rows: list[ModeloCompareDeltaRow] = []
    for casilla_id in sorted(set(rev_a.casilla_values) | set(rev_b.casilla_values)):
        value_a = rev_a.casilla_values.get(casilla_id, Decimal("0"))
        value_b = rev_b.casilla_values.get(casilla_id, Decimal("0"))
        delta = value_b - value_a
        label, section = _comparison_casilla_label_section(casilla_id, casilla_meta)
        pct_change = (delta / value_a * Decimal("100")).quantize(Decimal("0.01")) if value_a != Decimal("0") else None
        formula_id, legal_refs, source_refs = _compare_row_provenance(
            modelo=modelo,
            year_a=year_a,
            year_b=year_b,
            casilla_id=casilla_id,
            casilla_meta=casilla_meta,
            observation=obs_by_id.get(casilla_id),
        )
        delta_rows.append(
            ModeloCompareDeltaRow(
                casilla_id=casilla_id,
                label=label,
                section=section,
                year_a_value=value_a,
                year_b_value=value_b,
                delta=delta,
                pct_change=pct_change,
                formula_id=formula_id,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )
    return delta_rows


def _comparison_sections(
    delta_rows: Iterable[ModeloCompareDeltaRow],
) -> tuple[list[str], dict[str, list[ModeloCompareDeltaRow]]]:
    """Group comparison rows while preserving their first-seen section order."""
    sections_seen: list[str] = []
    by_section: dict[str, list[ModeloCompareDeltaRow]] = {}
    for row in delta_rows:
        if row.section not in by_section:
            sections_seen.append(row.section)
            by_section[row.section] = []
        by_section[row.section].append(row)
    return sections_seen, by_section


def compare_modelo_years(
    *,
    modelo: str,
    years: Iterable[int],
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
) -> ModeloCompareServiceResult:
    """Compare the best persisted revision for two filing years.

    Verified :class:`CalculationRevision` rows win over drafts. Each emitted
    :class:`ModeloCompareDeltaRow` is grounded against the compared
    :class:`ModeloRevision` casilla metadata or the revision's recorded
    observation provenance before the :class:`ModeloCompareServiceResult` is
    returned; comparing two already-persisted revisions is not itself a
    filing act, so the registry side is read structurally.
    """
    year_a, year_b = _comparison_year_pair(years)

    rev_a, draft_a, period_a = _best_revision_for_compare(modelo=modelo, filing_year=year_a, ports=ports)
    rev_b, draft_b, period_b = _best_revision_for_compare(modelo=modelo, filing_year=year_b, ports=ports)

    rev_a_static, rev_b_static = _comparison_static_revisions(
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        period_a=period_a,
        period_b=period_b,
        operation=operation,
    )
    casilla_meta = _comparison_casilla_metadata(rev_a_static, rev_b_static)

    # Both sides are the application's OWN arithmetic, which is what separates
    # this from the tree's other per-casilla comparators. A money tolerance
    # would be wrong here rather than merely unnecessary: two of our own
    # revisions differing by a cent differ by a cent, and absorbing that
    # would hide a real change. Absence is zero for the same reason -- a
    # casilla one revision never resolved contributes nothing to it.
    # ``detect_casilla_divergences`` compares against AEAT, where rounding IS
    # an artefact, and
    # ``casillas_a_recapture_would_change`` skips absence entirely.
    delta_rows = _comparison_delta_rows(
        rev_a,
        rev_b,
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        casilla_meta=casilla_meta,
    )
    sections_seen, by_section = _comparison_sections(delta_rows)

    return ModeloCompareServiceResult(
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        year_a_revision_id=rev_a.calculation_revision_id,
        year_b_revision_id=rev_b.calculation_revision_id,
        year_a_is_draft=draft_a,
        year_b_is_draft=draft_b,
        sections=tuple(
            ModeloCompareSection(section=section, rows=tuple(by_section[section])) for section in sections_seen
        ),
        delta_rows=tuple(delta_rows),
    )


__all__ = [
    "ModeloCompareDeltaRow",
    "ModeloCompareNeedTwoYearsError",
    "ModeloCompareNoRevisionsError",
    "ModeloCompareNoUsableRevisionsError",
    "ModeloCompareNoWorkUnitsError",
    "ModeloCompareSection",
    "ModeloCompareServiceResult",
    "ModeloProjectInvalidDecimalOverrideError",
    "ModeloProjectM100Projection",
    "ModeloProjectM130Accumulated",
    "ModeloProjectNoM130RevisionsError",
    "ModeloProjectNoM130UnitsError",
    "ModeloProjectServiceResult",
    "ModeloProjectionCasillaObservation",
    "ModeloProjectionError",
    "RegistrySnapshotError",
    "RegistryValidationError",
    "compare_modelo_years",
    "project_modelo_100_from_m130",
]

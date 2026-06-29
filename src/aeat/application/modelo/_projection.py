"""Projection and year-comparison services for modelo calculations.

The Modelo 100 projection path reads persisted :class:`CalculationRevision`
rows from quarterly Modelo 130 work units, resolves the annual
:class:`RegistrySnapshot`, overlays profile-sourced bindings, and runs
:func:`calculate_registry_snapshot` without persisting a new revision.

The comparison path selects the best draft or verified
:class:`CalculationRevision` for each requested year, grounds each delta row in
the compared registry snapshots, and returns either a
:class:`ModeloProjectServiceResult` or :class:`ModeloCompareServiceResult`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.errors import AeatError
from ...core.logging import get_logger
from ...core.resources import resources
from ...domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    RegistrySnapshotError,
    RegistryValidationError,
    RelationId,
    calculate_registry_snapshot,
    validated_casilla_id,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._work_unit import WorkUnitState
from ._calculation_actions import list_calculation_revisions
from ._profile_binding import resolve_profile_sourced_bindings
from ._registry_helpers import validate_casilla_input_ids
from ._work_lifecycle import list_work_units

_LOG = get_logger(__name__)
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_M100_RENDIMIENTO_NETO_PROJECTED_CASILLA: CasillaId = validated_casilla_id(
    "0171",
    surface="_M100_RENDIMIENTO_NETO_PROJECTED_CASILLA",
)
_M100_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "0505",
    surface="_M100_BASE_LIQUIDABLE_GENERAL_CASILLA",
)
_M100_CUOTA_INTEGRA_ESTATAL_CASILLA: CasillaId = validated_casilla_id(
    "0545",
    surface="_M100_CUOTA_INTEGRA_ESTATAL_CASILLA",
)
_M100_CUOTA_INTEGRA_AUTONOMICA_CASILLA: CasillaId = validated_casilla_id(
    "0546",
    surface="_M100_CUOTA_INTEGRA_AUTONOMICA_CASILLA",
)
_M100_CUOTA_LIQUIDA_ESTATAL_CASILLA: CasillaId = validated_casilla_id(
    "0595",
    surface="_M100_CUOTA_LIQUIDA_ESTATAL_CASILLA",
)
_M100_CUOTA_LIQUIDA_AUTONOMICA_CASILLA: CasillaId = validated_casilla_id(
    "0596",
    surface="_M100_CUOTA_LIQUIDA_AUTONOMICA_CASILLA",
)
_M100_CUOTA_RESULTANTE_CASILLA: CasillaId = validated_casilla_id(
    "0597",
    surface="_M100_CUOTA_RESULTANTE_CASILLA",
)
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_RELATION_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(RelationId)
_M100_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id(
    "0604",
    surface="_M100_PAGOS_FRACCIONADOS_CASILLA",
)


class ModeloProjectionError(AeatError):
    """Base class for application-level projection failures."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        super().__init__(
            message or translated_message or self.__class__.__name__,
            context=dict(context or {}),
            suggestion=suggestion,
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
            f"projection source {source!r} did not produce required casilla {casilla_id!r}",
            context={"source": source, "casilla_id": casilla_id},
        ) from exc


class ModeloProjectionCasillaObservation(BaseModel):
    """One computed casilla emitted by a projection service."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: Decimal
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)


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

    base_liquidable_general_0505: Decimal
    pagos_fraccionados_0604: Decimal
    cuota_integra_estatal_0545: Decimal
    cuota_integra_autonomica_0546: Decimal
    cuota_liquida_estatal_0595: Decimal
    cuota_liquida_autonomica_0596: Decimal
    cuota_resultante_0597: Decimal


class ModeloProjectServiceResult(BaseModel):
    """Year-end Modelo 100 projection from quarterly Modelo 130 filings."""

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
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)


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
    year_a_revision_id: str
    year_b_revision_id: str
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
    observation: object | None,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    cdef = casilla_meta.get(casilla_id)
    if cdef is None:
        raise ModeloProjectionError(
            f"modelo compare cannot ground casilla {casilla_id!r}; it is not declared by either compared revision",
            context={
                "modelo": modelo,
                "year_a": year_a,
                "year_b": year_b,
                "casilla_id": casilla_id,
            },
        )
    formula_id = getattr(observation, "formula_id", None)
    if formula_id is None and cdef.formula is not None:
        formula_id = cdef.formula
    legal_refs = tuple(getattr(observation, "legal_refs", ())) or tuple(cdef.legal_refs)
    source_refs = tuple(getattr(observation, "source_refs", ())) or tuple(cdef.source_refs)
    if not legal_refs or not source_refs:
        raise ModeloProjectionError(
            f"modelo compare cannot ground casilla {casilla_id!r}; registry provenance is incomplete",
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
    values: dict[CasillaId, Decimal] = {}
    for key, value in raw.items():
        try:
            values[key] = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ModeloProjectInvalidDecimalOverrideError(
                context={"key": key, "value": value},
                translated_message=translated_message,
            ) from exc
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


def project_modelo_100_from_m130(
    *,
    year: int,
    ccaa: str,
    casilla_overrides: Mapping[CasillaId, str] | None = None,
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> ModeloProjectServiceResult:
    """Project annual Modelo 100 values from quarterly M130 revisions into a :class:`ModeloProjectServiceResult`."""
    all_units = list_work_units()
    m130_units = [
        unit
        for unit in all_units
        if str(unit.modelo) == Modelo.M130.value and unit.filing_year == year and unit.state is WorkUnitState.BORRADOR
    ]
    if not m130_units:
        raise ModeloProjectNoM130UnitsError(
            context={"year": year},
            translated_message="cli.app.modelo.project.no_m130_units",
        )

    quarters = {"1T", "2T", "3T", "4T"}
    m130_quarters: dict[str, CalculationRevision] = {}
    for unit in m130_units:
        revisions = list_calculation_revisions(work_unit_id=unit.work_unit_id)
        period_token = unit.period.registry_token
        if revisions and period_token in quarters:
            m130_quarters[period_token] = revisions[-1]

    if not m130_quarters:
        raise ModeloProjectNoM130RevisionsError(
            context={"year": year},
            translated_message="cli.app.modelo.project.no_m130_revisions",
        )

    quarters_filed = len(m130_quarters)
    # Modelo 130 casillas 01/02/03 are year-to-date cumulative (their registry
    # bindings are named ``...-cumulative``): each quarter's value already
    # aggregates Jan 1 → end of that quarter. The annual basis is therefore the
    # latest available quarter's value, NOT the sum of the per-quarter snapshots
    # (summing them double/triple/quadruple-counts the same income).
    latest_token = max(m130_quarters, key=lambda token: int(token[0]))
    latest_ordinal = int(latest_token[0])
    latest_revision = m130_quarters[latest_token]
    total_rendimiento_neto = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_RENDIMIENTO_NETO_CASILLA,
        source=f"modelo 130 {latest_token} revision {latest_revision.calculation_revision_id}",
    )
    total_ingresos = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_INGRESOS_CASILLA,
        source=f"modelo 130 {latest_token} revision {latest_revision.calculation_revision_id}",
    )
    total_gastos = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_GASTOS_CASILLA,
        source=f"modelo 130 {latest_token} revision {latest_revision.calculation_revision_id}",
    )
    # Casilla 19 (resultado final) is the per-quarter incremental amount paid, so
    # the annual credit is the sum of the available quarters' results.
    total_pagos_fraccionados = sum(
        (
            _required_casilla_value(
                revision.casilla_values,
                _M130_RESULTADO_FINAL_CASILLA,
                source=f"modelo 130 {period_token} revision {revision.calculation_revision_id}",
            )
            for period_token, revision in m130_quarters.items()
        ),
        Decimal("0"),
    )

    if latest_ordinal < 4:
        projected_rendimiento_neto = (total_rendimiento_neto * Decimal(4) / Decimal(latest_ordinal)).quantize(
            Decimal("0.01"),
        )
        is_extrapolated = True
    else:
        projected_rendimiento_neto = total_rendimiento_neto
        is_extrapolated = False

    authority = resources().modelos.authority
    m100_snapshot = authority.snapshot(Modelo.M100.value, filing_year=year, period="0A")
    extra_inputs = validate_casilla_input_ids(
        m100_snapshot.revision,
        _decimal_overrides(
            casilla_overrides or {},
            translated_message="cli.app.modelo.work.casilla_not_decimal",
        ),
    )

    extra_bindings: dict[BindingId, Decimal] = {}
    extra_enum_bindings: dict[BindingId, str] = {}
    for raw_key, value in (binding_overrides or {}).items():
        key = _binding_id(raw_key, surface="project modelo 100 binding override")
        try:
            extra_bindings[key] = Decimal(value)
        except (InvalidOperation, ValueError):
            extra_enum_bindings[key] = value

    m100_inputs: dict[CasillaId, Decimal] = {
        _M100_RENDIMIENTO_NETO_PROJECTED_CASILLA: projected_rendimiento_neto,
        **extra_inputs,
    }
    m100_relations: dict[RelationId, Decimal] = {
        _relation_id(
            f"renta-{year}-rel-130-pagos-fraccionados",
            surface="project modelo 100 generated relation id",
        ): total_pagos_fraccionados,
        _relation_id(
            f"renta-{year}-rel-131-pagos-fraccionados",
            surface="project modelo 100 generated relation id",
        ): Decimal("0"),
    }
    retenciones_binding_ids = (
        _binding_id(
            f"renta-{year}-modelo-111-retenciones-periodicas",
            surface="project modelo 100 generated binding id",
        ),
        _binding_id(
            f"renta-{year}-modelo-115-retenciones-periodicas",
            surface="project modelo 100 generated binding id",
        ),
        _binding_id(
            f"renta-{year}-modelo-123-retenciones-periodicas",
            surface="project modelo 100 generated binding id",
        ),
        _binding_id(
            f"renta-{year}-modelo-193-retenciones-anuales",
            surface="project modelo 100 generated binding id",
        ),
    )
    verb_baseline_bindings: dict[BindingId, Decimal] = {
        _binding_id(
            f"renta-{year}-modelo-100-estimacion-directa-es-normal",
            surface="project modelo 100 generated binding id",
        ): Decimal("1"),
        _binding_id(
            f"renta-{year}-profile-declaration-type",
            surface="project modelo 100 generated binding id",
        ): Decimal("1"),
        _binding_id(
            f"renta-{year}-profile-family-minor-children-in-unit",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-profile-guarderia-gastos-reales",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-profile-cotizaciones-ss-madre",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-profile-marriage-full-year",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-profile-marriage-month-start",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-profile-marriage-month-end",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        _binding_id(
            f"renta-{year}-base-liquidable-negativa-general-anterior",
            surface="project modelo 100 generated binding id",
        ): Decimal("0"),
        **{binding_id: Decimal("0") for binding_id in retenciones_binding_ids},
    }
    verb_baseline_enum_bindings: dict[BindingId, str] = {
        _binding_id(
            f"renta-{year}-profile-tax-residence-ccaa",
            surface="project modelo 100 generated binding id",
        ): ccaa,
    }
    declared_binding_ids = {binding.id for binding in m100_snapshot.revision.bindings}
    verb_baseline_bindings = {
        binding_id: value for binding_id, value in verb_baseline_bindings.items() if binding_id in declared_binding_ids
    }
    verb_baseline_enum_bindings = {
        binding_id: value
        for binding_id, value in verb_baseline_enum_bindings.items()
        if binding_id in declared_binding_ids
    }

    from ...core import resolve_active_bucket_id

    profile_decimal_bindings: dict[BindingId, Decimal] = {}
    profile_date_bindings: dict[BindingId, date] = {}
    profile_enum_bindings: dict[BindingId, str] = {}
    bucket_id = resolve_active_bucket_id()
    if bucket_id is not None:
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
        )
        profile_decimal_bindings = dict(profile_result.binding_values)
        profile_date_bindings = dict(profile_result.date_binding_values)
        profile_enum_bindings = dict(profile_result.enum_binding_values)

    merged_bindings = {**verb_baseline_bindings, **profile_decimal_bindings, **extra_bindings}
    merged_enum_bindings = {**verb_baseline_enum_bindings, **profile_enum_bindings, **extra_enum_bindings}
    merged_date_bindings = dict(profile_date_bindings)

    try:
        engine_result = calculate_registry_snapshot(
            m100_snapshot,
            inputs=m100_inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values=merged_bindings,
            enum_binding_values=merged_enum_bindings,
            relation_values=m100_relations,
            date_binding_values=merged_date_bindings or None,
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
        quarters_filed=quarters_filed,
        quarters_available=tuple(sorted(m130_quarters)),
        is_extrapolated=is_extrapolated,
        m130_accumulated=ModeloProjectM130Accumulated(
            ingresos=total_ingresos,
            gastos=total_gastos,
            rendimiento_neto=total_rendimiento_neto,
            pagos_fraccionados=total_pagos_fraccionados,
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
        m100_projection=ModeloProjectM100Projection(
            base_liquidable_general_0505=_required_casilla_value(
                engine_result.values,
                _M100_BASE_LIQUIDABLE_GENERAL_CASILLA,
                source="modelo 100 projection engine result",
            ),
            pagos_fraccionados_0604=_required_casilla_value(
                engine_result.values,
                _M100_PAGOS_FRACCIONADOS_CASILLA,
                source="modelo 100 projection engine result",
            ),
            cuota_integra_estatal_0545=_required_casilla_value(
                engine_result.values,
                _M100_CUOTA_INTEGRA_ESTATAL_CASILLA,
                source="modelo 100 projection engine result",
            ),
            cuota_integra_autonomica_0546=_required_casilla_value(
                engine_result.values,
                _M100_CUOTA_INTEGRA_AUTONOMICA_CASILLA,
                source="modelo 100 projection engine result",
            ),
            cuota_liquida_estatal_0595=_required_casilla_value(
                engine_result.values,
                _M100_CUOTA_LIQUIDA_ESTATAL_CASILLA,
                source="modelo 100 projection engine result",
            ),
            cuota_liquida_autonomica_0596=_required_casilla_value(
                engine_result.values,
                _M100_CUOTA_LIQUIDA_AUTONOMICA_CASILLA,
                source="modelo 100 projection engine result",
            ),
            cuota_resultante_0597=_required_casilla_value(
                engine_result.values,
                _M100_CUOTA_RESULTANTE_CASILLA,
                source="modelo 100 projection engine result",
            ),
        ),
    )


def _best_revision_for_compare(
    *,
    modelo: str,
    filing_year: int,
) -> tuple[CalculationRevision, bool, str]:
    units_for_year = [
        unit for unit in list_work_units() if str(unit.modelo) == modelo and unit.filing_year == filing_year
    ]
    if not units_for_year:
        raise ModeloCompareNoWorkUnitsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_work_units",
        )

    period_by_unit = {unit.work_unit_id: unit.period.registry_token for unit in units_for_year}
    all_revisions: list[CalculationRevision] = []
    for unit in units_for_year:
        all_revisions.extend(list_calculation_revisions(work_unit_id=unit.work_unit_id))

    if not all_revisions:
        raise ModeloCompareNoRevisionsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_revisions",
        )

    verified = [
        revision for revision in all_revisions if revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    ]
    if verified:
        best = max(verified, key=lambda revision: revision.created_at)
        return best, False, period_by_unit.get(best.work_unit_id, "0A")

    borradores = [revision for revision in all_revisions if revision.state is CalculationRevisionState.BORRADOR]
    if borradores:
        best = max(borradores, key=lambda revision: revision.created_at)
        return best, True, period_by_unit.get(best.work_unit_id, "0A")

    raise ModeloCompareNoUsableRevisionsError(
        context={"modelo": modelo, "filing_year": filing_year},
        translated_message="cli.app.modelo.compare.no_usable_revisions",
    )


def compare_modelo_years(
    *,
    modelo: str,
    years: Iterable[int],
) -> ModeloCompareServiceResult:
    """Compare the best calculation revision for two filing years and return a :class:`ModeloCompareServiceResult`."""
    requested_years = list(years)
    if len(requested_years) != 2:
        raise ModeloCompareNeedTwoYearsError(translated_message="cli.app.modelo.compare.need_two_years")
    year_a, year_b = sorted(requested_years)

    rev_a, draft_a, period_a = _best_revision_for_compare(modelo=modelo, filing_year=year_a)
    rev_b, draft_b, period_b = _best_revision_for_compare(modelo=modelo, filing_year=year_b)

    authority = resources().modelos.authority
    snap_b = authority.snapshot(modelo, filing_year=year_b, period=period_b)
    snap_a = authority.snapshot(modelo, filing_year=year_a, period=period_a)

    casilla_meta: dict[CasillaId, CasillaDefinition] = {}
    for snapshot in (snap_a, snap_b):
        for cdef in snapshot.revision.casillas:
            casilla_meta[cdef.id] = cdef

    def _meta(casilla_id: CasillaId) -> tuple[str, str]:
        cdef = casilla_meta.get(casilla_id)
        if cdef is None:
            return casilla_id, ""
        label = getattr(cdef, "label", casilla_id)
        sections = getattr(cdef, "section", ())
        primary_section = sections[0] if sections else ""
        return label, primary_section

    obs_by_id = {obs.casilla_id: obs for revision in (rev_a, rev_b) for obs in revision.observations}
    delta_rows: list[ModeloCompareDeltaRow] = []
    for casilla_id in sorted(set(rev_a.casilla_values) | set(rev_b.casilla_values)):
        value_a = rev_a.casilla_values.get(casilla_id, Decimal("0"))
        value_b = rev_b.casilla_values.get(casilla_id, Decimal("0"))
        delta = value_b - value_a
        label, section = _meta(casilla_id)
        pct_change = (delta / value_a * Decimal("100")).quantize(Decimal("0.01")) if value_a != Decimal("0") else None
        observation = obs_by_id.get(casilla_id)
        formula_id, legal_refs, source_refs = _compare_row_provenance(
            modelo=modelo,
            year_a=year_a,
            year_b=year_b,
            casilla_id=casilla_id,
            casilla_meta=casilla_meta,
            observation=observation,
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

    sections_seen: list[str] = []
    by_section: dict[str, list[ModeloCompareDeltaRow]] = {}
    for row in delta_rows:
        if row.section not in by_section:
            sections_seen.append(row.section)
            by_section[row.section] = []
        by_section[row.section].append(row)

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

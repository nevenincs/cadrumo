"""Application services for modelo projection and comparison commands.

Use of :class:`CalculationRevision` for compliance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.errors import AeatError
from ...core.logging import get_logger
from ...core.resources import resources
from ...domain.calculations.registry import (
    RegistrySnapshotError,
    RegistryValidationError,
    calculate_registry_snapshot,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._work_unit import WorkUnitState
from ._calculation_actions import list_calculation_revisions
from ._profile_binding import resolve_profile_sourced_bindings
from ._work_lifecycle import list_work_units

_LOG = get_logger(__name__)


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


class ModeloProjectionCasillaObservation(BaseModel):
    """One computed casilla emitted by a projection service."""

    model_config = _STRICT_FROZEN

    casilla_id: str = Field(min_length=1)
    value: Decimal
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


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

    casilla_id: str = Field(min_length=1)
    label: str
    section: str
    year_a_value: Decimal
    year_b_value: Decimal
    delta: Decimal
    pct_change: Decimal | None
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


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


def _decimal_overrides(
    raw: Mapping[str, str],
    *,
    translated_message: str,
) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for key, value in raw.items():
        try:
            values[key] = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ModeloProjectInvalidDecimalOverrideError(
                context={"key": key, "value": value},
                translated_message=translated_message,
            ) from exc
    return values


def project_modelo_100_from_m130(
    *,
    year: int,
    ccaa: str,
    casilla_overrides: Mapping[str, str] | None = None,
    binding_overrides: Mapping[str, str] | None = None,
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
    total_rendimiento_neto = sum(
        (revision.casilla_values.get("03", Decimal("0")) for revision in m130_quarters.values()),
        Decimal("0"),
    )
    total_pagos_fraccionados = sum(
        (revision.casilla_values.get("19", Decimal("0")) for revision in m130_quarters.values()),
        Decimal("0"),
    )
    total_ingresos = sum(
        (revision.casilla_values.get("01", Decimal("0")) for revision in m130_quarters.values()),
        Decimal("0"),
    )
    total_gastos = sum(
        (revision.casilla_values.get("02", Decimal("0")) for revision in m130_quarters.values()),
        Decimal("0"),
    )

    if quarters_filed < 4:
        projected_rendimiento_neto = (total_rendimiento_neto * Decimal(4) / Decimal(quarters_filed)).quantize(
            Decimal("0.01"),
        )
        is_extrapolated = True
    else:
        projected_rendimiento_neto = total_rendimiento_neto
        is_extrapolated = False

    authority = resources().modelos.authority
    m100_snapshot = authority.snapshot(Modelo.M100.value, filing_year=year, period="0A")
    extra_inputs = _decimal_overrides(
        casilla_overrides or {},
        translated_message="cli.app.modelo.work.casilla_not_decimal",
    )

    extra_bindings: dict[str, Decimal] = {}
    extra_enum_bindings: dict[str, str] = {}
    for key, value in (binding_overrides or {}).items():
        try:
            extra_bindings[key] = Decimal(value)
        except (InvalidOperation, ValueError):
            extra_enum_bindings[key] = value

    m100_inputs: dict[str, Decimal] = {"0171": projected_rendimiento_neto, **extra_inputs}
    m100_relations: dict[str, Decimal] = {
        f"renta-{year}-rel-130-pagos-fraccionados": total_pagos_fraccionados,
        f"renta-{year}-rel-131-pagos-fraccionados": Decimal("0"),
    }
    retenciones_binding_ids = (
        f"renta-{year}-modelo-111-retenciones-periodicas",
        f"renta-{year}-modelo-115-retenciones-periodicas",
        f"renta-{year}-modelo-123-retenciones-periodicas",
        f"renta-{year}-modelo-193-retenciones-anuales",
    )
    verb_baseline_bindings: dict[str, Decimal] = {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        f"renta-{year}-profile-declaration-type": Decimal("1"),
        f"renta-{year}-profile-family-minor-children-in-unit": Decimal("0"),
        f"renta-{year}-profile-guarderia-gastos-reales": Decimal("0"),
        f"renta-{year}-profile-cotizaciones-ss-madre": Decimal("0"),
        f"renta-{year}-profile-marriage-full-year": Decimal("0"),
        f"renta-{year}-profile-marriage-month-start": Decimal("0"),
        f"renta-{year}-profile-marriage-month-end": Decimal("0"),
        f"renta-{year}-base-liquidable-negativa-general-anterior": Decimal("0"),
        **{binding_id: Decimal("0") for binding_id in retenciones_binding_ids},
    }
    verb_baseline_enum_bindings: dict[str, str] = {
        f"renta-{year}-profile-tax-residence-ccaa": ccaa,
    }

    from ...core import resolve_active_bucket_id

    profile_decimal_bindings: dict[str, Decimal] = {}
    profile_date_bindings: dict[str, date] = {}
    profile_enum_bindings: dict[str, str] = {}
    bucket_id = resolve_active_bucket_id()
    if bucket_id is not None:
        caller_owned = set(extra_bindings) | set(extra_enum_bindings) | set(m100_inputs)
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
                casilla_id=entry.target,
                value=entry.value,
                formula_id=entry.formula_id,
                legal_refs=tuple(entry.legal_refs),
                source_refs=tuple(entry.source_refs),
            )
            for entry in engine_result.entries
        ),
        m100_projection=ModeloProjectM100Projection(
            base_liquidable_general_0505=projected_rendimiento_neto,
            pagos_fraccionados_0604=total_pagos_fraccionados,
            cuota_integra_estatal_0545=engine_result.values.get("0545", Decimal("0")),
            cuota_integra_autonomica_0546=engine_result.values.get("0546", Decimal("0")),
            cuota_liquida_estatal_0595=engine_result.values.get("0595", Decimal("0")),
            cuota_liquida_autonomica_0596=engine_result.values.get("0596", Decimal("0")),
            cuota_resultante_0597=engine_result.values.get("0597", Decimal("0")),
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

    casilla_meta: dict[str, object] = {}
    for snapshot in (snap_a, snap_b):
        for cdef in snapshot.revision.casillas:
            casilla_meta[cdef.id] = cdef

    def _meta(casilla_id: str) -> tuple[str, str]:
        cdef = casilla_meta.get(casilla_id)
        if cdef is None:
            return casilla_id, ""
        label = getattr(cdef, "label", str(casilla_id))
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
        delta_rows.append(
            ModeloCompareDeltaRow(
                casilla_id=casilla_id,
                label=label,
                section=section,
                year_a_value=value_a,
                year_b_value=value_b,
                delta=delta,
                pct_change=pct_change,
                formula_id=observation.formula_id if observation is not None else None,
                legal_refs=tuple(observation.legal_refs) if observation is not None else (),
                source_refs=tuple(observation.source_refs) if observation is not None else (),
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

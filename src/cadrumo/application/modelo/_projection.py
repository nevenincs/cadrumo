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
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.period import Period
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal import try_parse_canonical_decimal
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger
from ...core.money import round_to_cents
from ...core.resources import bundled_path
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.temporal import select_revision
from ...domain.modelos.work_unit import WorkUnitState
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ._calculate_input import (
    ModeloCalculateBindingInputError,
)
from ._calculate_input import (
    decimal_binding_value as _decimal_binding_value,
)
from ._calculate_input import (
    validated_binding_input_channel as _validated_binding_input_channel,
)
from ._calculation_actions import list_calculation_revisions
from ._registry_helpers import validate_casilla_input_ids
from .work_lifecycle import list_work_units
from .profile_binding import resolve_profile_sourced_bindings

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


class ModeloProjectionError(CadrumoError):
    """Base class for application-level projection failures."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
    ) -> None:
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

    base_liquidable_general_0505: Decimal
    pagos_fraccionados_0604: Decimal
    cuota_integra_estatal_0545: Decimal
    cuota_integra_autonomica_0546: Decimal
    cuota_liquida_estatal_0595: Decimal
    cuota_liquida_autonomica_0596: Decimal
    cuota_resultante_0597: Decimal


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

    Mirrors :func:`cadrumo.application.modelo._calculate_input._decimal`: the
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


def _m130_quarter_revisions(year: int) -> dict[Period, CalculationRevision]:
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

    m130_quarters: dict[Period, CalculationRevision] = {}
    for unit in m130_units:
        revisions = list_calculation_revisions(work_unit_id=unit.work_unit_id)
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


def _m130_annual_projection(year: int) -> _M130AnnualProjection:
    """Read the stored Modelo 130 quarters and annualise the cumulative basis."""
    m130_quarters = _m130_quarter_revisions(year)
    quarters_filed = len(m130_quarters)
    # Modelo 130 casillas 01/02/03 are year-to-date cumulative (their registry
    # bindings are named ``...-cumulative``): each quarter's value already
    # aggregates Jan 1 → end of that quarter. The annual basis is therefore the
    # latest available quarter's value, NOT the sum of the per-quarter snapshots
    # (summing them double/triple/quadruple-counts the same income).
    latest_period = max(m130_quarters, key=lambda period: period.quarter_ordinal or 0)
    latest_ordinal = latest_period.quarter_ordinal
    if latest_ordinal is None:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={"modelo": Modelo.M130.value, "period_is_quarter": False},
        )
    latest_revision = m130_quarters[latest_period]
    total_rendimiento_neto = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_RENDIMIENTO_NETO_CASILLA,
        source=f"modelo 130 {latest_period.registry_token} revision {latest_revision.calculation_revision_id}",
    )
    total_ingresos = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_INGRESOS_CASILLA,
        source=f"modelo 130 {latest_period.registry_token} revision {latest_revision.calculation_revision_id}",
    )
    total_gastos = _required_casilla_value(
        latest_revision.casilla_values,
        _M130_GASTOS_CASILLA,
        source=f"modelo 130 {latest_period.registry_token} revision {latest_revision.calculation_revision_id}",
    )
    # Casilla 19 (resultado final) is the per-quarter incremental amount paid, so
    # the annual credit is the sum of the available quarters' results.
    total_pagos_fraccionados = sum(
        (
            _required_casilla_value(
                revision.casilla_values,
                _M130_RESULTADO_FINAL_CASILLA,
                source=f"modelo 130 {period.registry_token} revision {revision.calculation_revision_id}",
            )
            for period, revision in m130_quarters.items()
        ),
        Decimal("0"),
    )
    if latest_ordinal < 4:
        projected_rendimiento_neto = round_to_cents(total_rendimiento_neto * Decimal(4) / Decimal(latest_ordinal))
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

    This shares :func:`_validated_binding_input_channel` and
    :func:`_decimal_binding_value` with the calculate path rather than deriving a
    second channel-resolution shape, so the two surfaces cannot drift.
    """
    extra_bindings: dict[BindingId, Decimal] = {}
    extra_enum_bindings: dict[BindingId, str] = {}
    if not binding_overrides:
        return extra_bindings, extra_enum_bindings

    bindings_by_id = {binding.id: binding for binding in revision.bindings}
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
        key, channel = _validated_binding_input_channel(binding_id, revision, known_binding_ids, enum_channel_ids)
        if channel == "enum":
            extra_enum_bindings[key] = value
        else:
            extra_bindings[key] = _decimal_binding_value(value, bindings_by_id[key])
    return extra_bindings, extra_enum_bindings


def _verb_baseline_projection_bindings(
    year: int,
    ccaa: str,
    declared_binding_ids: set[BindingId],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Build the verb-supplied baseline projection bindings, filtered to declared ids."""
    retenciones_binding_ids = (
        _binding_id(
            f"renta-{year}-modelo-111-retenciones-periodicas",
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
    verb_baseline_bindings = {
        binding_id: value for binding_id, value in verb_baseline_bindings.items() if binding_id in declared_binding_ids
    }
    verb_baseline_enum_bindings = {
        binding_id: value
        for binding_id, value in verb_baseline_enum_bindings.items()
        if binding_id in declared_binding_ids
    }
    return verb_baseline_bindings, verb_baseline_enum_bindings


def _profile_projection_bindings(
    m100_snapshot: RegistrySnapshot,
    *,
    m100_inputs: Mapping[CasillaId, Decimal],
    extra_bindings: Mapping[BindingId, Decimal],
    extra_enum_bindings: Mapping[BindingId, str],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, date], dict[BindingId, str]]:
    """Resolve the active bucket's profile-sourced projection bindings (empty when no bucket)."""
    from ...core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return {}, {}, {}
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
    return (
        dict(profile_result.binding_values),
        dict(profile_result.date_binding_values),
        dict(profile_result.enum_binding_values),
    )


def project_modelo_100_from_m130(
    *,
    year: int,
    ccaa: str,
    casilla_overrides: Mapping[CasillaId, str] | None = None,
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> ModeloProjectServiceResult:
    """Project annual Modelo 100 values from quarterly M130 revisions.

    The service reads stored :class:`CalculationRevision` rows, uses the latest
    cumulative Modelo 130 figures for annual income, sums casilla 19 as the paid
    instalment relation, resolves the annual :class:`RegistrySnapshot`, and
    returns a :class:`ModeloProjectServiceResult` without writing a new revision.
    """
    annual = _m130_annual_projection(year)

    authority = bundled_authority()
    m100_snapshot = authority.snapshot(Modelo.M100.value, filing_year=year, period="0A")
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
        _M100_RENDIMIENTO_NETO_PROJECTED_CASILLA: annual.projected_rendimiento_neto,
        **extra_inputs,
    }
    m100_relations: dict[RelationId, Decimal] = {
        _relation_id(
            f"renta-{year}-rel-130-pagos-fraccionados",
            surface="project modelo 100 generated relation id",
        ): annual.total_pagos_fraccionados,
        _relation_id(
            f"renta-{year}-rel-131-pagos-fraccionados",
            surface="project modelo 100 generated relation id",
        ): Decimal("0"),
    }
    declared_binding_ids = {binding.id for binding in m100_snapshot.revision.bindings}
    verb_baseline_bindings, verb_baseline_enum_bindings = _verb_baseline_projection_bindings(
        year,
        ccaa,
        declared_binding_ids,
    )
    profile_decimal_bindings, profile_date_bindings, profile_enum_bindings = _profile_projection_bindings(
        m100_snapshot,
        m100_inputs=m100_inputs,
        extra_bindings=extra_bindings,
        extra_enum_bindings=extra_enum_bindings,
    )

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
    """Compare the best persisted revision for two filing years.

    Verified :class:`CalculationRevision` rows win over drafts. Each emitted
    :class:`ModeloCompareDeltaRow` is grounded against the compared
    :class:`ModeloRevision` casilla metadata or the revision's recorded
    observation provenance before the :class:`ModeloCompareServiceResult` is
    returned; comparing two already-persisted revisions is not itself a
    filing act, so the registry side is read structurally.
    """
    requested_years = list(years)
    if len(requested_years) != 2:
        raise ModeloCompareNeedTwoYearsError(translated_message="cli.app.modelo.compare.need_two_years")
    year_a, year_b = sorted(requested_years)

    rev_a, draft_a, period_a = _best_revision_for_compare(modelo=modelo, filing_year=year_a)
    rev_b, draft_b, period_b = _best_revision_for_compare(modelo=modelo, filing_year=year_b)

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    rev_b_static = select_revision(modelo_definition, filing_year=year_b, period=period_b)
    rev_a_static = select_revision(modelo_definition, filing_year=year_a, period=period_a)

    casilla_meta: dict[CasillaId, CasillaDefinition] = {}
    for static_revision in (rev_a_static, rev_b_static):
        for cdef in static_revision.casillas:
            casilla_meta[cdef.id] = cdef

    def _meta(casilla_id: CasillaId) -> tuple[str, str]:
        cdef = casilla_meta.get(casilla_id)
        if cdef is None:
            return casilla_id, ""
        label = cdef.label
        sections = cdef.section
        primary_section = sections[0] if sections else ""
        return label, primary_section

    # Both sides are the application's OWN arithmetic, which is what separates
    # this from the tree's other per-casilla comparators. A money tolerance
    # would be wrong here rather than merely unnecessary: two of our own
    # revisions differing by a cent differ by a cent, and absorbing that
    # would hide a real change. Absence is zero for the same reason -- a
    # casilla one revision never resolved contributes nothing to it.
    # ``detect_casilla_divergences`` and ``compare_calculation_to_filed_observation``
    # both compare against AEAT, where rounding IS an artefact, and
    # ``casillas_a_recapture_would_change`` skips absence entirely.
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

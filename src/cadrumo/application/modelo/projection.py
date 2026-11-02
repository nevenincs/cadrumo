"""Projection and year-comparison services for modelo calculations.

The Modelo 100 projection path reads persisted :class:`CalculationRevision`
rows from quarterly Modelo 130 work units, resolves the annual
:class:`RegistrySnapshot`, injects the latest cumulative Modelo 130 income at
the annual Renta input leaf, threads pagos fraccionados through the relation
channel, overlays decimal, enum, and date profile facts from
:func:`resolve_profile_sourced_bindings`, resolves the suffered-withholding
credits through their source-mesh resolver, and runs
:func:`calculate_registry_snapshot` without persisting the synthetic result. A
credit with no payer record or attestation stays unresolved, and so does every
box computed from it: both are reported, never shown as a number.

The comparison path selects the best draft or verified
:class:`CalculationRevision` for each requested year, grounds each delta row in
the compared registry snapshots, and returns either a
:class:`ModeloProjectServiceResult` or :class:`ModeloCompareServiceResult`.

Core types:
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.money.rounding import round_to_cents
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period, StandardPeriodCode
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id, sole_bound_casilla
from ...domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ...domain.calculations.registry.errors import (
    GovernedFactNotApplicableError,
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    SourceRefId,
)
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    revision_date_binding_ids,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from ..aggregation.retencion_soportada_source import RetencionSoportadaSourceResolver
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ..operator_actions.models import PreconditionVerdict
from ..user_profile.projections import fact_value
from ._calculation_source_staging import add_expected_missing_binding_diagnostics
from ._registry_helpers import validate_casilla_input_ids
from .calculate_input_validation import (
    ModeloCalculateBindingInputError,
    decimal_binding_value,
    validated_binding_input_channel,
)
from .calculation_action_ports import CalculationActionPorts
from .calculation_revision_queries import list_calculation_revisions
from .calculation_route import require_calculation_route_resolver
from .calculation_source_guards import reject_caller_overrides_of_source_bindings
from .preconditions import build_modelo_precondition_failure_for_scenario
from .profile_binding import resolve_profile_sourced_bindings
from .profile_readiness_gate import load_modelo_work_profile
from .work_lifecycle import list_work_units
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_LOG = get_logger(__name__)
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_RELATION_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(RelationId)
# Suffered withholding is owned by the payer records and absence attestations,
# so a caller figure would stand in for the evidence the calculation refuses to
# take from a caller; the projection refuses it the same way.
_PROJECTION_SOURCE_OWNED_KINDS: frozenset[BindingSourceKind] = frozenset({BindingSourceKind.RETENCION_SOPORTADA})

# The verb baseline: bindings a projection supplies itself rather than reading
# from the taxpayer profile.
_VERB_BASELINE_DECIMAL_BINDINGS: Mapping[str, Decimal] = {
    "renta-profile-declaration-type": Decimal("1"),
    "renta-profile-family-minor-children-in-unit": Decimal("0"),
    "renta-profile-cotizaciones-ss-madre": Decimal("0"),
    "renta-profile-marriage-month-start": Decimal("0"),
    "renta-profile-marriage-month-end": Decimal("0"),
    "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
}
_VERB_BASELINE_BOOLEAN_BINDINGS: Mapping[str, bool] = {
    "renta-modelo-100-estimacion-directa-es-normal": True,
    "renta-profile-marriage-full-year": False,
}
_REGION_BINDING_ID = "renta-profile-tax-residence-ccaa"
"""The value source that carries the filer's tax-residence region into the annual return."""


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


class ModeloProjectNoM130UnitsError(TerminalPreconditionErrorMixin[PreconditionVerdict], ModeloProjectionError):
    """Raised when a year-end projection has no quarterly Modelo 130 work units.

    The verdict names creating the first quarter as the remedy, so a frontend
    offers that action without any command in the sentence it shows.
    """


class ModeloProjectNoM130RevisionsError(TerminalPreconditionErrorMixin[PreconditionVerdict], ModeloProjectionError):
    """Raised when Modelo 130 work units exist but have no calculation revisions.

    The verdict names calculating the earliest uncalculated quarter as the remedy.
    """


class ModeloProjectRegionUnstatedError(TerminalPreconditionErrorMixin[PreconditionVerdict], ModeloProjectionError):
    """Raised when a projection names no region and the profile's tax residence states none.

    A region is never guessed: the filer's own tax residence decides which
    autonomous-community scale applies, so without one nothing honest can be
    projected.
    """


class ModeloProjectInvalidDecimalOverrideError(ModeloProjectionError):
    """Raised when a projection override cannot be parsed as a decimal."""


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


class ModeloProjectionUnresolvedBinding(BaseModel):
    """One source-owned binding the projection's sources left without a value.

    ``reason`` is the source diagnostic's reason token and ``note`` its closed
    calculation-note sentence when the resolver named one (for a credit: no
    payer evidence, or evidence contradicted by an absence attestation).
    ``fact`` is that sentence with the values it names, kept so the words of the
    note can be served; it is not a public field.
    """

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    casilla_id: CasillaId | None
    source_kind: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    note: CalculationNoteSentence | None = None
    fact: CalculationNoteFact | None = None


UNRESOLVED_OPERAND_REASON = "unresolved_operand"
"""The reason of a computed box omitted because an operand it reads is unresolved."""


class ModeloProjectionUnresolvedCasilla(BaseModel):
    """One computed box the projection could not give a value, with its formula's grounding.

    ``reason`` is :data:`UNRESOLVED_OPERAND_REASON` when the box reads an
    unresolved operand, or the engine's typed outcome reason otherwise.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    reason: str = Field(min_length=1)
    formula_id: FormulaId
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
    unresolved_bindings: tuple[ModeloProjectionUnresolvedBinding, ...] = ()
    unresolved_casillas: tuple[ModeloProjectionUnresolvedCasilla, ...] = ()


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
    target_revision: str
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
        target_revision=declared("revision"),
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


def modelo_projection_available(
    *,
    modelo: str,
    period: Period,
    filing_year: int,
    registry_revision_id: str,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the registry lets this declaration's revision ask for the annual projection.

    The dated cross-model projection declaration names the modelo, period and
    revision it was authored against. A declaration is projectable only when it
    is exactly that target, so the answer follows the registry and never the
    modelo's number. A year the declaration does not reach is not projectable.
    """
    try:
        declaration = _registry_projection_declaration(filing_year, operation=operation)
    except GovernedFactNotApplicableError:
        return False
    return (
        declaration.target_modelo == modelo
        and declaration.target_period == period.registry_token
        and declaration.target_revision == registry_revision_id
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


def _no_quarter_remedy(year: int, *, declaration: _ProjectionDeclaration) -> PreconditionVerdict:
    """The verdict that names creating the first quarter's declaration as the way to a projection."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.project",
        scenario_id="modelo.project.m130_quarters.no_work_units",
        evidence_id="modelo.project.m130_quarters",
        evidence_values={"modelo": declaration.source_modelo, "year": year, "work_units_present": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={
            "modelo": declaration.source_modelo,
            "period": StandardPeriodCode.Q1.value,
            "year": year,
        },
    ).verdict


def _uncalculated_quarter_remedy(
    year: int, *, declaration: _ProjectionDeclaration, uncalculated: list[WorkUnit]
) -> PreconditionVerdict:
    """The verdict that names calculating the earliest quarter that has no calculation."""
    earliest = min(uncalculated, key=lambda unit: unit.period.quarter_ordinal or 0)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.project",
        scenario_id="modelo.project.m130_quarters.no_calculation",
        evidence_id="modelo.project.m130_quarters",
        evidence_values={
            "modelo": declaration.source_modelo,
            "year": year,
            "work_unit_id": earliest.work_unit_id,
            "calculation_present": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": earliest.work_unit_id},
    ).verdict


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
        and unit.period.is_quarterly
    ]
    if not m130_units:
        raise ModeloProjectNoM130UnitsError(
            context={"year": year},
            translated_message="application.modelo.projection_words.no_m130_units",
            precondition_verdict=_no_quarter_remedy(year, declaration=declaration),
        )

    m130_quarters: dict[Period, CalculationRevision] = {}
    for unit in m130_units:
        revisions = list_calculation_revisions(work_unit_id=unit.work_unit_id, ports=ports)
        if revisions:
            m130_quarters[unit.period] = revisions[-1]

    if not m130_quarters:
        raise ModeloProjectNoM130RevisionsError(
            context={"year": year},
            translated_message="application.modelo.projection_words.no_m130_revisions",
            precondition_verdict=_uncalculated_quarter_remedy(year, declaration=declaration, uncalculated=m130_units),
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
    revision: ModeloRevision,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str], dict[BindingId, bool]]:
    """Build the verb-supplied baseline projection bindings, filtered to what the verb owns.

    The baseline supplies only bindings the registry does not source from the
    taxpayer profile, plus the ``ccaa`` the verb itself takes as a parameter. A
    profile-sourced binding belongs to the profile channel: a baseline copy
    would put a stand-in value on a second channel beside the profile's typed
    one, and would turn an absent profile fact into a supplied zero or false.
    """
    declared = {binding.id for binding in revision.bindings}
    profile_sourced = {binding.id for binding in revision.bindings if binding.source is BindingSourceKind.PROFILE}
    owned = declared - profile_sourced

    def baseline[Value](table: Mapping[str, Value], allowed: set[BindingId]) -> dict[BindingId, Value]:
        keyed = {
            _binding_id(raw, surface="project modelo 100 baseline binding id"): value for raw, value in table.items()
        }
        return {key: value for key, value in keyed.items() if key in allowed}

    return (
        baseline(_VERB_BASELINE_DECIMAL_BINDINGS, owned),
        baseline({_REGION_BINDING_ID: ccaa}, declared),
        baseline(_VERB_BASELINE_BOOLEAN_BINDINGS, owned),
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


def _absent_profile_binding_ids(revision: ModeloRevision, *, supplied: set[BindingId]) -> tuple[BindingId, ...]:
    """Name each profile-sourced binding no channel supplied, so the engine reports it unresolved.

    The profile is silent on a fact the taxpayer never declared. That absence is
    not zero or false, so the dependent boxes stay unresolved instead of the
    engine refusing the whole projection or a stand-in value filling the gap.
    """
    return tuple(
        binding.id
        for binding in revision.bindings
        if binding.source is BindingSourceKind.PROFILE and binding.id not in supplied
    )


def _unresolved_formula_expressions(
    engine_result: RegistryCalculationResult,
    revision: ModeloRevision,
) -> dict[CasillaId, str]:
    """Return the serialized expression of each formula target the engine produced no observation for."""
    observed = {observation.casilla_id for observation in engine_result.observations}
    return {
        formula.target_casilla_id: formula.expression.model_dump_json()
        for formula in revision.formulas
        if formula.target_casilla_id not in observed
    }


def _expressions_reached_from(
    expression_by_target: Mapping[CasillaId, str],
    required: tuple[CasillaId, ...],
) -> list[str]:
    """Return the expressions of the unresolved formulas the required boxes transitively read.

    Only the unresolved formulas the required boxes actually read are followed,
    so an unrelated undeclared fact is not blamed for the refusal.
    """
    pending = [casilla_id for casilla_id in required if casilla_id in expression_by_target]
    reached: dict[CasillaId, str] = {}
    while pending:
        casilla_id = pending.pop()
        if casilla_id in reached:
            continue
        reached[casilla_id] = expression_by_target[casilla_id]
        pending.extend(
            target for target in expression_by_target if target not in reached and f'"{target}"' in reached[casilla_id]
        )
    return list(reached.values())


def _blocking_profile_fact_paths(
    revision: ModeloRevision,
    *,
    absent_profile_binding_ids: tuple[BindingId, ...],
    unresolved_expressions: list[str],
) -> list[str]:
    """Name the profile fact behind each absent binding an unresolved expression reads, once each."""
    bindings_by_id = revision_bindings_by_id(revision)
    fact_paths: list[str] = []
    for binding_id in absent_profile_binding_ids:
        if not any(f'"{binding_id}"' in expression for expression in unresolved_expressions):
            continue
        profile_key = selector_as_dict(bindings_by_id[binding_id]).get("profile_key")
        fact_path = profile_key if isinstance(profile_key, str) else str(binding_id)
        if fact_path not in fact_paths:
            fact_paths.append(fact_path)
    return fact_paths


def _raise_if_absent_profile_facts_block_projection(
    engine_result: RegistryCalculationResult,
    revision: ModeloRevision,
    *,
    absent_profile_binding_ids: tuple[BindingId, ...],
    declaration: _ProjectionDeclaration,
) -> None:
    """Refuse a projection a missing profile fact blocks, naming each fact the profile never declared.

    The result schema needs the base liquidable and quota boxes, so a profile
    fact their formulas read and the profile never declared leaves nothing
    honest to return. The refusal names those facts instead of the box alone.
    """
    required = (
        declaration.base_liquidable_general,
        declaration.pagos_fraccionados,
        declaration.cuota_integra_estatal,
        declaration.cuota_integra_autonomica,
        declaration.cuota_liquida_estatal,
        declaration.cuota_liquida_autonomica,
        declaration.cuota_resultante,
    )
    if all(casilla_id in engine_result.values for casilla_id in required):
        return
    fact_paths = _blocking_profile_fact_paths(
        revision,
        absent_profile_binding_ids=absent_profile_binding_ids,
        unresolved_expressions=_expressions_reached_from(
            _unresolved_formula_expressions(engine_result, revision), required
        ),
    )
    if not fact_paths:
        return
    raise ModeloProjectionError(
        translated_message="application.modelo.projection_words.profile_fact_missing",
        context={"profile_facts": ", ".join(fact_paths), "casilla_produced": False},
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


def _suffered_withholding_resolution(
    m100_snapshot: RegistrySnapshot,
    *,
    year: int,
    period: Period,
    bucket_id: str,
    profile: ModeloWorkProfile | None,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
) -> CalculationSourceResolution:
    """Resolve the suffered-withholding credits as the calculation's source mesh does.

    Only this family is resolved: the projection's activity income is the
    extrapolated Modelo 130 basis, which a ledger resolution would contradict.
    The expected-missing pass then marks every credit with no value
    unresolved, so the engine never reads it as zero.
    """
    resolver = RetencionSoportadaSourceResolver(ports=ports.retencion_soportada_ports)
    require_calculation_route_resolver("mesh", resolver)
    context = CalculationSourceContext(
        bucket_id=bucket_id,
        modelo=str(m100_snapshot.modelo.id),
        filing_year=year,
        period=period,
        revision=m100_snapshot.revision,
        profile=profile,
        operation=operation,
    )
    return add_expected_missing_binding_diagnostics(m100_snapshot.revision, resolver.resolve(context))


def _unresolved_bindings(
    resolution: CalculationSourceResolution,
    revision: ModeloRevision,
) -> tuple[ModeloProjectionUnresolvedBinding, ...]:
    """Report each unresolved binding once, by the diagnostic that names its box."""
    bindings_by_id = revision_bindings_by_id(revision)
    diagnostics = {
        diagnostic.binding_id: diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "unresolved_binding" and diagnostic.binding_id is not None
    }
    rows: list[ModeloProjectionUnresolvedBinding] = []
    for binding_id in resolution.unresolved_binding_ids:
        diagnostic = diagnostics.get(binding_id)
        if diagnostic is None:
            rows.append(
                ModeloProjectionUnresolvedBinding(
                    binding_id=binding_id,
                    casilla_id=sole_bound_casilla(revision, binding_id),
                    source_kind=str(bindings_by_id[binding_id].source),
                    reason="unresolved_binding",
                )
            )
            continue
        rows.append(
            ModeloProjectionUnresolvedBinding(
                binding_id=binding_id,
                casilla_id=diagnostic.casilla_id or sole_bound_casilla(revision, binding_id),
                source_kind=diagnostic.source_kind,
                reason=diagnostic.reason,
                note=diagnostic.fact.sentence if diagnostic.fact is not None else None,
                fact=diagnostic.fact,
            )
        )
    return tuple(rows)


def _unresolved_casillas(
    engine_result: RegistryCalculationResult,
    revision: ModeloRevision,
) -> tuple[ModeloProjectionUnresolvedCasilla, ...]:
    """Report every formula target the engine left without a value.

    The engine omits a formula target that reads an unresolved operand and
    reports a typed outcome for one it could not evaluate; every other formula
    target carries an observation. A target in neither is therefore omitted for
    an unresolved operand.
    """
    observed = {observation.casilla_id for observation in engine_result.observations}
    outcomes = {outcome.casilla_id: outcome for outcome in engine_result.unresolved_outcomes}
    rows = [
        ModeloProjectionUnresolvedCasilla(
            casilla_id=formula.target_casilla_id,
            reason=(
                str(outcomes[formula.target_casilla_id].reason)
                if formula.target_casilla_id in outcomes
                else UNRESOLVED_OPERAND_REASON
            ),
            formula_id=formula.id,
            legal_refs=tuple(formula.legal_refs),
            source_refs=tuple(formula.source_refs),
        )
        for formula in revision.formulas
        if formula.target_casilla_id not in observed
    ]
    return tuple(sorted(rows, key=lambda row: row.casilla_id))


def _projection_observations(
    engine_result: RegistryCalculationResult,
    *,
    source_casilla_ids: frozenset[CasillaId],
) -> tuple[ModeloProjectionCasillaObservation, ...]:
    """Return the computed boxes and the boxes the projection's sources resolved, in engine order."""
    return tuple(
        ModeloProjectionCasillaObservation(
            casilla_id=observation.casilla_id,
            value=observation.value,
            formula_id=observation.formula_id,
            legal_refs=tuple(observation.legal_refs),
            source_refs=tuple(observation.source_refs),
        )
        for observation in engine_result.observations
        if isinstance(observation.value, Decimal)
        and (observation.formula_id is not None or observation.casilla_id in source_casilla_ids)
    )


def _source_resolved_casilla_ids(
    resolution: CalculationSourceResolution,
    revision: ModeloRevision,
) -> frozenset[CasillaId]:
    """Return the boxes bound to a binding the projection's sources resolved."""
    bound = (sole_bound_casilla(revision, binding_id) for binding_id in resolution.binding_values)
    return frozenset(casilla_id for casilla_id in bound if casilla_id is not None)


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


def _calculate_projection(
    m100_snapshot: RegistrySnapshot,
    *,
    year: int,
    ccaa: str,
    inputs: Mapping[CasillaId, Decimal],
    bindings: Mapping[BindingId, Decimal],
    enum_bindings: Mapping[BindingId, str],
    relations: Mapping[RelationId, Decimal],
    date_bindings: Mapping[BindingId, date],
    boolean_bindings: Mapping[BindingId, bool],
    unresolved_binding_ids: tuple[BindingId, ...],
) -> RegistryCalculationResult:
    """Run the annual Modelo 100 engine, logging the channels it was given when the registry refuses them."""
    try:
        return calculate_registry_snapshot(
            m100_snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values=bindings,
            enum_binding_values=enum_bindings,
            relation_values=relations,
            unresolved_binding_ids=unresolved_binding_ids,
            date_binding_values=date_bindings or None,
            boolean_binding_values=boolean_bindings or None,
        )
    except RegistryValidationError:
        _LOG.exception(
            "modelo.project failed year=%s ccaa=%s inputs=%r bindings=%r "
            "enum_bindings=%r relations=%r date_bindings=%r",
            year,
            ccaa,
            inputs,
            bindings,
            enum_bindings,
            relations,
            date_bindings,
        )
        raise


def _projection_service_result(
    *,
    year: int,
    ccaa: str,
    annual: _M130AnnualProjection,
    engine_result: RegistryCalculationResult,
    credits: CalculationSourceResolution,
    revision: ModeloRevision,
    declaration: _ProjectionDeclaration,
) -> ModeloProjectServiceResult:
    """Assemble the projection result from the annual M130 figures and the engine's observations."""
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
        casilla_observations=_projection_observations(
            engine_result,
            source_casilla_ids=_source_resolved_casilla_ids(credits, revision),
        ),
        m100_projection=_m100_projection_result(engine_result.values, declaration=declaration),
        unresolved_bindings=_unresolved_bindings(credits, revision),
        unresolved_casillas=_unresolved_casillas(engine_result, revision),
    )


def _binding_overrides_with_region(
    binding_overrides: Mapping[BindingId, str] | None,
    *,
    ccaa: str | None,
    revision: ModeloRevision,
) -> Mapping[BindingId, str] | None:
    """Make a region the caller named an override of the profile's, as the caller's own value.

    Without it the profile's tax residence would win over the region the
    request names while the result still reported the requested one. A
    binding override the caller names for the region itself stays.
    """
    if ccaa is None:
        return binding_overrides
    region_binding = _binding_id(_REGION_BINDING_ID, surface="project modelo 100 region binding id")
    if region_binding not in {binding.id for binding in revision.bindings}:
        return binding_overrides
    overrides: dict[BindingId, str] = {region_binding: ccaa}
    overrides.update(binding_overrides or {})
    return overrides


def _projection_region(ccaa: str | None, *, profile: ModeloWorkProfile | None) -> str:
    """The region the projection is made for: the caller's own, else the profile's tax residence.

    Refuses when neither states one. The region selects the autonomous-community
    scale of the tax, so it is the filer's to state and is never defaulted.
    """
    if ccaa is not None:
        return ccaa
    stated = fact_value(None if profile is None else profile.record, "tax_residence.ccaa")
    if stated is not None and stated.strip():
        return stated
    raise ModeloProjectRegionUnstatedError(
        translated_message="application.modelo.projection_words.region_unstated",
        precondition_verdict=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.project",
            scenario_id="modelo.project.region.unstated",
            evidence_id="modelo.project.region",
            evidence_values={"profile_region_stated": False},
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ).verdict,
    )


def project_modelo_100_from_m130(
    *,
    year: int,
    ccaa: str | None,
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

    ``ccaa`` is the region the projection is made for. A caller that omits it
    gets the region the exact profile's tax residence states, and a profile
    that states none is refused with :class:`ModeloProjectRegionUnstatedError`.
    """
    declaration = _registry_projection_declaration(year, operation=operation)
    profile = load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context())
    region = _projection_region(ccaa, profile=profile)
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
        _binding_overrides_with_region(binding_overrides, ccaa=ccaa, revision=m100_snapshot.revision),
        m100_snapshot.revision,
    )
    reject_caller_overrides_of_source_bindings(
        revision=m100_snapshot.revision,
        owned_sources=_PROJECTION_SOURCE_OWNED_KINDS,
        caller_binding_values=extra_bindings,
        caller_casilla_inputs=extra_inputs,
        caller_enum_binding_values=extra_enum_bindings,
        subject_leaf_key="modelo.project",
    )

    credits = _suffered_withholding_resolution(
        m100_snapshot,
        year=year,
        period=Period.from_year_and_code(year, declaration.target_period),
        bucket_id=bucket_id,
        profile=profile,
        ports=ports,
        operation=operation,
    )

    m100_inputs: dict[CasillaId, Decimal] = {
        declaration.rendimiento_neto_projected: annual.projected_rendimiento_neto,
        # A bound box reads its binding through the input channel, as on the calculation path.
        **resolve_available_bound_inputs_by_casilla_id(m100_snapshot.revision, credits.binding_values),
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
        _verb_baseline_projection_bindings(region, m100_snapshot.revision)
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

    merged_bindings = {
        **verb_baseline_bindings,
        **profile_decimal_bindings,
        **credits.binding_values,
        **extra_bindings,
    }
    merged_enum_bindings = {**verb_baseline_enum_bindings, **profile_enum_bindings, **extra_enum_bindings}
    merged_date_bindings = dict(profile_date_bindings)
    merged_boolean_bindings = {**verb_baseline_boolean_bindings, **profile_boolean_bindings}
    _apply_zero_maritime_projection_default(declared_binding_ids, merged_bindings, merged_boolean_bindings)
    absent_profile_binding_ids = _absent_profile_binding_ids(
        m100_snapshot.revision,
        supplied={
            *merged_bindings,
            *merged_enum_bindings,
            *merged_date_bindings,
            *merged_boolean_bindings,
            *credits.unresolved_binding_ids,
        },
    )

    engine_result = _calculate_projection(
        m100_snapshot,
        year=year,
        ccaa=region,
        inputs=m100_inputs,
        bindings=merged_bindings,
        enum_bindings=merged_enum_bindings,
        relations=m100_relations,
        date_bindings=merged_date_bindings,
        boolean_bindings=merged_boolean_bindings,
        unresolved_binding_ids=(*credits.unresolved_binding_ids, *absent_profile_binding_ids),
    )
    _raise_if_absent_profile_facts_block_projection(
        engine_result,
        m100_snapshot.revision,
        absent_profile_binding_ids=absent_profile_binding_ids,
        declaration=declaration,
    )
    return _projection_service_result(
        year=year,
        ccaa=region,
        annual=annual,
        engine_result=engine_result,
        credits=credits,
        revision=m100_snapshot.revision,
        declaration=declaration,
    )


__all__ = [
    "UNRESOLVED_OPERAND_REASON",
    "ModeloProjectInvalidDecimalOverrideError",
    "ModeloProjectM100Projection",
    "ModeloProjectM130Accumulated",
    "ModeloProjectNoM130RevisionsError",
    "ModeloProjectNoM130UnitsError",
    "ModeloProjectRegionUnstatedError",
    "ModeloProjectServiceResult",
    "ModeloProjectionCasillaObservation",
    "ModeloProjectionError",
    "ModeloProjectionUnresolvedBinding",
    "ModeloProjectionUnresolvedCasilla",
    "RegistrySnapshotError",
    "RegistryValidationError",
    "modelo_projection_available",
    "project_modelo_100_from_m130",
]

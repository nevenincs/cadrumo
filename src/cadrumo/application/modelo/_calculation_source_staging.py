"""Staged source-resolution helpers for bucket aggregation calculations.

These helpers let source resolvers that depend on current-year registry values
run the registry engine once without persisting a calculation revision. The
staged values feed prorrata and bienes-inversion regularizacion resolvers and
add diagnostics for source kinds that would otherwise default to a silent zero.

See Also:
    :func:`~application.modelo._calculation_actions.calculate_modelo_revision_from_bucket_aggregation`
        Bucket-backed calculate path that composes these staging helpers.
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh envelope merged and diagnosed by this module.
    :func:`~application.aggregation.merge_source_resolutions`
        Merge primitive used after staged prorrata and bienes-inversion
        resolutions are produced.
    :func:`~application.aggregation.collect_unhandled_source_diagnostics`
        Diagnostic sweep used to surface declared-but-unhandled source kinds.
    :class:`~application.calculations.ProrrataRegularizacionSourceResolver`
        Resolver fed by materialised current-year prorrata registry values.
    :class:`~application.calculations.BienesInversionRegularizacionSourceResolver`
        Dependent capital-goods resolver composed with the staged prorrata pass.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry engine invoked without persistence to materialise current-year
        casilla values for staged resolvers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry import (
    IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS,
    BindingId,
    CasillaId,
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
    RelationId,
    calculate_registry_snapshot,
    casillas_by_id,
    initial_value_casilla_ids,
)
from ...domain.modelos import WorkUnit
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
)
from ..calculations import BienesInversionRegularizacionSourceResolver, ProrrataRegularizacionSourceResolver
from ._calculation_modelo_adjustments import _m131_objective_estimation_data_base_inputs
from ._calculation_resolution import resolve_calculation_inputs as _resolve_calculation_inputs


@dataclass(frozen=True, slots=True)
class SourceResolutionRegistryValues:
    """Registry-engine values materialised for a staged source resolver."""

    values: Mapping[CasillaId, Decimal]
    initial_casilla_ids: frozenset[CasillaId]
    unresolved_casilla_ids: tuple[CasillaId, ...] = ()
    missing_casilla_ids: tuple[CasillaId, ...] = ()

    def select(self, casilla_ids: Iterable[CasillaId]) -> SourceResolutionRegistryValues:
        """Return a narrowed view for one source resolver's declared dependencies."""
        ordered = tuple(casilla_ids)
        selected = {casilla_id: self.values[casilla_id] for casilla_id in ordered if casilla_id in self.values}
        unresolved = frozenset(self.unresolved_casilla_ids)
        return SourceResolutionRegistryValues(
            values=MappingProxyType(selected),
            initial_casilla_ids=frozenset(
                casilla_id for casilla_id in ordered if casilla_id in self.initial_casilla_ids
            ),
            unresolved_casilla_ids=tuple(casilla_id for casilla_id in ordered if casilla_id in unresolved),
            missing_casilla_ids=tuple(casilla_id for casilla_id in ordered if casilla_id not in selected),
        )


_PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS: tuple[CasillaId, ...] = (
    "iva.cuota-deducible-total",
    "iva.prorrata-volumen-con-derecho",
    "iva.prorrata-volumen-total",
    "iva.prorrata-porcentaje",
)


def resolve_prorrata_regularizacion_sources(
    *,
    registry_snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    context: CalculationSourceContext,
    source_resolution: CalculationSourceResolution,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    binding_values: Mapping[BindingId, Decimal] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    date_binding_values: Mapping[BindingId, date] | None,
    relation_values: Mapping[RelationId, Decimal] | None,
    filing_period_date: date | None,
) -> CalculationSourceResolution:
    """Resolve prorrata and dependent capital-goods staged mesh sources.

    Args:
        registry_snapshot: The target revision's :class:`RegistrySnapshot`,
            consulted to check whether the revision declares a
            ``prorrata_regularizacion``-sourced binding at all.
        work_unit: The :class:`WorkUnit` addressing the target filing,
            threaded to the staged registry engine run.
        context: The :class:`CalculationSourceContext` the staged prorrata
            and bienes-inversion resolvers resolve against.
        source_resolution: The upstream :class:`CalculationSourceResolution`
            mesh envelope the staged resolutions are merged into.
        casilla_inputs: Operator- and backend-supplied casilla values that
            seed the staged registry run.
        text_casilla_inputs: Text-typed casilla inputs seeding the staged run.
        binding_values: Caller-supplied Decimal binding values overlaid on the
            source resolution's own binding values.
        enum_binding_values: Caller-supplied enum (string) binding values
            overlaid on the source resolution's enum binding values.
        date_binding_values: Caller-supplied date binding values overlaid on
            the source resolution's date binding values.
        relation_values: Caller-supplied relation values overlaid on the
            source resolution's relation values.
        filing_period_date: The filing period date used for period-sensitive
            resolution.

    Returns:
        The source resolution unchanged when the revision declares no
        ``prorrata_regularizacion`` binding, otherwise the source resolution
        merged with the staged prorrata and bienes-inversion resolutions.
    """
    snapshot_revision = registry_snapshot.revision
    if not any(binding.source is BindingSourceKind.PRORRATA_REGULARIZACION for binding in snapshot_revision.bindings):
        return source_resolution

    caller_binding_values = dict(binding_values or {})
    caller_relation_values = dict(relation_values or {})
    materialised = materialise_prorrata_regularizacion_current_year_values(
        registry_snapshot=registry_snapshot,
        work_unit=work_unit,
        casilla_inputs=casilla_inputs or {},
        backend_casilla_inputs=source_resolution.bound_inputs_by_casilla_id,
        binding_values={**dict(source_resolution.binding_values), **caller_binding_values},
        enum_binding_values={**dict(source_resolution.enum_binding_values), **dict(enum_binding_values or {})},
        date_binding_values={**dict(source_resolution.date_binding_values), **dict(date_binding_values or {})},
        text_casilla_inputs=text_casilla_inputs,
        relation_values={**dict(source_resolution.relation_values), **caller_relation_values},
        unresolved_relation_ids=tuple(
            relation_id
            for relation_id in source_resolution.unresolved_relation_ids
            if relation_id not in caller_relation_values
        ),
        unresolved_binding_ids=tuple(
            binding_id
            for binding_id in source_resolution.unresolved_binding_ids
            if binding_id not in caller_binding_values
        ),
        filing_period_date=filing_period_date,
    )
    prorrata_resolution = ProrrataRegularizacionSourceResolver(
        current_year_values=materialised.values,
        missing_current_year_casilla_ids=materialised.missing_casilla_ids,
        unresolved_current_year_casilla_ids=materialised.unresolved_casilla_ids,
        registry_snapshot=registry_snapshot,
    ).resolve(context)
    bienes_resolution = BienesInversionRegularizacionSourceResolver(
        current_year_values=materialised.values,
        missing_current_year_casilla_ids=materialised.missing_casilla_ids,
        unresolved_current_year_casilla_ids=materialised.unresolved_casilla_ids,
    ).resolve(context)
    return merge_source_resolutions((source_resolution, prorrata_resolution, bienes_resolution))


def materialise_prorrata_regularizacion_current_year_values(
    *,
    registry_snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    filing_period_date: date | None = None,
) -> SourceResolutionRegistryValues:
    """Materialise the current-year values needed by ``prorrata_regularizacion``.

    Args:
        registry_snapshot: The target revision's :class:`RegistrySnapshot`,
            used to resolve the current-year casilla ids through the
            registry engine.
        work_unit: The :class:`WorkUnit` addressing the target filing,
            threaded to the staged registry engine run.
        casilla_inputs: Operator- and backend-supplied casilla values that
            seed the staged registry run.
        backend_casilla_inputs: Casilla values already bound by the backend
            source resolution, seeded into the staged run.
        binding_values: Decimal binding values overlaid on the staged run.
        enum_binding_values: Enum (string) binding values for the staged run.
        date_binding_values: Date binding values for the staged run.
        text_casilla_inputs: Text-typed casilla inputs for the staged run.
        relation_values: Relation values for the staged run.
        unresolved_relation_ids: Relation ids still unresolved after the
            backend pass, propagated so the engine does not treat them as zero.
        unresolved_binding_ids: Binding ids still unresolved after the backend
            pass, propagated so the engine does not treat them as zero.
        filing_period_date: The filing period date used for period-sensitive
            resolution.

    Returns:
        The narrowed :class:`SourceResolutionRegistryValues` for the four
        prorrata current-year casillas, or an empty materialisation when the
        revision does not declare all of them.
    """
    revision = registry_snapshot.revision
    revision_casillas = casillas_by_id(revision)
    if any(casilla_id not in revision_casillas for casilla_id in _PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS):
        return SourceResolutionRegistryValues(
            values=MappingProxyType({}),
            initial_casilla_ids=initial_value_casilla_ids(revision),
            missing_casilla_ids=_PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS,
        )
    materialised = materialise_registry_values_for_source_resolution(
        registry_snapshot=registry_snapshot,
        work_unit=work_unit,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        date_binding_values=date_binding_values,
        text_casilla_inputs=text_casilla_inputs,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        staging_binding_defaults={
            binding_id: Decimal("0.00")
            for binding_id in IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS
            if binding_id not in binding_values
        },
        filing_period_date=filing_period_date,
    )
    return materialised.select(_PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS)


def materialise_registry_values_for_source_resolution(
    *,
    registry_snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    staging_binding_defaults: Mapping[BindingId, Decimal] | None = None,
    filing_period_date: date | None = None,
) -> SourceResolutionRegistryValues:
    """Run the registry engine without persistence so staged resolvers can read current values.

    ``registry_snapshot`` is the compiled :class:`RegistrySnapshot` the engine
    evaluates the staged current-year values against.
    """
    revision = registry_snapshot.revision
    effective_binding_values = {**dict(staging_binding_defaults or {}), **dict(binding_values)}
    effective_unresolved_binding_ids = tuple(
        binding_id for binding_id in unresolved_binding_ids if binding_id not in effective_binding_values
    )
    resolved_backend_inputs = {
        **_m131_objective_estimation_data_base_inputs(
            work_unit=work_unit,
            revision=revision,
            binding_values=effective_binding_values,
        ),
        **dict(backend_casilla_inputs or {}),
    }
    channel_inputs = _resolve_calculation_inputs(
        revision=revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        backend_casilla_inputs=resolved_backend_inputs,
        resolved_bindings=effective_binding_values,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
    )
    resolved_inputs = channel_inputs.casilla_inputs
    resolved_text_inputs = channel_inputs.text_casilla_inputs
    engine_result = calculate_registry_snapshot(
        registry_snapshot,
        inputs=resolved_inputs,
        text_inputs=resolved_text_inputs or None,
        date_context={"filing_period": filing_period_date} if filing_period_date is not None else {},
        binding_values=effective_binding_values,
        enum_binding_values=enum_binding_values or {},
        relation_values=relation_values or {},
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=effective_unresolved_binding_ids,
        date_binding_values=date_binding_values or None,
    )
    return SourceResolutionRegistryValues(
        values=MappingProxyType(dict(engine_result.values)),
        initial_casilla_ids=initial_value_casilla_ids(revision),
        unresolved_casilla_ids=tuple(sorted(outcome.casilla_id for outcome in engine_result.unresolved_outcomes)),
    )


def add_unhandled_source_diagnostics(
    revision: ModeloRevision,
    source_resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Add advisories for declared binding sources not handled by the mesh.

    ``revision`` is the compiled :class:`ModeloRevision` whose declared binding
    sources are checked against the mesh's owned-source set.
    """
    pre_mesh_handled = frozenset(
        {
            BindingSourceKind.PROFILE,
            BindingSourceKind.BORRADOR,
            BindingSourceKind.IVA_WALLET_DECISION,
        },
    )
    diagnostics = collect_unhandled_source_diagnostics(
        revision,
        handled_sources=frozenset(source_resolution.owned_sources) | pre_mesh_handled,
        manual_sources=frozenset({"manual_input"}),
    )
    if not diagnostics:
        return source_resolution
    return source_resolution.model_copy(update={"diagnostics": source_resolution.diagnostics + diagnostics})


def add_expected_missing_binding_diagnostics(
    revision: ModeloRevision,
    source_resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Mark present-source, no-value binding gaps unresolved instead of silent.

    ``revision`` is the compiled :class:`ModeloRevision` whose bound casillas
    are checked for present-source, no-value binding gaps.
    """
    missing = expected_but_missing_binding_ids(
        revision,
        owned_sources=frozenset(source_resolution.owned_sources),
        resolved_binding_values=source_resolution.binding_values,
    )
    if not missing:
        return source_resolution
    unresolved_binding_ids = tuple(
        sorted(
            {
                *source_resolution.unresolved_binding_ids,
                *(binding_id for binding_id, _casilla_id, _source in missing),
            }
        )
    )
    diagnostics = tuple(
        CalculationSourceDiagnostic(
            reason="unresolved_binding",
            source_kind=str(source),
            binding_id=binding_id,
            casilla_id=casilla_id,
            message=(
                f"binding {binding_id!r} (casilla {casilla_id!r}) declares present source "
                f"{source!r} whose resolver produced no value; the bound casilla would otherwise "
                "default to a silent zero. Supply the source records before filing."
            ),
        )
        for binding_id, casilla_id, source in missing
    )
    return source_resolution.model_copy(
        update={
            "unresolved_binding_ids": unresolved_binding_ids,
            "diagnostics": source_resolution.diagnostics + diagnostics,
        },
    )


def expected_but_missing_binding_ids(
    revision: ModeloRevision,
    *,
    owned_sources: frozenset[BindingSourceKind],
    resolved_binding_values: Mapping[BindingId, Decimal],
) -> tuple[tuple[BindingId, CasillaId, BindingSourceKind], ...]:
    """Return direct bound bindings whose present source resolved no value.

    ``revision`` is the compiled :class:`ModeloRevision` whose bindings and
    casillas are scanned for present-source, no-value gaps.
    """
    non_silent_sources = frozenset({"previous_filing", "relation_prefill", "manual_input"})
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    missing: list[tuple[BindingId, CasillaId, BindingSourceKind]] = []
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None:
            continue
        source = binding.source
        if str(source) in non_silent_sources or source not in owned_sources or binding.id in resolved_binding_values:
            continue
        missing.append((binding.id, casilla.id, source))
    return tuple(missing)

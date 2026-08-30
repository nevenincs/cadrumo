"""Application-owned binding input resolution for modelo calculations.

This module prepares binding, enum, and informational inputs for one
:class:`RegistrySnapshot` before the registry
engine evaluates its :class:`ModeloRevision`.
Profile, backend mesh, borrador, and caller values are normalised as
:class:`~cadrumo.application.aggregation.CalculationSourceResolution` tiers, then
the calculation assembly layer overlays them by precedence: profile, backend
mesh, borrador, and finally caller overrides.

Projecting resolved binding values onto bound
:class:`~cadrumo.core.CasillaId` inputs is registry-owned rather than an
application concern: see
:func:`~cadrumo.domain.calculations.registry.resolve_available_bound_inputs_by_casilla_id`.
Completeness and unrouted-input concerns remain advisory or verify-gate
responsibilities rather than a second projection contract.

See Also:
    :mod:`~cadrumo.application.modelo._calculation_resolution`:
        Merges these tiers and builds the canonical engine input maps.
    :mod:`~cadrumo.application.modelo.profile_binding`:
        Resolves profile-sourced bindings into decimal, enum, and date channels.
    :mod:`~cadrumo.application.modelo.borrador_binding`:
        Resolves Modelo 100 borrador snapshots as a precedence tier.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind as _BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core import Period as _Period
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
)
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.modelos.errors import ModeloError
from ..aggregation import CalculationSourceResolution
from .borrador_binding import Modelo100BorradorSourceResolver
from .calculation_route import require_calculation_route_resolver

if TYPE_CHECKING:
    from ..live.borrador_100 import Borrador100SnapshotRepository
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)


def resolve_borrador_source_tier(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    filing_year: int,
    period: _Period,
    borrador_snapshot_id: str | None,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
) -> CalculationSourceResolution:
    """Resolve the borrador precedence tier as a source-mesh resolution.

    The :class:`RegistrySnapshot` supplies
    the revision and modelo identity used to resolve the borrador source through
    the source mesh; the returned
    :class:`~cadrumo.application.aggregation.CalculationSourceResolution` carries
    the typed ``borrador_provenance`` (snapshot id + sourced-binding trace) the
    persistence boundary consumes.

    Caller-supplied :class:`~cadrumo.domain.calculations.registry.BindingId` values
    remain higher precedence than the snapshot, so the resolver receives both
    decimal and enum caller channels and omits any borrador value already owned
    by the caller.

    See Also:
        :class:`~cadrumo.application.aggregation.CalculationSourceResolution`:
            The shared carrier used by the precedence overlay.
        :class:`~cadrumo.application.live.Borrador100SnapshotRepository`:
            Loads the optional captured snapshot when a borrador id is supplied.
    """
    return _resolve_borrador_bindings_for_calculation(
        bucket_id=bucket_id,
        modelo=snapshot.modelo.id,
        filing_year=filing_year,
        period=period,
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        registry_snapshot=snapshot,
        snapshot_repository=borrador_snapshot_repository,
    )


def resolve_profile_source_tier(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    borrador_resolution: CalculationSourceResolution,
    backend_binding_values: Mapping[BindingId, Decimal],
) -> CalculationSourceResolution:
    """Resolve the profile precedence tier as a source-mesh resolution.

    The :class:`RegistrySnapshot` identifies
    the revision whose ``source = "profile"`` bindings are enrolled through the
    source mesh. Profile is the LOWEST precedence tier, so every binding the
    caller, borrador, or mesh backend already supplied is excluded here (the
    profile resolver never overrides a higher tier).

    The ``borrador_resolution`` and backend values are passed only as ownership
    exclusions. They do not change profile facts; they prevent the profile tier
    from claiming a :class:`~cadrumo.domain.calculations.registry.BindingId` that a
    higher-precedence source already supplied.

    See Also:
        :class:`~cadrumo.application.aggregation.ProfileSourceResolver`:
            Source resolver that reads the stored user profile facts.
        :func:`~cadrumo.application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
            Places this profile tier below backend, borrador, and caller tiers.

    Returns:
        A :class:`~cadrumo.application.aggregation.CalculationSourceResolution`
        carrying the profile-owned bindings not already claimed by
        higher-precedence tiers.
    """
    from ..aggregation import CalculationSourceContext, ProfileSourceResolver

    caller_owned = (
        set(caller_binding_values)
        | set(caller_enum_binding_values)
        | set(borrador_resolution.binding_values)
        | set(borrador_resolution.enum_binding_values)
        | set(backend_binding_values)
    )
    resolver = ProfileSourceResolver(
        caller_binding_ids=caller_owned,
        registry_snapshot=snapshot,
    )
    require_calculation_route_resolver("pre_mesh", resolver)
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=snapshot.modelo.id,
            filing_year=snapshot.filing_year,
            period=_Period.from_year_and_code(snapshot.filing_year, snapshot.period),
            revision=snapshot.revision,
        ),
    )


def reject_binding_channel_mismatch(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str],
) -> None:
    """Reject binding values supplied on the wrong engine channel.

    The :class:`ModeloRevision` determines
    channel ownership from formula consumption: enum dispatch bindings must
    arrive through
    ``enum_binding_values``; decimal operands must arrive through
    ``binding_values``. A mismatch raises
    :class:`~ModeloError` before the engine sees an
    apparently missing binding.

    See Also:
        :func:`~cadrumo.domain.calculations.registry.enum_consumed_binding_ids`:
            Identifies bindings consumed by enum-dispatch formulas.
    """
    _reject_binding_channel_mismatch(revision, binding_values, enum_binding_values)


def lift_previous_filing_casilla_overrides_to_bindings(
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    """Promote eligible previous-filing casilla overrides into binding values.

    The :class:`ModeloRevision` supplies the
    bound casilla and binding metadata. A caller may supply a
    :class:`~cadrumo.core.CasillaId` override for a bound
    casilla whose binding source is ``previous_filing`` when no resolver-produced
    binding value exists. This helper mirrors that override onto the matching
    :class:`~cadrumo.domain.calculations.registry.BindingId` so the registry
    engine's bound-input consistency guards see the same source of truth in both
    channels. Existing resolved bindings are never overwritten.

    See Also:
        :func:`~cadrumo.application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
            Calls this after the precedence overlay settles.
    """
    return _lift_previous_filing_casilla_overrides_to_bindings(revision, casilla_inputs, resolved_bindings)


@dataclass(frozen=True, slots=True)
class DeclarationPeriodInputs:
    """Work-unit metadata projected onto its two typed engine channels.

    ``casilla_inputs`` carries the int-family ``filing_year`` role on the Decimal
    channel; ``text_casilla_inputs`` carries the string-family ``filing_period``
    role, whose registry ``data_type = "period_code"`` binds it to the typed
    text-scalar channel and its ``period_code`` validator.
    """

    casilla_inputs: dict[CasillaId, Decimal] = field(default_factory=dict)
    text_casilla_inputs: dict[CasillaId, str] = field(default_factory=dict)


def resolve_declaration_period_inputs(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: _Period,
) -> DeclarationPeriodInputs:
    """Resolve work-unit period metadata into informational casilla inputs.

    The :class:`ModeloRevision` supplies the
    informational casillas eligible for metadata projection. Only casillas with
    unique ``filing_year`` or ``filing_period`` semantic roles are populated. The
    ``filing_year`` role lands as a :class:`~decimal.Decimal` and the
    ``filing_period`` role as the canonical :class:`~cadrumo.core.Period`
    registry token (``"1T"``, ``"EXT-1T"``), which is the form AEAT accepts and
    the only representation total over every declared period. A
    non-informational role target raises
    :class:`~ModeloError`.

    See Also:
        :func:`~cadrumo.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`:
            Enforces that each populated semantic role resolves to one casilla.
    """
    return _resolve_declaration_period_inputs(revision, filing_year=filing_year, period=period)


def _reject_binding_channel_mismatch(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str],
) -> None:
    """Refuse bindings supplied through the wrong engine channel."""
    enum_consumed = enum_consumed_binding_ids(revision)
    misrouted_to_decimal = sorted(set(binding_values) & enum_consumed)
    if misrouted_to_decimal:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={
                "misrouted_binding_ids": ", ".join(str(b) for b in misrouted_to_decimal),
                "expected_input_channel": "enum",
                "supplied_input_channel": "decimal",
            },
        )
    misrouted_to_enum = sorted(set(enum_binding_values) & {b.id for b in revision.bindings} - enum_consumed)
    misrouted_to_enum = [
        binding_id for binding_id in misrouted_to_enum if _binding_is_formula_consumed(revision, binding_id)
    ]
    if misrouted_to_enum:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={
                "misrouted_binding_ids": ", ".join(str(b) for b in misrouted_to_enum),
                "expected_input_channel": "decimal",
                "supplied_input_channel": "enum",
            },
        )


def _binding_is_formula_consumed(revision: ModeloRevision, binding_id: BindingId) -> bool:
    """Return whether any formula expression references ``binding_id``."""
    return any(binding_id in expression_binding_refs(formula.expression) for formula in revision.formulas)


def _resolve_borrador_bindings_for_calculation(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: _Period,
    borrador_snapshot_id: str | None,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None,
) -> CalculationSourceResolution:
    """Resolve the optional borrador snapshot, returning its resolution directly.

    The returned
    :class:`~cadrumo.application.aggregation.CalculationSourceResolution` carries
    the typed ``borrador_provenance`` (snapshot id + sourced-binding trace) the
    persistence boundary consumes.
    """
    from ..aggregation import CalculationSourceContext

    resolver = Modelo100BorradorSourceResolver(
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
    )
    require_calculation_route_resolver("pre_mesh", resolver)
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision=registry_snapshot.revision,
        ),
    )


def _lift_previous_filing_casilla_overrides_to_bindings(
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    """Promote operator casilla overrides for previous-filing-bound casillas into bindings."""
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    revision_casillas_by_id = casillas_by_id(revision)
    promoted: dict[BindingId, Decimal] = {}
    for casilla_id, value in casilla_inputs.items():
        casilla = revision_casillas_by_id.get(casilla_id)
        if casilla is None or casilla.input_kind != InputKind.BOUND or not casilla.binding:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None or binding.source != _BindingSourceKind.PREVIOUS_FILING:
            continue
        if casilla.binding in resolved_bindings:
            continue
        promoted[casilla.binding] = value
    return {**resolved_bindings, **promoted}


def _resolve_declaration_period_inputs(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: _Period,
) -> DeclarationPeriodInputs:
    """Return informational-casilla inputs sourced from work-unit metadata."""
    resolved: dict[CasillaId, Decimal] = {}
    filing_year_id = _informational_semantic_role_casilla_id(revision, "filing_year")
    if filing_year_id is not None:
        resolved[filing_year_id] = Decimal(filing_year)

    resolved_text: dict[CasillaId, str] = {}
    filing_period_id = _informational_semantic_role_casilla_id(revision, "filing_period")
    if filing_period_id is not None:
        resolved_text[filing_period_id] = period.registry_token
    return DeclarationPeriodInputs(casilla_inputs=resolved, text_casilla_inputs=resolved_text)


def _informational_semantic_role_casilla_id(revision: ModeloRevision, semantic_role: str) -> CasillaId | None:
    try:
        casilla_id = casilla_id_for_unique_revision_semantic_role(revision, semantic_role)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc
    if casilla_id is None:
        return None
    casilla = casillas_by_id(revision).get(casilla_id)
    if casilla is None or casilla.input_kind != InputKind.INFORMATIONAL:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={
                "semantic_role": semantic_role,
                "casilla_id": casilla_id,
                "casilla_informational": False,
            },
        )
    return casilla_id


__all__ = [
    "DeclarationPeriodInputs",
    "lift_previous_filing_casilla_overrides_to_bindings",
    "reject_binding_channel_mismatch",
    "resolve_borrador_source_tier",
    "resolve_declaration_period_inputs",
    "resolve_profile_source_tier",
]

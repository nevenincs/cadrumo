"""Application-owned binding input resolution for modelo calculations.

This module prepares binding, enum, and informational inputs for one
:class:`RegistrySnapshot` before the registry engine evaluates its
:class:`ModeloRevision`. Profile, backend mesh, borrador, and caller values are
normalised as :class:`aeat.application.aggregation.CalculationSourceResolution`
tiers, then the calculation assembly layer overlays them by precedence:
profile, backend mesh, borrador, and finally caller overrides.

The module also owns the application-specific partial projection from available
binding values to :class:`CasillaId` inputs. That differs from the domain
registry's strict bound-input projection: live calculate paths may carry absent
optional bindings while still projecting every value that did resolve.

See Also:
    :mod:`aeat.application.modelo._calculation_resolution`:
        Merges these tiers and builds the canonical engine input maps.
    :func:`aeat.domain.calculations.registry.resolve_bound_inputs_by_casilla_id`:
        Strict registry projection that requires every bound fact to be present.
    :mod:`aeat.application.modelo._profile_binding`:
        Resolves profile-sourced bindings into decimal, enum, and date channels.
    :mod:`aeat.application.modelo._borrador_binding`:
        Resolves Modelo 100 borrador snapshots as a precedence tier.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Period as _Period
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
    casillas_by_id,
    enum_consumed_binding_ids,
    expression_binding_refs,
    resolve_bound_casilla_binding_value,
)
from ...domain.modelos._errors import ModeloError
from ..aggregation._source_mesh import CalculationSourceResolution
from ..live import Borrador100SnapshotRepository
from ._borrador_binding import Modelo100BorradorSourceResolver
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

    The :class:`RegistrySnapshot` supplies the revision and modelo identity used
    to resolve the borrador source through the source mesh; the returned
    :class:`aeat.application.aggregation.CalculationSourceResolution` carries
    the typed ``borrador_provenance`` (snapshot id + sourced-binding trace) the
    persistence boundary consumes.

    Caller-supplied :class:`BindingId` values remain higher precedence than the
    snapshot, so the resolver receives both decimal and enum caller channels and
    omits any borrador value already owned by the caller.

    See Also:
        :class:`aeat.application.aggregation.CalculationSourceResolution`:
            The shared carrier used by the precedence overlay.
        :class:`aeat.application.live.Borrador100SnapshotRepository`:
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

    The :class:`RegistrySnapshot` identifies the revision whose
    ``source = "profile"`` bindings are enrolled through the source mesh. Profile
    is the LOWEST precedence tier, so every binding the caller, borrador, or mesh
    backend already supplied is excluded here (the profile resolver never
    overrides a higher tier).

    The ``borrador_resolution`` and backend values are passed only as ownership
    exclusions. They do not change profile facts; they prevent the profile tier
    from claiming a :class:`BindingId` that a higher-precedence source already
    supplied.

    See Also:
        :class:`aeat.application.aggregation.ProfileSourceResolver`:
            Source resolver that reads the stored user profile facts.
        :func:`aeat.application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
            Places this profile tier below backend, borrador, and caller tiers.

    Returns:
        A :class:`CalculationSourceResolution` carrying the profile-owned
        bindings not already claimed by higher-precedence tiers.
    """
    from ..aggregation import CalculationSourceContext, ProfileSourceResolver

    caller_owned = (
        set(caller_binding_values)
        | set(caller_enum_binding_values)
        | set(borrador_resolution.binding_values)
        | set(borrador_resolution.enum_binding_values)
        | set(backend_binding_values)
    )
    return ProfileSourceResolver(
        caller_binding_ids=caller_owned,
        registry_snapshot=snapshot,
    ).resolve(
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

    The :class:`ModeloRevision` determines channel ownership from formula
    consumption: enum dispatch bindings must arrive through
    ``enum_binding_values``; decimal operands must arrive through
    ``binding_values``. A mismatch raises :class:`ModeloError` before the engine
    sees an apparently missing binding.

    See Also:
        :func:`aeat.domain.calculations.registry.enum_consumed_binding_ids`:
            Identifies bindings consumed by enum-dispatch formulas.
    """
    _reject_binding_channel_mismatch(revision, binding_values, enum_binding_values)


def lift_previous_filing_casilla_overrides_to_bindings(
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    """Promote eligible previous-filing casilla overrides into binding values.

    The :class:`ModeloRevision` supplies the bound casilla and binding metadata.
    A caller may supply a :class:`CasillaId` override for a bound casilla whose
    binding source is ``previous_filing`` when no resolver-produced binding value
    exists. This helper mirrors that override onto the matching :class:`BindingId`
    so the registry engine's bound-input consistency guards see the same source
    of truth in both channels. Existing resolved bindings are never overwritten.

    See Also:
        :func:`aeat.application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
            Calls this after the precedence overlay settles.
    """
    return _lift_previous_filing_casilla_overrides_to_bindings(revision, casilla_inputs, resolved_bindings)


def resolve_declaration_period_inputs(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: _Period,
) -> dict[CasillaId, Decimal]:
    """Resolve work-unit period metadata into informational casilla inputs.

    The :class:`ModeloRevision` supplies the informational casillas eligible for
    metadata projection. Only casillas with unique ``filing_year`` or
    ``filing_period`` semantic roles are populated. The
    :class:`aeat.core.Period` registry token is mapped to the ordinal expected
    by the registry snapshot; unsupported tokens or non-informational role
    targets raise :class:`ModeloError`.

    See Also:
        :func:`aeat.application.modelo._semantic_role_resolution.casilla_id_for_unique_revision_semantic_role`:
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
            f"bindings {misrouted_to_decimal!r} are consumed by the registry as enum "
            f"dispatch keys and must be supplied through the enum-binding channel, "
            f"not as Decimal binding values",
        )
    misrouted_to_enum = sorted(set(enum_binding_values) & {b.id for b in revision.bindings} - enum_consumed)
    misrouted_to_enum = [
        binding_id for binding_id in misrouted_to_enum if _binding_is_formula_consumed(revision, binding_id)
    ]
    if misrouted_to_enum:
        raise ModeloError(
            f"bindings {misrouted_to_enum!r} are consumed by the registry as Decimal "
            f"operands and must be supplied as Decimal binding values, not through the "
            f"enum-binding channel. `aeat app modelo bindings list` reports each "
            f"binding's input_channel; a binding shown as input_channel=decimal "
            f"takes a numeric --binding KEY=VALUE even when typed_enum is set",
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
    :class:`aeat.application.aggregation.CalculationSourceResolution` carries
    the typed ``borrador_provenance`` (snapshot id + sourced-binding trace) the
    persistence boundary consumes.
    """
    from ..aggregation import CalculationSourceContext

    return Modelo100BorradorSourceResolver(
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
    ).resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision=registry_snapshot.revision,
        ),
    )


def resolve_available_bound_inputs_by_casilla_id(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project available binding values into input values keyed by bound ``casilla.id``.

    The :class:`ModeloRevision` supplies the bound casilla-to-binding mapping;
    only values already present in ``binding_values`` are projected. Missing
    optional bindings are skipped rather than treated as registry errors, which
    lets application calculate paths combine partial source mesh output with
    caller overrides before the engine runs.

    Args:
        revision: The :class:`ModeloRevision` whose bound casillas are inspected.
        binding_values: Decimal values keyed by :class:`BindingId`.

    Returns:
        A ``dict`` keyed by :class:`CasillaId` for every bound casilla whose
        binding value is currently available.

    See Also:
        :func:`aeat.domain.calculations.registry.resolve_bound_inputs_by_casilla_id`:
            Strict domain helper that rejects unknown or missing binding facts.
        :func:`aeat.application.modelo._calculation_resolution.resolve_calculation_inputs`:
            Uses this partial projection when assembling engine inputs.
    """
    resolved: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        value, _binding_ids = resolve_bound_casilla_binding_value(casilla, binding_values)
        if value is not None:
            resolved[casilla.id] = value
    return resolved


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
        if binding is None or binding.source != "previous_filing":
            continue
        if casilla.binding in resolved_bindings:
            continue
        promoted[casilla.binding] = value
    return {**resolved_bindings, **promoted}


_FILING_PERIOD_ORDINALS: Mapping[str, int] = {
    "1T": 1,
    "2T": 2,
    "3T": 3,
    "4T": 4,
    "0A": 0,
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
    "10": 10,
    "11": 11,
    "12": 12,
    "1P": 1,
    "2P": 2,
    "3P": 3,
}


def _resolve_declaration_period_inputs(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: _Period,
) -> dict[CasillaId, Decimal]:
    """Return informational-casilla inputs sourced from work-unit metadata."""
    resolved: dict[CasillaId, Decimal] = {}
    filing_year_id = _informational_semantic_role_casilla_id(revision, "filing_year")
    if filing_year_id is not None:
        resolved[filing_year_id] = Decimal(filing_year)

    filing_period_id = _informational_semantic_role_casilla_id(revision, "filing_period")
    if filing_period_id is not None:
        ordinal = _FILING_PERIOD_ORDINALS.get(period.registry_token)
        if ordinal is None:
            raise ModeloError(
                f"work-unit period {period.registry_token!r} has no registry period ordinal; "
                f"cannot resolve informational casilla {filing_period_id!r}",
            )
        resolved[filing_period_id] = Decimal(ordinal)
    return resolved


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
            f"semantic_role={semantic_role!r} resolved to casilla {casilla_id!r}, "
            "but declaration-period metadata can only populate informational casillas",
            context={"semantic_role": semantic_role, "casilla_id": casilla_id},
        )
    return casilla_id


__all__ = [
    "lift_previous_filing_casilla_overrides_to_bindings",
    "reject_binding_channel_mismatch",
    "resolve_available_bound_inputs_by_casilla_id",
    "resolve_borrador_source_tier",
    "resolve_declaration_period_inputs",
    "resolve_profile_source_tier",
]

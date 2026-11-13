"""Calculation input-channel resolution helpers.

The helpers merge caller, backend, profile, and borrador channels for a
:class:`RegistrySnapshot`, then build the canonical input map consumed by the
selected :class:`ModeloRevision`.

This module is the calculation-service assembly layer between source resolution
and engine execution. It delegates source-specific work to the binding
resolution helpers, then returns typed channel bundles that
:func:`application.modelo.calculation_actions.calculate_modelo_revision_with_trusted_mesh_sources` can pass to
:func:`domain.calculations.registry.formula_runtime.calculate_registry_snapshot` and the
:class:`CalculationRevision` persistence boundary.

See Also:
    :func:`application.modelo.binding_resolution.resolve_borrador_source_tier`
        Resolves the optional borrador tier before the final precedence merge.
    :func:`application.modelo.binding_resolution.resolve_profile_source_tier`
        Resolves profile-sourced bindings as the lowest-precedence tier.
    :func:`application.aggregation.source_resolution_operations.merge_source_resolutions_by_precedence`
        Applies the ordered overlay contract used by this module and reports
        every value a higher tier replaced.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.hashing import CONTENT_DIGEST_PREFIX, content_hash_hex
from ...core.period import Period
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id, sole_bound_casilla
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.bindings import (
    resolve_available_bound_inputs_by_casilla_id,
    resolve_bound_casilla_binding_value,
)
from ...domain.calculations.registry.casilla_membership import casillas_by_id, text_family_casilla_ids
from ...domain.calculations.registry.filing_bound_reach import FilingBoundReach, snapshot_filing_bound_reach
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema import (
    BindingDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_binding_values import PERSISTED_BOOLEAN_BINDING_TOKENS
from ...domain.modelos.calculation_revision_sources import (
    CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT,
    CalculationSourceIssue,
    CalculationSourceRef,
)
from ...domain.modelos.filing_record import FilingDeclarationKind
from ...domain.modelos.profile_read_fingerprint import ProfileReadFingerprint
from ...domain.modelos.source_disagreement import SourceDisagreementFact, SourceDisagreementRole
from ...domain.modelos.work_unit import WorkUnit
from ..aggregation.source_diagnostic_reason import CalculationSourceDiagnosticReason
from ..aggregation.source_mesh import (
    BorradorSourceProvenance,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    RowBindingValue,
)
from ..aggregation.source_resolution_operations import (
    PrecedenceKeyKind,
    PrecedenceOverlay,
    PrecedenceTier,
    TierDivergence,
    TierValueProvenance,
    merge_source_resolutions,
    merge_source_resolutions_by_precedence,
)
from .binding_resolution import (
    lift_previous_filing_casilla_overrides_to_bindings,
    reject_binding_channel_mismatch,
    resolve_borrador_source_tier,
    resolve_declaration_period_inputs,
    resolve_profile_source_tier,
)
from .profile_binding import profile_resolved_binding_ids

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.row_source_identity import RowBindingKey
    from ..live.borrador_100 import Borrador100SnapshotRepository
    from .work_profile import ModeloWorkProfile


def _no_row_values() -> dict[RowBindingKey, RowBindingValue]:
    return {}


@dataclass(frozen=True, slots=True)
class ResolvedCalculationChannels:
    """Merged engine binding channels for one calculation.

    ``bindings`` feeds the Decimal channel, ``enum_bindings`` feeds string
    dispatch keys, ``date_bindings`` feeds date-valued profile bindings, and
    ``boolean_bindings`` feeds the truth values of bindings whose registry value
    contract declares the boolean channel.
    The borrador fields carry the typed snapshot trace from
    :class:`~application.aggregation.source_mesh.CalculationSourceResolution` through to
    the persisted :class:`CalculationRevision`.
    """

    bindings: dict[BindingId, Decimal]
    enum_bindings: dict[BindingId, str]
    date_bindings: dict[BindingId, date]
    boolean_bindings: dict[BindingId, bool]
    borrador_snapshot_id: str | None
    bindings_sourced_from_borrador: tuple[BindingId, ...]
    precedence_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    """Every value a higher tier replaced that a lower tier held differently, as the screen reports it."""
    profile_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    """The profile's unanswered bindings that no higher tier answered, each naming the box and the fact to record."""
    profile_source_provenance: tuple[CalculationSourceRef, ...] = ()
    """Profile evidence considered by the overlay: each scalar, including one a caller value superseded, and
    each row set the profile enumerated, which is what shows a declared-empty group as empty rather than unknown."""
    row_binding_values: Mapping[RowBindingKey, RowBindingValue] = field(default_factory=_no_row_values)
    """The row sets the precedence tiers answered, such as the household rows a profile states."""
    profile_read_fingerprint: ProfileReadFingerprint | None = None
    """The profile facts the profile tier read, which the revision keeps so a later edit to one is detected."""


@dataclass(frozen=True, slots=True)
class ResolvedCalculationInputs:
    """Canonical per-channel casilla inputs for one engine run.

    ``casilla_inputs`` feeds ``calculate_registry_snapshot(inputs=...)`` and
    ``text_casilla_inputs`` feeds its ``text_inputs=...`` channel. Callers
    receive both together so a string-family casilla cannot be silently dropped
    on the way to the engine.
    """

    casilla_inputs: dict[CasillaId, Decimal]
    text_casilla_inputs: dict[CasillaId, str]


@dataclass(frozen=True, slots=True)
class CalculationReplayPayloads:
    """Canonical string payloads stored for calculation replay.

    The persistence layer stores user-visible inputs as strings, not live
    :class:`~decimal.Decimal` instances. These maps are derived after all source
    overlays have settled so replay and revision identity use the same canonical
    values the engine consumed. They are the persisted replay side of the
    :class:`CalculationRevision` hash domain, not an independent calculation
    path.
    """

    input_values_by_casilla_id: dict[CasillaId, str]
    binding_overrides: dict[BindingId, str]
    row_binding_values: dict[BindingId, dict[str, str]]
    relation_overrides: dict[RelationId, str]


def resolve_calculation_binding_channels(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_inputs: Mapping[CasillaId, Decimal],
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    backend_binding_values: Mapping[BindingId, Decimal],
    borrador_snapshot_id: str | None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile,
    backend_source_provenance: Sequence[CalculationSourceRef] = (),
) -> ResolvedCalculationChannels:
    """Resolve all binding channels for ``work_unit`` and ``snapshot``.

    The ``work_unit`` is the :class:`WorkUnit` whose bucket, filing year, and
    period select the source-resolution axis. The ``snapshot`` is the
    :class:`RegistrySnapshot` supplying the revision whose binding
    channels are being resolved.

    The source-precedence ladder is profile, backend, borrador, then caller. The
    returned :class:`ResolvedCalculationChannels` contains the merged Decimal,
    enum, date, and boolean channels, plus any
    :class:`~application.live.borrador_100.Borrador100SnapshotRepository` provenance,
    after
    :func:`application.modelo.binding_resolution.reject_binding_channel_mismatch`
    verifies the registry-declared channel shape and
    :func:`application.modelo.binding_resolution.lift_previous_filing_casilla_overrides_to_bindings`
    mirrors eligible previous-filing casilla overrides onto their binding ids.

    ``backend_source_provenance`` is the source mesh's provenance for the
    backend values; a divergence names each backend value by its declared
    source and locates it by a digest of the evidence fingerprints behind it.
    """
    borrador_resolution = resolve_borrador_source_tier(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
        operation=operation,
    )
    profile_resolution = resolve_profile_source_tier(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        operation=operation,
        profile=profile,
    )
    overlay = _overlay_binding_tiers(
        snapshot,
        profile_resolution=profile_resolution,
        borrador_resolution=borrador_resolution,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        backend_binding_values=backend_binding_values,
        backend_source_provenance=backend_source_provenance,
    )
    merged = overlay.resolution
    resolved_bindings = dict(sorted(merged.binding_values.items()))
    resolved_enum_bindings = dict(sorted(merged.enum_binding_values.items()))
    resolved_date_bindings = dict(sorted(merged.date_binding_values.items()))
    resolved_boolean_bindings = dict(sorted(merged.boolean_binding_values.items()))
    reject_binding_channel_mismatch(
        snapshot.revision,
        resolved_bindings,
        resolved_enum_bindings,
        resolved_boolean_bindings,
    )
    screen = precedence_screen_context(work_unit, snapshot, operation=operation)
    casilla_divergences = _caller_casillas_over_tier_bound_values(
        snapshot.revision,
        casilla_inputs=casilla_inputs,
        resolved_bindings=resolved_bindings,
        selected_binding_roles=overlay.selected_binding_roles,
        backend_binding_ids=frozenset(backend_binding_values),
    )
    resolved_bindings = dict(
        sorted(
            lift_previous_filing_casilla_overrides_to_bindings(
                snapshot.revision,
                casilla_inputs,
                resolved_bindings,
            ).items(),
        ),
    )
    borrador_provenance = merged.borrador_provenance
    answered_binding_ids = (
        resolved_bindings.keys()
        | resolved_enum_bindings.keys()
        | resolved_date_bindings.keys()
        | resolved_boolean_bindings.keys()
    )
    profile_scalar_binding_ids = profile_resolved_binding_ids(profile_resolution)
    return ResolvedCalculationChannels(
        bindings=resolved_bindings,
        enum_bindings=resolved_enum_bindings,
        date_bindings=resolved_date_bindings,
        boolean_bindings=resolved_boolean_bindings,
        borrador_snapshot_id=borrador_provenance.snapshot_id if borrador_provenance is not None else None,
        bindings_sourced_from_borrador=_bindings_won_by_borrador(borrador_provenance, overlay),
        precedence_diagnostics=precedence_divergence_diagnostics(
            (*overlay.divergences, *casilla_divergences),
            screen=screen,
        ),
        profile_diagnostics=tuple(
            diagnostic
            for diagnostic in profile_resolution.diagnostics
            if diagnostic.reason in _PROFILE_NOTE_REASONS and diagnostic.binding_id not in answered_binding_ids
        ),
        profile_source_provenance=calculation_source_provenance_refs(
            tuple(
                row
                for row in profile_resolution.provenance
                if _ROWS_REF_MARKER in row.source_ref
                or (
                    _BINDING_REF_MARKER in row.source_ref
                    and row.source_ref.rsplit(_BINDING_REF_MARKER, 1)[1] in profile_scalar_binding_ids
                )
            )
        ),
        row_binding_values=dict(merged.row_binding_values),
        profile_read_fingerprint=profile_resolution.profile_read_fingerprint,
    )


def calculation_row_binding_values(
    mesh_row_binding_values: Mapping[RowBindingKey, RowBindingValue] | None,
    channels: ResolvedCalculationChannels,
) -> dict[RowBindingKey, RowBindingValue]:
    """Join the source mesh's row sets with the row sets the precedence tiers answered.

    Each row binding has one owning source, so the join is the exclusive merge the
    mesh itself applies: a row both sides state is refused rather than overlaid.
    """
    merged = merge_source_resolutions(
        (
            CalculationSourceResolution(
                resolver_id=_BACKEND_ROWS_RESOLVER_ID,
                row_binding_values=dict(mesh_row_binding_values or {}),
            ),
            CalculationSourceResolution(
                resolver_id=_PRECEDENCE_TIERS_RESOLVER_ID,
                row_binding_values=dict(channels.row_binding_values),
            ),
        )
    )
    return dict(merged.row_binding_values)


def _bindings_won_by_borrador(
    borrador_provenance: BorradorSourceProvenance | None, overlay: PrecedenceOverlay
) -> tuple[BindingId, ...]:
    """The borrador's bindings whose final value still came from the borrador tier."""
    if borrador_provenance is None:
        return ()
    return tuple(
        binding_id
        for binding_id in borrador_provenance.bindings_sourced
        if overlay.selected_binding_roles.get(binding_id) is SourceDisagreementRole.BORRADOR
    )


def _overlay_binding_tiers(
    snapshot: RegistrySnapshot,
    *,
    profile_resolution: CalculationSourceResolution,
    borrador_resolution: CalculationSourceResolution,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    backend_binding_values: Mapping[BindingId, Decimal],
    backend_source_provenance: Sequence[CalculationSourceRef],
) -> PrecedenceOverlay:
    """Overlay the profile, backend, borrador and caller tiers in that precedence order."""
    backend_tier = CalculationSourceResolution(
        resolver_id="calculate_backend_bindings",
        binding_values=dict(backend_binding_values),
    )
    caller_tier = CalculationSourceResolution(
        resolver_id="calculate_caller_bindings",
        binding_values=dict(caller_binding_values),
        enum_binding_values=dict(caller_enum_binding_values),
    )
    return merge_source_resolutions_by_precedence(
        (
            PrecedenceTier(
                role=SourceDisagreementRole.PROFILE,
                resolution=profile_resolution,
                source_family=BindingSourceKind.PROFILE.value,
                provenance=_binding_keyed_provenance(profile_resolution, BindingSourceKind.PROFILE.value),
            ),
            PrecedenceTier(
                role=SourceDisagreementRole.BACKEND,
                resolution=backend_tier,
                source_family=_BACKEND_SOURCE_FAMILY,
                provenance=_backend_binding_provenance(
                    snapshot.revision, backend_binding_values, backend_source_provenance
                ),
            ),
            PrecedenceTier(
                role=SourceDisagreementRole.BORRADOR,
                resolution=borrador_resolution,
                source_family=BindingSourceKind.BORRADOR.value,
                provenance=_binding_keyed_provenance(
                    borrador_resolution,
                    BindingSourceKind.BORRADOR.value,
                    evidence_ref=(
                        None
                        if borrador_resolution.borrador_provenance is None
                        else borrador_resolution.borrador_provenance.snapshot_id
                    ),
                ),
            ),
            PrecedenceTier(
                role=SourceDisagreementRole.CALLER,
                resolution=caller_tier,
                source_family=OPERATOR_INPUT_SOURCE_FAMILY,
                provenance=_caller_provenance(
                    PrecedenceKeyKind.BINDING, (*caller_binding_values, *caller_enum_binding_values)
                ),
            ),
        ),
    )


OPERATOR_INPUT_SOURCE_FAMILY: Final[str] = "operator_input"
"""The source family of every value the operator supplied: a binding, a relation or a box."""
_BACKEND_SOURCE_FAMILY: Final[str] = "source_mesh"
_BINDING_REF_MARKER: Final[str] = ":binding:"
_ROWS_REF_MARKER: Final[str] = ":rows:"
_PROFILE_NOTE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unresolved_binding",
        "household_rows_incomplete",
        "household_row_fact_unstated",
        "ascendant_disability_minimum_not_computed",
    }
)
"""The profile diagnostics a calculation carries onward: an unanswered fact, the household rows still owed
and an ascendant disability minimum not computed."""
_PRECEDENCE_TIERS_RESOLVER_ID: Final[str] = "calculate_precedence_tiers"
_BACKEND_ROWS_RESOLVER_ID: Final[str] = "calculate_backend_rows"
PRECEDENCE_TIER_DIVERGENCE_REASON: Final = "precedence_tier_divergence"
"""The reason of a divergence on a filed figure; it withholds checking, exporting and recording."""
PRECEDENCE_TIER_DIVERGENCE_ADVISORY_REASON: Final = "precedence_tier_divergence_advisory"
"""The reason of a divergence on a figure that reaches no exported box; it withholds nothing."""
_OPERATOR_OVERRIDE_ADVISORY_REASON: Final = "operator_override_diverges_from_computed"


def _binding_keyed_provenance(
    resolution: CalculationSourceResolution, source_family: str, *, evidence_ref: str | None = None
) -> dict[str, TierValueProvenance]:
    """Each binding a tier's provenance names, with its keyed source reference and fingerprint.

    The profile and borrador tiers name each value they source as
    ``...:binding:<id>``; a supplied ``evidence_ref`` (the borrador snapshot)
    stands in for the row's fingerprint.
    """
    provenance: dict[str, TierValueProvenance] = {}
    for row in resolution.provenance:
        if _BINDING_REF_MARKER not in row.source_ref:
            continue
        binding_id = row.source_ref.rsplit(_BINDING_REF_MARKER, 1)[1]
        provenance[binding_id] = TierValueProvenance(
            source_family=source_family,
            source_ref=row.source_ref,
            evidence_ref=evidence_ref if evidence_ref is not None else row.fingerprint,
        )
    return provenance


def _backend_binding_provenance(
    revision: ModeloRevision,
    backend_binding_values: Mapping[BindingId, Decimal],
    source_provenance: Sequence[CalculationSourceRef],
) -> dict[str, TierValueProvenance]:
    """Each backend value named by its declared source and located by the evidence behind it.

    ``source_ref`` is ``<declared source>:binding:<id>``: it names the value
    without naming any source object, because a mesh reference can carry a
    third party's tax identifier. ``evidence_ref`` digests the fingerprints of
    the provenance rows the declared source produced, so a reader can tell
    which evidence the value rested on; it is ``None`` when those rows carry no
    fingerprint.
    """
    bindings = revision_bindings_by_id(revision)
    fingerprints_by_source: dict[BindingSourceKind, set[str]] = {}
    for row in source_provenance:
        if row.fingerprint is not None:
            fingerprints_by_source.setdefault(row.resolved_binding_source, set()).add(row.fingerprint)
    provenance: dict[str, TierValueProvenance] = {}
    for binding_id in backend_binding_values:
        binding = bindings.get(binding_id)
        source = None if binding is None else binding.source
        family = _BACKEND_SOURCE_FAMILY if source is None else source.value
        fingerprints: frozenset[str] = (
            frozenset[str]() if source is None else frozenset(fingerprints_by_source.get(source, ()))
        )
        provenance[binding_id] = TierValueProvenance(
            source_family=family,
            source_ref=f"{family}{_BINDING_REF_MARKER}{binding_id}",
            evidence_ref=f"{CONTENT_DIGEST_PREFIX}{content_hash_hex(sorted(fingerprints))}" if fingerprints else None,
        )
    return provenance


def _caller_provenance(key_kind: PrecedenceKeyKind, keys: Iterable[str]) -> dict[str, TierValueProvenance]:
    """Each operator value marked as the operator's: ``operator_input:<key kind>:<key>``."""
    return {
        key: TierValueProvenance(
            source_family=OPERATOR_INPUT_SOURCE_FAMILY,
            source_ref=f"{OPERATOR_INPUT_SOURCE_FAMILY}:{key_kind.value}:{key}",
        )
        for key in keys
    }


_LOWER_TIER_ROLES = (SourceDisagreementRole.PROFILE, SourceDisagreementRole.BORRADOR)


def _lower_tier_bound_inputs(
    revision: ModeloRevision,
    *,
    resolved_bindings: Mapping[BindingId, Decimal],
    selected_binding_roles: Mapping[BindingId, SourceDisagreementRole],
    backend_binding_ids: frozenset[BindingId],
) -> dict[SourceDisagreementRole, dict[CasillaId, Decimal]]:
    """Return, per profile or borrador tier, the box values its non-mesh resolved bindings bring."""
    return {
        role: resolve_available_bound_inputs_by_casilla_id(
            revision,
            {
                binding_id: value
                for binding_id, value in resolved_bindings.items()
                if selected_binding_roles.get(binding_id) is role and binding_id not in backend_binding_ids
            },
        )
        for role in _LOWER_TIER_ROLES
    }


def _caller_casillas_over_tier_bound_values(
    revision: ModeloRevision,
    *,
    casilla_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
    selected_binding_roles: Mapping[BindingId, SourceDisagreementRole],
    backend_binding_ids: frozenset[BindingId],
) -> tuple[TierDivergence, ...]:
    """Compare each operator box with the value its binding brought from the profile or the borrador.

    A box bound to a source-mesh binding is compared where the mesh's bound
    values are merged with the operator's boxes, so it is left out here, as is
    a box whose binding the operator also set: both values are the operator's.
    """
    bound_by_role = _lower_tier_bound_inputs(
        revision,
        resolved_bindings=resolved_bindings,
        selected_binding_roles=selected_binding_roles,
        backend_binding_ids=backend_binding_ids,
    )
    contested = {
        casilla_id: value
        for casilla_id, value in casilla_inputs.items()
        if any(casilla_id in bound for bound in bound_by_role.values())
    }
    if not contested:
        return ()
    tiers = [
        PrecedenceTier(
            role=role,
            resolution=CalculationSourceResolution(
                resolver_id=f"calculate_{role.value}_bound_casillas",
                bound_inputs_by_casilla_id={
                    casilla_id: value for casilla_id, value in bound_by_role[role].items() if casilla_id in contested
                },
            ),
            source_family=role.value,
        )
        for role in _LOWER_TIER_ROLES
    ]
    tiers.append(
        PrecedenceTier(
            role=SourceDisagreementRole.CALLER,
            resolution=CalculationSourceResolution(
                resolver_id="calculate_caller_casillas", bound_inputs_by_casilla_id=contested
            ),
            source_family=OPERATOR_INPUT_SOURCE_FAMILY,
            provenance=_caller_provenance(PrecedenceKeyKind.CASILLA, contested),
        )
    )
    return merge_source_resolutions_by_precedence(tiers).divergences


@dataclass(frozen=True, slots=True)
class PrecedenceScreenContext:
    """What a precedence divergence is stated against: the declaration, its revision and its filing-bound set."""

    modelo: str
    filing_year: int
    period: str
    work_unit_id: str
    revision: ModeloRevision
    reach: FilingBoundReach
    declared_bindings: Mapping[BindingId, BindingDefinition]


def precedence_screen_context(
    work_unit: WorkUnit, snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation
) -> PrecedenceScreenContext:
    """Bind the precedence screen to ``work_unit`` and the filing-bound set of ``snapshot``'s revision.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    revision = snapshot.revision
    return PrecedenceScreenContext(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        work_unit_id=work_unit.work_unit_id,
        revision=revision,
        reach=snapshot_filing_bound_reach(snapshot, operation=operation),
        declared_bindings=MappingProxyType(dict(revision_bindings_by_id(revision))),
    )


def _declaration_digest(screen: PrecedenceScreenContext, divergence: TierDivergence) -> str:
    """The content digest of the registry declaration a divergence's key is read from."""
    if divergence.key_kind is PrecedenceKeyKind.CASILLA:
        casilla = casillas_by_id(screen.revision).get(validated_casilla_id(divergence.key))
        declaration: object = None if casilla is None else casilla.model_dump(mode="json")
    else:
        binding = screen.declared_bindings.get(divergence.key)
        declaration = None if binding is None else binding.model_dump(mode="json")
    return content_hash_hex({"key_kind": divergence.key_kind.value, "key": divergence.key, "declaration": declaration})


def _reached_casillas(screen: PrecedenceScreenContext, divergence: TierDivergence) -> tuple[CasillaId, ...]:
    if divergence.key_kind is PrecedenceKeyKind.CASILLA:
        return screen.reach.casilla_reach(validated_casilla_id(divergence.key))
    return screen.reach.binding_reach(divergence.key)


def _divergence_reason(divergence: TierDivergence, *, filing_bound: bool) -> CalculationSourceDiagnosticReason:
    if filing_bound:
        return PRECEDENCE_TIER_DIVERGENCE_REASON
    if divergence.key_kind is PrecedenceKeyKind.CASILLA:
        return _OPERATOR_OVERRIDE_ADVISORY_REASON
    return PRECEDENCE_TIER_DIVERGENCE_ADVISORY_REASON


def _held_roles_text(divergence: TierDivergence) -> str:
    replaced = dict.fromkeys(
        source.role.value for source in divergence.sources if source.role is not divergence.selected_role
    )
    return ", ".join(replaced)


def _divergence_diagnostic(screen: PrecedenceScreenContext, divergence: TierDivergence) -> CalculationSourceDiagnostic:
    """State one divergence as a diagnostic that names its tiers and never its amounts."""
    reached = _reached_casillas(screen, divergence)
    fact = SourceDisagreementFact.of(
        modelo=screen.modelo,
        filing_year=screen.filing_year,
        period=screen.period,
        work_unit_id=screen.work_unit_id,
        registry_revision_id=str(screen.revision.id),
        inputs_digest=_declaration_digest(screen, divergence),
        key=divergence.key,
        value_channel=divergence.value_channel,
        reached_casillas=reached,
        sources=divergence.sources,
        selected_role=divergence.selected_role,
        differing_row_indices=divergence.differing_row_indices,
    )
    binding = None if divergence.key_kind is PrecedenceKeyKind.CASILLA else screen.declared_bindings.get(divergence.key)
    source_kind = OPERATOR_INPUT_SOURCE_FAMILY if binding is None else binding.source.value
    message = (
        f"{divergence.key_kind.value} {divergence.key!r}: the {divergence.selected_role.value} value replaced a "
        f"different value from {_held_roles_text(divergence)}"
    )
    return CalculationSourceDiagnostic(
        reason=_divergence_reason(divergence, filing_bound=bool(reached)),
        source_kind=source_kind,
        message=message[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT],
        remedy=(
            "Correct the source in error so both state the same value, or remove the higher tier's value, "
            "then calculate again."
        ),
        resolver_id=fact.sources[-1].resolver_id,
        binding_id=divergence.key if divergence.key_kind is PrecedenceKeyKind.BINDING else None,
        relation_id=divergence.key if divergence.key_kind is PrecedenceKeyKind.RELATION else None,
        casilla_id=(
            validated_casilla_id(divergence.key)
            if divergence.key_kind is PrecedenceKeyKind.CASILLA
            else sole_bound_casilla(screen.revision, divergence.key)
        ),
        disagreement=fact,
    )


def precedence_divergence_diagnostics(
    divergences: Iterable[TierDivergence], *, screen: PrecedenceScreenContext
) -> tuple[CalculationSourceDiagnostic, ...]:
    """State every overlay divergence against ``screen``: blocking on a filed figure, an advisory elsewhere.

    A figure is filed when its key reaches an exported casilla of a revision
    declared at the filing rung (:func:`~cadrumo.domain.calculations.registry.filing_bound_reach.filing_bound_reach`).
    A box the operator set over a bound value that reaches no exported box
    keeps the operator-override advisory it always had.
    """
    return tuple(_divergence_diagnostic(screen, divergence) for divergence in divergences)


def operator_over_source_divergences(
    *,
    source_relations: Mapping[RelationId, Decimal],
    operator_relations: Mapping[RelationId, Decimal],
    source_casillas: Mapping[CasillaId, Decimal],
    operator_casillas: Mapping[CasillaId, Decimal],
) -> tuple[TierDivergence, ...]:
    """Compare each relation and box the operator set with the value the source mesh resolved for it.

    These two channels are merged where the mesh's own values are in hand
    rather than in the binding overlay, so they are screened here: the mesh is
    the backend tier and the operator the caller tier, in the declared order.
    A key only one side holds is no contest and is left out.
    """
    contested_relations = operator_relations.keys() & source_relations.keys()
    contested_casillas = operator_casillas.keys() & source_casillas.keys()
    if not contested_relations and not contested_casillas:
        return ()
    return merge_source_resolutions_by_precedence(
        (
            PrecedenceTier(
                role=SourceDisagreementRole.BACKEND,
                resolution=CalculationSourceResolution(
                    resolver_id="calculate_backend_relations_and_boxes",
                    relation_values={key: source_relations[key] for key in contested_relations},
                    bound_inputs_by_casilla_id={key: source_casillas[key] for key in contested_casillas},
                ),
                source_family=_BACKEND_SOURCE_FAMILY,
            ),
            PrecedenceTier(
                role=SourceDisagreementRole.CALLER,
                resolution=CalculationSourceResolution(
                    resolver_id="calculate_caller_relations_and_boxes",
                    relation_values={key: operator_relations[key] for key in contested_relations},
                    bound_inputs_by_casilla_id={key: operator_casillas[key] for key in contested_casillas},
                ),
                source_family=OPERATOR_INPUT_SOURCE_FAMILY,
                provenance={
                    **_caller_provenance(PrecedenceKeyKind.RELATION, contested_relations),
                    **_caller_provenance(PrecedenceKeyKind.CASILLA, contested_casillas),
                },
            ),
        )
    ).divergences


def precedence_tier_issue(diagnostic: CalculationSourceDiagnostic) -> CalculationSourceIssue | None:
    """The persisted issue a blocking divergence diagnostic becomes; ``None`` for an advisory one.

    The issue carries every tier's value inside the encrypted revision, so
    check, export and recording read the finding without resolving again.
    """
    if diagnostic.reason != PRECEDENCE_TIER_DIVERGENCE_REASON or diagnostic.disagreement is None:
        return None
    return CalculationSourceIssue(
        reason=PRECEDENCE_TIER_DIVERGENCE_REASON,
        binding_source=diagnostic.binding_source,
        casilla_id=diagnostic.casilla_id,
        message=diagnostic.message[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT],
        resolver_id=diagnostic.resolver_id,
        disagreement=diagnostic.disagreement,
    )


def resolve_calculation_inputs(
    *,
    revision: ModeloRevision,
    filing_year: int,
    period: Period,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    resolved_bindings: Mapping[BindingId, Decimal],
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    profile_text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    resolved_text_bindings: Mapping[BindingId, str] | None = None,
) -> ResolvedCalculationInputs:
    """Build the canonical casilla input maps for engine execution.

    The ``revision`` is the :class:`ModeloRevision` whose declaration-period and
    bound casilla inputs are being projected. The :class:`~core.period.Period`
    supplies the filing-period casilla values that the registry declares as
    inputs.

    Declaration-period bindings are projected first, followed by backend casilla
    inputs, bound casillas resolved from merged binding values, and finally the
    caller's explicit casilla overrides. Both returned maps are sorted for stable
    replay payloads and revision identity.

    A work-unit calculation prepares the period's original declaration -- the
    kind the local filing record carries -- so the ``tipo_declaracion`` role
    receives :attr:`~cadrumo.domain.modelos.filing_record.FilingDeclarationKind.ORIGINAL`;
    an amendment is built by the amendment service with its own kind.
    ``profile_text_casilla_inputs`` are the bound text casillas the declarant's
    profile answers, resolved by
    :func:`~application.modelo.profile_export_binding.resolve_profile_text_casilla_inputs`;
    they rank below a bound value on the binding channel and below the caller's
    own text. ``resolved_text_bindings`` are the source-resolved values of
    text-channel bindings; a bound text casilla takes its binding's text
    verbatim, so a code keeps its leading zeros.

    The two channels are returned together, and never merged, because the
    registry assigns each casilla to exactly one of them by declared
    ``data_type`` family: the ``filing_period`` role is ``period_code`` (a
    string family whose ``period_code`` validator accepts ``1T``, ``EXT-1T``,
    and every other declared token), while ``filing_year`` is ``year`` and stays
    on the Decimal channel.
    """
    declaration = resolve_declaration_period_inputs(
        revision,
        filing_year=filing_year,
        period=period,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    return ResolvedCalculationInputs(
        casilla_inputs=dict(
            sorted(
                {
                    **declaration.casilla_inputs,
                    **dict(backend_casilla_inputs or {}),
                    **resolve_available_bound_inputs_by_casilla_id(revision, resolved_bindings),
                    **casilla_inputs,
                }.items(),
            ),
        ),
        text_casilla_inputs=dict(
            sorted(
                {
                    **declaration.text_casilla_inputs,
                    **dict(profile_text_casilla_inputs or {}),
                    **_bound_text_casilla_inputs(revision, resolved_bindings),
                    **_bound_text_channel_casilla_inputs(revision, resolved_text_bindings or {}),
                    **dict(text_casilla_inputs or {}),
                }.items(),
            ),
        ),
    )


def _bound_text_casilla_inputs(
    revision: ModeloRevision,
    resolved_bindings: Mapping[BindingId, Decimal],
) -> dict[CasillaId, str]:
    """Project resolved binding values onto the text casillas they are bound to.

    A bound text casilla -- such as a declaration-type code read from the
    profile -- can arrive on the binding channel as a number. It is still text:
    it enters the calculation on the text channel, spelled as the canonical
    decimal token its binding resolved to, which is the same spelling a replay
    of the persisted inputs reads back. A casilla whose binding resolved to
    nothing stays absent.
    """
    text_casilla_ids = text_family_casilla_ids(revision.casillas)
    projected: dict[CasillaId, str] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.id not in text_casilla_ids:
            continue
        value, _binding_ids = resolve_bound_casilla_binding_value(casilla, resolved_bindings)
        if value is not None:
            projected[casilla.id] = canonical_decimal_string(value)
    return projected


def _bound_text_channel_casilla_inputs(
    revision: ModeloRevision,
    resolved_text_bindings: Mapping[BindingId, str],
) -> dict[CasillaId, str]:
    """Project text-channel binding values onto the text casillas bound to them.

    Only a binding declared on the ``text`` channel is read, so an enum token
    meant for a typed consumer never lands in a casilla as free text. A casilla
    whose binding resolved to nothing stays absent.
    """
    if not resolved_text_bindings:
        return {}
    text_casilla_ids = text_family_casilla_ids(revision.casillas)
    text_bindings = {binding.id for binding in revision.bindings if binding.value.channel is BindingValueChannel.TEXT}
    return {
        casilla.id: resolved_text_bindings[casilla.binding]
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND
        and casilla.id in text_casilla_ids
        and casilla.binding is not None
        and casilla.binding in text_bindings
        and casilla.binding in resolved_text_bindings
    }


def _binding_replay_overrides(
    resolved_bindings: Mapping[BindingId, Decimal],
    resolved_enum_bindings: Mapping[BindingId, str],
    resolved_date_bindings: Mapping[BindingId, date],
    resolved_boolean_bindings: Mapping[BindingId, bool] | None,
) -> dict[BindingId, str]:
    """Serialize admitted decimal, enum, date and boolean channels before relation de-duplication."""
    binding_overrides = dict(
        sorted(
            [(k.strip(), canonical_decimal_string(v)) for k, v in resolved_bindings.items()]
            + [(k.strip(), v.strip()) for k, v in resolved_enum_bindings.items()]
            + [(k.strip(), v.isoformat()) for k, v in resolved_date_bindings.items()]
            + [(k.strip(), PERSISTED_BOOLEAN_BINDING_TOKENS[v]) for k, v in (resolved_boolean_bindings or {}).items()],
        ),
    )
    return binding_overrides


def build_calculation_replay_payloads(
    *,
    resolved_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
    resolved_enum_bindings: Mapping[BindingId, str],
    resolved_date_bindings: Mapping[BindingId, date],
    resolved_relations: Mapping[RelationId, Decimal],
    resolved_row_bindings: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None = None,
    resolved_boolean_bindings: Mapping[BindingId, bool] | None = None,
) -> CalculationReplayPayloads:
    """Convert resolved engine inputs into persisted :class:`CalculationReplayPayloads`.

    Casilla and relation Decimals are canonicalized with the domain decimal
    formatter. Decimal, enum, date, and boolean binding channels share the single
    ``binding_overrides`` replay map (a truth value as ``true``/``false``) because that is the persisted scalar
    :class:`CalculationRevision` contract. Row-indexed bindings are carried in
    ``row_binding_values`` so the row coordinate remains structured for draft
    and export replay instead of being encoded into a synthetic binding id. The
    replay payload is built after source precedence and bound-casilla projection
    so its values match the engine inputs exactly.

    A carried relation value is keyed by the binding it folds into, so the
    relation prefill resolves it on both channels. Replay reads both channels
    into one namespace, so a relation entry that repeats its binding's value
    is dropped; a relation entry that disagrees is kept, and the revision's
    channel-uniqueness invariant refuses it rather than choosing a winner.
    """
    binding_overrides = _binding_replay_overrides(
        resolved_bindings, resolved_enum_bindings, resolved_date_bindings, resolved_boolean_bindings
    )
    relation_overrides = {
        relation_id: value
        for relation_id, value in sorted(
            (k.strip(), canonical_decimal_string(v)) for k, v in resolved_relations.items()
        )
        if binding_overrides.get(relation_id) != value
    }
    return CalculationReplayPayloads(
        input_values_by_casilla_id=dict(
            sorted(
                (
                    validated_casilla_id(k, surface="calculation_replay.input_values_by_casilla_id"),
                    canonical_decimal_string(v),
                )
                for k, v in resolved_inputs.items()
            ),
        ),
        binding_overrides=binding_overrides,
        row_binding_values=_row_binding_replay_values(resolved_row_bindings or {}),
        relation_overrides=relation_overrides,
    )


def _row_binding_replay_values(
    resolved_row_bindings: Mapping[tuple[BindingId, int], Decimal | str | int | bool],
) -> dict[BindingId, dict[str, str]]:
    replay_values: dict[BindingId, dict[str, str]] = {}
    for (binding_id, row_index), value in sorted(resolved_row_bindings.items()):
        if row_index < 1:
            raise ValueError(f"row binding {binding_id!r} carries non-positive row index {row_index!r}")
        row_values = replay_values.setdefault(binding_id.strip(), {})
        if isinstance(value, bool):
            # A subclass of ``int``, so tested before ``int``/``Decimal`` --
            # matches the boolean-to-Decimal("1")/Decimal("0") convention
            # already established for engine-facing binding channels (see
            # ``profile_binding._decimal_value``).
            canonical = canonical_decimal_string(Decimal("1") if value else Decimal("0"))
        elif isinstance(value, Decimal):
            canonical = canonical_decimal_string(value)
        elif isinstance(value, int):
            canonical = canonical_decimal_string(Decimal(value))
        else:
            canonical = value.strip()
        row_values[str(row_index)] = canonical
    return replay_values


def calculation_source_provenance_refs(
    provenance_rows: Sequence[CalculationSourceProvenance],
) -> tuple[CalculationSourceRef, ...]:
    """Project application source evidence into persisted domain refs.

    Maps each :class:`~application.aggregation.source_mesh.CalculationSourceProvenance`
    row (the resolver→source-object→fingerprint trace) into the domain-side
    :class:`~CalculationSourceRef` that
    :func:`~application.modelo.revision_persistence.persist_calculation_revision`
    persists on the :class:`~CalculationRevision`. This is the
    application→domain boundary map: the domain never imports the application
    provenance model, and the compact ref deliberately drops the per-casilla
    ``legal_refs`` / ``source_refs`` (carried by the revision's ``observations``)
    to avoid duplicating that grounding. ``dependency_treatment`` is NOT dropped:
    unlike the per-casilla refs, nothing else on the revision carries it, so it
    survives onto the persisted ref unchanged. ``source_casilla_ids`` is also NOT
    dropped: it is a subject identity, not grounding, and the anti-
    duplication rationale for ``legal_refs``/``source_refs`` does not extend to
    it -- nothing else on the revision recovers which casilla a general
    (non-row-materialized) source object explains. ``source_filing_year`` is
    kept for the same reason: it is the only persisted trace of a Modelo 193
    disclosure phase row's accrual year, which tells a settled prior-accrual
    row from a pending one.
    """
    return tuple(
        CalculationSourceRef(
            resolver_id=provenance.resolver_id,
            resolved_binding_source=provenance.resolved_binding_source,
            contributor_source_kind=provenance.contributor_source_kind,
            contributor_binding_source=provenance.contributor_binding_source,
            lineage_role=provenance.lineage_role,
            source_ref=provenance.source_ref,
            parent_source_ref=provenance.parent_source_ref,
            fingerprint=provenance.fingerprint,
            source_casilla_ids=provenance.source_casilla_ids,
            dependency_treatment=provenance.dependency_treatment,
            source_filing_year=provenance.source_filing_year,
        )
        for provenance in provenance_rows
    )


__all__ = [
    "OPERATOR_INPUT_SOURCE_FAMILY",
    "PRECEDENCE_TIER_DIVERGENCE_ADVISORY_REASON",
    "PRECEDENCE_TIER_DIVERGENCE_REASON",
    "CalculationReplayPayloads",
    "PrecedenceScreenContext",
    "ResolvedCalculationChannels",
    "ResolvedCalculationInputs",
    "build_calculation_replay_payloads",
    "calculation_row_binding_values",
    "calculation_source_provenance_refs",
    "operator_over_source_divergences",
    "precedence_divergence_diagnostics",
    "precedence_screen_context",
    "precedence_tier_issue",
    "resolve_calculation_binding_channels",
    "resolve_calculation_inputs",
]

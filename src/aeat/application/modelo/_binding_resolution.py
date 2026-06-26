"""Application-owned binding input resolution for modelo calculations.

Use of :class:`ModeloRevision`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from ...core import Period as _Period
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
    RelationId,
    casillas_by_id,
    enum_consumed_binding_ids,
    expression_binding_refs,
)
from ...domain.modelos._errors import ModeloError
from ..live import Borrador100SnapshotRepository
from ._borrador_binding import (
    Modelo100BorradorBindingResult,
    Modelo100BorradorSourceResolver,
)
from ._profile_binding import ProfileSourcedBindingResult
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)


@runtime_checkable
class BindingSourceResolution(Protocol):
    """The one role every binding source-resolution result fills.

    A binding source resolver answers a single question — "which registry
    bindings does source X satisfy, and with what values" — and returns the
    resolved values projected onto the engine's two scalar input channels:
    ``binding_values`` (Decimal channel) and ``enum_binding_values`` (string /
    enum-dispatch channel). :class:`ProfileSourcedBindingResult` (profile facts)
    and :class:`Modelo100BorradorBindingResult` (AEAT borrador snapshot) both
    satisfy this Protocol; each additionally carries its own provenance trace
    (``bindings_sourced_from_profile`` / ``bindings_sourced_from_borrador``) and
    source-specific metadata. The IVA-wallet compensation path feeds the same
    ``binding_values`` channel through a distinct decision-gate mechanism (the
    M303 carve-out) rather than a result object, so it is intentionally not a
    member of this Protocol.

    This Protocol names the shared role so the result types are recognisably one
    contract rather than three look-alikes; it is structural (``runtime_checkable``)
    and adds no inheritance or behaviour to the concrete results.
    """

    @property
    def binding_values(self) -> Mapping[BindingId, Decimal]: ...

    @property
    def enum_binding_values(self) -> Mapping[BindingId, str]: ...


@dataclass(frozen=True)
class CalculationBindingResolution:
    """Engine-ready inputs resolved from caller, backend, profile, and borrador sources."""

    resolved_inputs: Mapping[CasillaId, Decimal]
    resolved_bindings: Mapping[BindingId, Decimal]
    resolved_enum_bindings: Mapping[BindingId, str]
    resolved_date_bindings: Mapping[BindingId, date]
    resolved_relations: Mapping[RelationId, Decimal]
    borrador_result: Modelo100BorradorBindingResult
    profile_result: ProfileSourcedBindingResult


def resolve_calculation_binding_inputs(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    filing_year: int,
    period: _Period,
    casilla_inputs: Mapping[CasillaId, Decimal],
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    backend_binding_values: Mapping[BindingId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    borrador_snapshot_id: str | None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
    relation_values: Mapping[RelationId, Decimal] | None,
) -> CalculationBindingResolution:
    """Resolve every binding-related engine channel for one calculation.

    Returns:
        :class:`CalculationBindingResolution`: The resolved binding state.

    Use of :class:`RegistrySnapshot` for compliance.
    """
    borrador_result = _resolve_borrador_bindings_for_calculation(
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
    profile_result = _resolve_profile_bindings_for_calculation(
        bucket_id=bucket_id,
        snapshot=snapshot,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        borrador_result=borrador_result,
        backend_binding_values=backend_binding_values,
    )
    resolved_bindings = dict(
        sorted(
            {
                **profile_result.binding_values,
                **backend_binding_values,
                **borrador_result.binding_values,
                **caller_binding_values,
            }.items(),
        ),
    )
    resolved_enum_bindings = dict(
        sorted(
            {
                **profile_result.enum_binding_values,
                **borrador_result.enum_binding_values,
                **caller_enum_binding_values,
            }.items(),
        ),
    )
    resolved_date_bindings = dict(sorted(profile_result.date_binding_values.items()))
    _reject_binding_channel_mismatch(snapshot.revision, resolved_bindings, resolved_enum_bindings)

    resolved_relations = dict(relation_values or {})
    # Relation target_binding materialisation NO LONGER happens here. It moved
    # INTO RelationPrefillSourceResolver (aggregation-taxonomy ADR ruling 4), so
    # the materialised slot values arrive through the source mesh's
    # backend_binding_values channel and are adjudicated by the mesh
    # _claim_binding exclusive-ownership guard. The previous silent post-mesh
    # merge ({**relation_binding_values, **resolved_bindings}) — which let every
    # other source quietly override a relation-materialised value — is retired.
    resolved_bindings = dict(
        sorted(
            _lift_previous_filing_casilla_overrides_to_bindings(
                snapshot.revision,
                casilla_inputs,
                resolved_bindings,
            ).items(),
        ),
    )
    declaration_period_inputs = _resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=filing_year,
        period=period,
    )
    resolved_inputs = dict(
        sorted(
            {
                **declaration_period_inputs,
                **dict(backend_casilla_inputs or {}),
                **resolve_available_bound_inputs_by_casilla_id(
                    snapshot.revision,
                    resolved_bindings,
                ),
                **casilla_inputs,
            }.items(),
        ),
    )
    return CalculationBindingResolution(
        resolved_inputs=resolved_inputs,
        resolved_bindings=resolved_bindings,
        resolved_enum_bindings=resolved_enum_bindings,
        resolved_date_bindings=resolved_date_bindings,
        resolved_relations=resolved_relations,
        borrador_result=borrador_result,
        profile_result=profile_result,
    )


def _resolve_profile_bindings_for_calculation(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_enum_binding_values: Mapping[BindingId, str],
    borrador_result: Modelo100BorradorBindingResult,
    backend_binding_values: Mapping[BindingId, Decimal],
) -> ProfileSourcedBindingResult:
    """Resolve ``source = "profile"`` bindings from the bucket's user profile."""
    from ..aggregation import CalculationSourceContext, ProfileSourceResolver

    caller_owned = (
        set(caller_binding_values)
        | set(caller_enum_binding_values)
        | set(borrador_result.binding_values)
        | set(borrador_result.enum_binding_values)
        | set(backend_binding_values)
    )
    resolution = ProfileSourceResolver(
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
    return ProfileSourcedBindingResult(
        binding_values=resolution.binding_values,
        enum_binding_values=resolution.enum_binding_values,
        date_binding_values=resolution.date_binding_values,
        bindings_sourced_from_profile=tuple(
            sorted(
                set(resolution.binding_values)
                | set(resolution.enum_binding_values)
                | set(resolution.date_binding_values),
            ),
        ),
    )


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
) -> Modelo100BorradorBindingResult:
    from ..aggregation import CalculationSourceContext

    resolution = Modelo100BorradorSourceResolver(
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
    sourced = tuple(sorted(set(resolution.binding_values) | set(resolution.enum_binding_values)))
    return Modelo100BorradorBindingResult(
        borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
        binding_values=resolution.binding_values,
        enum_binding_values=resolution.enum_binding_values,
        bindings_sourced_from_borrador=sourced,
    )


def resolve_available_bound_inputs_by_casilla_id(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project available binding values into input values keyed by bound ``casilla.id``.

    Use of :class:`ModeloRevision` for compliance.
    """
    resolved: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        value = binding_values.get(casilla.binding)
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
    "CalculationBindingResolution",
    "resolve_available_bound_inputs_by_casilla_id",
    "resolve_calculation_binding_inputs",
]

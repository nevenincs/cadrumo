"""Application-owned binding input resolution for modelo calculations.

Use of :class:`ModeloRevision`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core import Period as _Period
from ...domain.calculations.registry import (
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
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


@dataclass(frozen=True)
class CalculationBindingResolution:
    """Engine-ready inputs resolved from caller, backend, profile, and borrador sources."""

    resolved_inputs: Mapping[str, Decimal]
    resolved_bindings: Mapping[str, Decimal]
    resolved_enum_bindings: Mapping[str, str]
    resolved_date_bindings: Mapping[str, date]
    resolved_relations: Mapping[str, Decimal]
    borrador_result: Modelo100BorradorBindingResult
    profile_result: ProfileSourcedBindingResult


def resolve_calculation_binding_inputs(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    filing_year: int,
    period: _Period,
    casilla_inputs: Mapping[str, Decimal],
    caller_binding_values: Mapping[str, Decimal],
    caller_enum_binding_values: Mapping[str, str],
    backend_binding_values: Mapping[str, Decimal],
    backend_casilla_inputs: Mapping[str, Decimal] | None,
    borrador_snapshot_id: str | None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
    relation_values: Mapping[str, Decimal] | None,
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
                **resolve_bound_casilla_inputs_for_available_bindings(
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
    caller_binding_values: Mapping[str, Decimal],
    caller_enum_binding_values: Mapping[str, str],
    borrador_result: Modelo100BorradorBindingResult,
    backend_binding_values: Mapping[str, Decimal],
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
    binding_values: Mapping[str, Decimal],
    enum_binding_values: Mapping[str, str],
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


def _binding_is_formula_consumed(revision: ModeloRevision, binding_id: str) -> bool:
    """Return whether any formula expression references ``binding_id``."""
    return any(binding_id in expression_binding_refs(formula.expression) for formula in revision.formulas)


def _resolve_borrador_bindings_for_calculation(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: _Period,
    borrador_snapshot_id: str | None,
    caller_binding_values: Mapping[str, Decimal],
    caller_enum_binding_values: Mapping[str, str],
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


def resolve_bound_casilla_inputs_for_available_bindings(
    revision: ModeloRevision,
    binding_values: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Project available binding values into their bound casilla input ids.

    Use of :class:`ModeloRevision` for compliance.
    """
    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        value = binding_values.get(casilla.binding)
        if value is not None:
            resolved[casilla.id] = value
    return resolved


def _lift_previous_filing_casilla_overrides_to_bindings(
    revision: ModeloRevision,
    casilla_inputs: Mapping[str, Decimal],
    resolved_bindings: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Promote operator casilla overrides for previous-filing-bound casillas into bindings."""
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    promoted: dict[str, Decimal] = {}
    for casilla_id, value in casilla_inputs.items():
        casilla = casillas_by_id.get(casilla_id)
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
) -> dict[str, Decimal]:
    """Return informational-casilla inputs sourced from work-unit metadata."""
    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.INFORMATIONAL:
            continue
        if casilla.semantic_role == "filing_year":
            resolved[casilla.id] = Decimal(filing_year)
        elif casilla.semantic_role == "filing_period":
            ordinal = _FILING_PERIOD_ORDINALS.get(period.registry_token)
            if ordinal is None:
                raise ModeloError(
                    f"work-unit period {period.registry_token!r} has no registry period ordinal; "
                    f"cannot resolve informational casilla {casilla.id!r}",
                )
            resolved[casilla.id] = Decimal(ordinal)
    return resolved


__all__ = [
    "CalculationBindingResolution",
    "resolve_bound_casilla_inputs_for_available_bindings",
    "resolve_calculation_binding_inputs",
]

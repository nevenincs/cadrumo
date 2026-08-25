"""Calculation input-channel resolution helpers.

The helpers merge caller, backend, profile, and borrador channels for a
:class:`RegistrySnapshot`, then build the canonical input map consumed by the
selected :class:`ModeloRevision`.

This module is the calculation-service assembly layer between source resolution
and engine execution. It delegates source-specific work to the binding
resolution helpers, then returns typed channel bundles that
:func:`application.modelo.calculate_modelo_revision` can pass to
:func:`domain.calculations.registry.calculate_registry_snapshot` and the
:class:`CalculationRevision` persistence boundary.

See Also:
    :func:`application.modelo._binding_resolution.resolve_borrador_source_tier`
        Resolves the optional borrador tier before the final precedence merge.
    :func:`application.modelo._binding_resolution.resolve_profile_source_tier`
        Resolves profile-sourced bindings as the lowest-precedence tier.
    :func:`application.aggregation.merge_source_resolutions_by_precedence`
        Applies the ordered overlay contract used by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core import CasillaId, Period, validated_casilla_id
from ...domain.identifiers import canonical_decimal_string as _canonical_decimal_str
from ...domain.calculations.registry import (
    BindingId,
    ModeloRevision,
    RegistrySnapshot,
    RelationId,
    resolve_available_bound_inputs_by_casilla_id,
)
from ...domain.modelos import WorkUnit
from ..aggregation import CalculationSourceResolution, merge_source_resolutions_by_precedence
from ._binding_resolution import (
    lift_previous_filing_casilla_overrides_to_bindings,
    reject_binding_channel_mismatch,
    resolve_borrador_source_tier,
    resolve_declaration_period_inputs,
    resolve_profile_source_tier,
)

if TYPE_CHECKING:
    from ..live import Borrador100SnapshotRepository


@dataclass(frozen=True, slots=True)
class ResolvedCalculationChannels:
    """Merged engine binding channels for one calculation.

    ``bindings`` feeds the Decimal channel, ``enum_bindings`` feeds string
    dispatch keys, and ``date_bindings`` feeds date-valued profile bindings.
    The borrador fields carry the typed snapshot trace from
    :class:`~application.aggregation.CalculationSourceResolution` through to
    the persisted :class:`CalculationRevision`.
    """

    bindings: dict[BindingId, Decimal]
    enum_bindings: dict[BindingId, str]
    date_bindings: dict[BindingId, date]
    borrador_snapshot_id: str | None
    bindings_sourced_from_borrador: tuple[BindingId, ...]


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
) -> ResolvedCalculationChannels:
    """Resolve all binding channels for ``work_unit`` and ``snapshot``.

    The ``work_unit`` is the :class:`WorkUnit` whose bucket, filing year, and
    period select the source-resolution axis. The ``snapshot`` is the
    :class:`RegistrySnapshot` supplying the revision whose binding
    channels are being resolved.

    The source-precedence ladder is profile, backend, borrador, then caller. The
    returned :class:`ResolvedCalculationChannels` contains the merged Decimal,
    enum, and date channels, plus any
    :class:`~application.live.Borrador100SnapshotRepository` provenance,
    after
    :func:`application.modelo._binding_resolution.reject_binding_channel_mismatch`
    verifies the registry-declared channel shape and
    :func:`application.modelo._binding_resolution.lift_previous_filing_casilla_overrides_to_bindings`
    mirrors eligible previous-filing casilla overrides onto their binding ids.
    """
    borrador_resolution = resolve_borrador_source_tier(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        borrador_snapshot_repository=borrador_snapshot_repository,
    )
    profile_resolution = resolve_profile_source_tier(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        borrador_resolution=borrador_resolution,
        backend_binding_values=backend_binding_values,
    )
    backend_tier = CalculationSourceResolution(
        resolver_id="calculate_backend_bindings",
        binding_values=dict(backend_binding_values),
    )
    caller_tier = CalculationSourceResolution(
        resolver_id="calculate_caller_bindings",
        binding_values=dict(caller_binding_values),
        enum_binding_values=dict(caller_enum_binding_values),
    )
    merged = merge_source_resolutions_by_precedence(
        (profile_resolution, backend_tier, borrador_resolution, caller_tier),
    )
    resolved_bindings = dict(sorted(merged.binding_values.items()))
    resolved_enum_bindings = dict(sorted(merged.enum_binding_values.items()))
    resolved_date_bindings = dict(sorted(merged.date_binding_values.items()))
    reject_binding_channel_mismatch(snapshot.revision, resolved_bindings, resolved_enum_bindings)
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
    return ResolvedCalculationChannels(
        bindings=resolved_bindings,
        enum_bindings=resolved_enum_bindings,
        date_bindings=resolved_date_bindings,
        borrador_snapshot_id=borrador_provenance.snapshot_id if borrador_provenance is not None else None,
        bindings_sourced_from_borrador=(
            borrador_provenance.bindings_sourced if borrador_provenance is not None else ()
        ),
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
) -> ResolvedCalculationInputs:
    """Build the canonical casilla input maps for engine execution.

    The ``revision`` is the :class:`ModeloRevision` whose declaration-period and
    bound casilla inputs are being projected. The :class:`~core.Period`
    supplies the filing-period casilla values that the registry declares as
    inputs.

    Declaration-period bindings are projected first, followed by backend casilla
    inputs, bound casillas resolved from merged binding values, and finally the
    caller's explicit casilla overrides. Both returned maps are sorted for stable
    replay payloads and revision identity.

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
                    **dict(text_casilla_inputs or {}),
                }.items(),
            ),
        ),
    )


def build_calculation_replay_payloads(
    *,
    resolved_inputs: Mapping[CasillaId, Decimal],
    resolved_bindings: Mapping[BindingId, Decimal],
    resolved_enum_bindings: Mapping[BindingId, str],
    resolved_date_bindings: Mapping[BindingId, date],
    resolved_relations: Mapping[RelationId, Decimal],
    resolved_row_bindings: Mapping[tuple[BindingId, int], Decimal | str] | None = None,
) -> CalculationReplayPayloads:
    """Convert resolved engine inputs into persisted :class:`CalculationReplayPayloads`.

    Casilla and relation Decimals are canonicalized with the domain decimal
    formatter. Decimal, enum, and date binding channels share the single
    ``binding_overrides`` replay map because that is the persisted scalar
    :class:`CalculationRevision` contract. Row-indexed bindings are carried in
    ``row_binding_values`` so the row coordinate remains structured for draft
    and export replay instead of being encoded into a synthetic binding id. The
    replay payload is built after source precedence and bound-casilla projection
    so its values match the engine inputs exactly.
    """
    return CalculationReplayPayloads(
        input_values_by_casilla_id=dict(
            sorted(
                (
                    validated_casilla_id(k, surface="calculate_modelo_revision.input_values_by_casilla_id"),
                    _canonical_decimal_str(v),
                )
                for k, v in resolved_inputs.items()
            ),
        ),
        binding_overrides=dict(
            sorted(
                [(k.strip(), _canonical_decimal_str(v)) for k, v in resolved_bindings.items()]
                + [(k.strip(), v.strip()) for k, v in resolved_enum_bindings.items()]
                + [(k.strip(), v.isoformat()) for k, v in resolved_date_bindings.items()],
            ),
        ),
        row_binding_values=_row_binding_replay_values(resolved_row_bindings or {}),
        relation_overrides=dict(
            sorted((k.strip(), _canonical_decimal_str(v)) for k, v in resolved_relations.items()),
        ),
    )


def _row_binding_replay_values(
    resolved_row_bindings: Mapping[tuple[BindingId, int], Decimal | str],
) -> dict[BindingId, dict[str, str]]:
    replay_values: dict[BindingId, dict[str, str]] = {}
    for (binding_id, row_index), value in sorted(resolved_row_bindings.items()):
        if row_index < 1:
            raise ValueError(f"row binding {binding_id!r} carries non-positive row index {row_index!r}")
        row_values = replay_values.setdefault(binding_id.strip(), {})
        row_values[str(row_index)] = _canonical_decimal_str(value) if isinstance(value, Decimal) else value.strip()
    return replay_values


__all__ = [
    "CalculationReplayPayloads",
    "ResolvedCalculationChannels",
    "ResolvedCalculationInputs",
    "build_calculation_replay_payloads",
    "resolve_calculation_binding_channels",
    "resolve_calculation_inputs",
]

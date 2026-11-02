"""Resolve repeating profile bindings into row values from stored row objects.

A row-object binding reads one leaf of ``{object_path}.{n}.{leaf}`` for every
stored row ``n``. A row exists when any of its leaves is stored, so a leaf the
filer left blank on an existing row stays an unknown cell rather than shifting
the rows below it. Rows are numbered from one in stored order, the row-set
channel's coordinate.

The rows alone cannot tell a filer who declared none from one who has not
answered. The object's stated count can, but only when it is exactly zero: when
rows are stored, or the count is stated as zero, the resolver records a source
trace naming the boxes the binding feeds. That trace is the persisted positive
fact a reader needs to show an empty group as declared empty. A non-zero count
with no stored rows is a household the filer has described but not entered, so it
records no trace and the group stays unknown, like an unanswered one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.profile_bindings import ProfileProvider, ProfileRowsSelector
from ..aggregation.source_mesh import CalculationSourceProvenance, RowBindingValue

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
    from ...domain.calculations.row_source_identity import RowBindingKey
    from ...domain.user_profile.values import UserProfileFactValue

__all__ = ["ProfileRowResolution", "profile_row_bindings", "resolve_profile_row_values"]


@dataclass(frozen=True, slots=True)
class ProfileRowResolution:
    """Row values and the source traces that state which row sets were enumerated."""

    row_binding_values: dict[RowBindingKey, RowBindingValue]
    provenance: tuple[CalculationSourceProvenance, ...]


def profile_row_bindings(snapshot: RegistrySnapshot) -> tuple[BindingDefinition, ...]:
    """Return the revision's bindings that read a leaf of a stored row object."""
    return tuple(
        binding
        for binding in snapshot.revision.bindings
        if isinstance(binding.provider, ProfileProvider) and binding.provider.rows is not None
    )


def _row_indexes(selector: ProfileRowsSelector, fact_index: Mapping[str, UserProfileFactValue]) -> tuple[int, ...]:
    pattern = re.compile(rf"^{re.escape(selector.object_path)}\.(\d+)\.[a-z][a-z0-9_]*$")
    found = {int(match.group(1)) for path in fact_index if (match := pattern.match(path)) is not None}
    return tuple(sorted(found))


def _row_value(value: UserProfileFactValue) -> RowBindingValue | None:
    if isinstance(value, bool | int | Decimal):
        return value
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _count_is_stated_zero(selector: ProfileRowsSelector, fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    value = fact_index.get(selector.count_path)
    if value is None or isinstance(value, bool):
        return False
    try:
        return Decimal(str(value).strip()) == 0
    except InvalidOperation:
        return False


def _bound_casillas(snapshot: RegistrySnapshot, binding_id: BindingId) -> tuple[CasillaId, ...]:
    return tuple(
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.binding == binding_id or binding_id in casilla.alternate_bindings
    )


def resolve_profile_row_values(
    snapshot: RegistrySnapshot,
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    bucket_id: str,
    fingerprint: str | None,
    caller_binding_ids: frozenset[BindingId],
    resolver_id: str,
) -> ProfileRowResolution:
    """Resolve every row-object profile binding the revision declares.

    Returns:
        The row values keyed by binding and row index, and one source trace per
        binding whose rows are stored or whose object states a count of zero.
    """
    values: dict[RowBindingKey, RowBindingValue] = {}
    provenance: list[CalculationSourceProvenance] = []
    for binding in profile_row_bindings(snapshot):
        provider = binding.provider
        if binding.id in caller_binding_ids or not isinstance(provider, ProfileProvider) or provider.rows is None:
            continue
        selector = provider.rows
        indexes = _row_indexes(selector, fact_index)
        for position, index in enumerate(indexes, start=1):
            raw = fact_index.get(selector.row_path(index))
            value = None if raw is None else _row_value(raw)
            if value is not None:
                values[(binding.id, position)] = value
        if not indexes and not _count_is_stated_zero(selector, fact_index):
            continue
        provenance.append(
            CalculationSourceProvenance(
                resolver_id=resolver_id,
                resolved_binding_source=BindingSourceKind.PROFILE,
                contributor_source_kind=BindingSourceKind.PROFILE.value,
                contributor_binding_source=BindingSourceKind.PROFILE,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"profile:{bucket_id}:rows:{binding.id}",
                parent_source_ref=None,
                terminal_origin=TerminalOriginClass.PROFILE_FIELD,
                fingerprint=fingerprint,
                source_casilla_ids=_bound_casillas(snapshot, binding.id),
            )
        )
    return ProfileRowResolution(row_binding_values=values, provenance=tuple(provenance))

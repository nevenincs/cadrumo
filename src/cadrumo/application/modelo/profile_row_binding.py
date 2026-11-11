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

A stated count larger than the stored rows (three stated, one recorded) is an
incomplete group, never a complete one. The stored rows are still served, and the
resolver raises one ``household_rows_incomplete`` diagnostic per object whose
fact states the two numbers, so the group is not read as proven complete.

A leaf the official design requires of every row (the selector's ``required``)
is owed by each stored row that states no value for it. The resolver then raises
one ``household_row_fact_unstated`` diagnostic per object and leaf, whose fact
counts the rows that omit it. The cell stays unknown; nothing stands in for the
missing value. :class:`RegistrySnapshot` is the pinned registry snapshot.
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
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ..aggregation.source_mesh import CalculationSourceDiagnostic, CalculationSourceProvenance, RowBindingValue

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
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def profile_row_bindings(snapshot: RegistrySnapshot) -> tuple[BindingDefinition, ...]:
    """Return the revision's bindings that read a leaf of a stored row object.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
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


def _stated_count(selector: ProfileRowsSelector, fact_index: Mapping[str, UserProfileFactValue]) -> Decimal | None:
    """The count the object states, or ``None`` when it states none or not a number."""
    value = fact_index.get(selector.count_path)
    if value is None or isinstance(value, bool):
        return None
    try:
        count = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return count if count.is_finite() else None


def _incomplete_diagnostic(
    selector: ProfileRowsSelector,
    stated: Decimal,
    recorded: int,
    *,
    bucket_id: str,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    stated_text = format(stated.normalize(), "f")
    return CalculationSourceDiagnostic(
        reason="household_rows_incomplete",
        source_kind=BindingSourceKind.PROFILE.value,
        binding_source=BindingSourceKind.PROFILE,
        message=(
            f"profile object {selector.object_path!r} states {stated_text} rows through "
            f"{selector.count_path!r} but records {recorded}; the recorded rows are used and the group is not complete"
        ),
        resolver_id=resolver_id,
        source_ref=f"profile:{bucket_id}:rows:{selector.object_path}",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.HOUSEHOLD_ROWS_INCOMPLETE,
            group=selector.object_path,
            stated=stated_text,
            recorded=recorded,
        ),
    )


def _unstated_diagnostic(
    selector: ProfileRowsSelector,
    omitting: int,
    recorded: int,
    *,
    bucket_id: str,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="household_row_fact_unstated",
        source_kind=BindingSourceKind.PROFILE.value,
        binding_source=BindingSourceKind.PROFILE,
        message=(
            f"profile object {selector.object_path!r} records {recorded} rows, "
            f"{omitting} of them without the required {selector.leaf!r}"
        ),
        resolver_id=resolver_id,
        source_ref=f"profile:{bucket_id}:rows:{selector.object_path}.{selector.leaf}",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.HOUSEHOLD_ROW_FACT_UNSTATED,
            group=selector.object_path,
            leaf=selector.leaf,
            omitting=omitting,
            recorded=recorded,
        ),
    )


def _unstated_note(
    selector: ProfileRowsSelector, recorded: int, stated_rows: int, *, bucket_id: str, resolver_id: str
) -> CalculationSourceDiagnostic | None:
    """The note for a required leaf that some stored rows omit, or ``None`` when none does."""
    omitting = recorded - stated_rows
    if not selector.required or omitting <= 0:
        return None
    return _unstated_diagnostic(selector, omitting, recorded, bucket_id=bucket_id, resolver_id=resolver_id)


def _incomplete_note(
    selector: ProfileRowsSelector, stated: Decimal | None, recorded: int, *, bucket_id: str, resolver_id: str
) -> CalculationSourceDiagnostic | None:
    """The note for a stated count larger than the stored rows, or ``None`` when it is not."""
    if stated is None or stated <= recorded:
        return None
    return _incomplete_diagnostic(selector, stated, recorded, bucket_id=bucket_id, resolver_id=resolver_id)


def _bound_casillas(snapshot: RegistrySnapshot, binding_id: BindingId) -> tuple[CasillaId, ...]:
    return tuple(
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.binding == binding_id or binding_id in casilla.alternate_bindings
    )


def _stored_row_values(
    binding_id: BindingId,
    selector: ProfileRowsSelector,
    indexes: tuple[int, ...],
    fact_index: Mapping[str, UserProfileFactValue],
) -> dict[RowBindingKey, RowBindingValue]:
    """Read the stored rows of one object, keyed by binding and one-based row position."""
    values: dict[RowBindingKey, RowBindingValue] = {}
    for position, index in enumerate(indexes, start=1):
        raw = fact_index.get(selector.row_path(index))
        value = None if raw is None else _row_value(raw)
        if value is not None:
            values[(binding_id, position)] = value
    return values


def _row_provenance(
    snapshot: RegistrySnapshot,
    binding_id: BindingId,
    *,
    bucket_id: str,
    fingerprint: str | None,
    resolver_id: str,
) -> CalculationSourceProvenance:
    """Trace one row binding back to the profile object it was read from."""
    return CalculationSourceProvenance(
        resolver_id=resolver_id,
        resolved_binding_source=BindingSourceKind.PROFILE,
        contributor_source_kind=BindingSourceKind.PROFILE.value,
        contributor_binding_source=BindingSourceKind.PROFILE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"profile:{bucket_id}:rows:{binding_id}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.PROFILE_FIELD,
        fingerprint=fingerprint,
        source_casilla_ids=_bound_casillas(snapshot, binding_id),
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
        The row values keyed by binding and row index, one source trace per
        binding whose rows are stored or whose object states a count of zero, and
        one diagnostic per object whose stated count exceeds its stored rows, and
        one per required leaf that a stored row omits.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    values: dict[RowBindingKey, RowBindingValue] = {}
    provenance: list[CalculationSourceProvenance] = []
    incomplete: dict[str, CalculationSourceDiagnostic] = {}
    unstated: list[CalculationSourceDiagnostic] = []
    for binding in profile_row_bindings(snapshot):
        provider = binding.provider
        if binding.id in caller_binding_ids or not isinstance(provider, ProfileProvider) or provider.rows is None:
            continue
        selector = provider.rows
        indexes = _row_indexes(selector, fact_index)
        stored = _stored_row_values(binding.id, selector, indexes, fact_index)
        values.update(stored)
        omitted = _unstated_note(selector, len(indexes), len(stored), bucket_id=bucket_id, resolver_id=resolver_id)
        if omitted is not None:
            unstated.append(omitted)
        stated = _stated_count(selector, fact_index)
        if selector.object_path not in incomplete:
            short = _incomplete_note(selector, stated, len(indexes), bucket_id=bucket_id, resolver_id=resolver_id)
            if short is not None:
                incomplete[selector.object_path] = short
        if indexes or stated == 0:
            provenance.append(
                _row_provenance(
                    snapshot, binding.id, bucket_id=bucket_id, fingerprint=fingerprint, resolver_id=resolver_id
                )
            )
    return ProfileRowResolution(
        row_binding_values=values,
        provenance=tuple(provenance),
        diagnostics=(*incomplete.values(), *unstated),
    )

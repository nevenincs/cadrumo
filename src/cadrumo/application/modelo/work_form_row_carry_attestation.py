"""The rows of a repeating group whose carry the filer can still state holds nothing, one statement per row.

Some carries are stated row by row: the interest and repair expenses a let
property still carries from earlier ejercicios are stated per property and
per origin year (Ley 35/2006 art. 23.1.a; RIRPF art. 13.a). Each row the
current calculation holds for the carry's source takes one statement naming
it, over the carry columns of that row the calculation still asks about: a
note of the calculation names the column and the row, and the filer has not
stated it. A column the calculation resolved, a zero included, is not asked
about, because a resolved zero leaves the box off and so cannot be told apart
from an unknown one by the row's values. A form with no calculation holds no
row and offers none.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.ids import BindingId
from ...domain.modelos.calculation_revision import CalculationRevision
from .edit_models import ModeloEditBindingIntentKind, ModeloEditWritableBindingOverrideSurfaceEntryV1
from .edit_row_statement_withdrawal import calculated_row_indexes
from .work_form_context import WorkFormContext

_NOTE_COLUMN: Final = "binding"
"""The value under which a calculation note names the column whose statement settles it."""


@dataclass(frozen=True, slots=True)
class OpenCarryRow:
    """One row of a row-stated family whose carry the calculation still asks about."""

    family: AbsenceAttestationFamily
    #: The source identity of the row, as the calculation holds it.
    row_identity: str
    #: The row's index in its repeating group, as the form numbers its rows.
    index: int
    #: The carry columns of the row the calculation asks a statement of, sorted.
    binding_ids: tuple[BindingId, ...]


def _row_doors(context: WorkFormContext) -> dict[AbsenceAttestationFamily, list[BindingId]]:
    """The row-stated carry columns the edit admits a statement of absence on, by family."""
    doors: dict[AbsenceAttestationFamily, list[BindingId]] = {}
    for entry in (context.surface or {}).values():
        if not isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
            continue
        binding = context.bindings.get(entry.binding_id)
        family = None if binding is None else binding.absence_attestation
        if (
            family is not None
            and family.row_grain
            and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
        ):
            doors.setdefault(family, []).append(entry.binding_id)
    return doors


def _stated_keys(head: CalculationRevision) -> frozenset[tuple[BindingId, str]]:
    layer = head.operator_layer
    return frozenset(()) if layer is None else frozenset(statement.key for statement in layer.row_attestations)


def _asked_keys(head: CalculationRevision) -> frozenset[tuple[str, str]]:
    """The column and row each note of ``head`` asks a statement of, as the note names them."""
    asked: set[tuple[str, str]] = set()
    for issue in head.source_issues:
        column = None if issue.fact is None else dict(issue.fact.values).get(_NOTE_COLUMN)
        if column is not None and issue.fact is not None:
            asked.update((column, row) for row in issue.fact.row_refs)
    return frozenset(asked)


def _family_rows(
    context: WorkFormContext, head: CalculationRevision, family: AbsenceAttestationFamily, columns: list[BindingId]
) -> Iterator[OpenCarryRow]:
    """Each row the calculation holds for ``columns``' source with a column still asked about, in row order."""
    stated = _stated_keys(head)
    asked = _asked_keys(head)
    rows: dict[str, int] = {}
    for binding_id in columns:
        rows.update(calculated_row_indexes(head, context.snapshot.revision, binding_id))
    for identity, index in sorted(rows.items(), key=lambda item: item[1]):
        open_columns = tuple(
            sorted(
                binding_id
                for binding_id in columns
                if (binding_id, identity) in asked and (binding_id, identity) not in stated
            )
        )
        if open_columns:
            yield OpenCarryRow(family=family, row_identity=identity, index=index, binding_ids=open_columns)


def open_carry_rows(context: WorkFormContext) -> tuple[OpenCarryRow, ...]:
    """Every row whose row-stated carry the calculation still asks a statement of.

    None on a form that admits no edit or holds no calculation.
    """
    head = context.revision
    if context.surface is None or head is None:
        return ()
    doors = _row_doors(context)
    return tuple(
        row
        for family in AbsenceAttestationFamily
        if family in doors
        for row in _family_rows(context, head, family, doors[family])
    )


__all__ = ["OpenCarryRow", "open_carry_rows"]

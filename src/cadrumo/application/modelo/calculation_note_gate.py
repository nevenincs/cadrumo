"""Refuse to check, export or record a declaration while its calculation left a figure out of every box.

A calculation persists the notes that mean an amount from the filer's records
reached no box, that the IVA owed on a reverse-charge invoice could not be
derived, that a box the form prints could not be worked out, or that a source
has no route or could not be read yet
(:data:`~.calculation_notes.GATE_REFUSED_REASONS`). While the current
calculation carries one, no entrypoint may produce a complete check, an export
file or a recorded filing from it: a recalculation that clears the note
releases them. The refusal is worded by the same catalogue sentence the
editor's findings list shows.

An unrouted one-stop-shop row is left to the Modelo 369 check, which reads it
with its own evidence, as the other reasons the application refuses on are
left to their own check step or to the export
(:data:`~.calculation_notes.BLOCKING_REASONS`).

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
"""

from __future__ import annotations

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationSourceIssue
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import ModeloPreconditionErrorMixin
from .calculation_notes import GATE_REFUSED_REASONS, what_locale_key
from .printed_boxes import PrintedBoxes, snapshot_printed_boxes


class ModeloCalculationBlockedError(ModeloPreconditionErrorMixin, ModeloError):
    """The current calculation carries a note that withholds this action until a recalculation clears it."""


def _refused_here(issue: CalculationSourceIssue) -> bool:
    """Whether the gate refuses on ``issue``; an unrouted one-stop-shop row is the Modelo 369 check's to decide."""
    if issue.reason not in GATE_REFUSED_REASONS:
        return False
    return not (
        issue.reason == "unrouted_observation" and issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION
    )


def blocking_calculation_issues(revision: CalculationRevision) -> tuple[CalculationSourceIssue, ...]:
    """The persisted notes of ``revision`` that withhold checking, exporting and recording it.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    return tuple(issue for issue in revision.source_issues if _refused_here(issue))


def require_no_blocking_calculation_notes(
    revision: CalculationRevision,
    *,
    action: str,
    boxes: PrintedBoxes | None = None,
) -> None:
    """Refuse ``action`` while ``revision`` carries a persisted blocking note.

    The refusal is worded by the first note's own catalogue sentence and
    carries every note's reason in its context. ``boxes`` are the boxes the
    revision's form prints, used to name the note's box by its printed number.

    Raises:
        ModeloCalculationBlockedError: The revision carries a blocking note.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    blocking = blocking_calculation_issues(revision)
    if not blocking:
        return
    first = blocking[0]
    box = None if boxes is None or first.casilla_id is None else boxes.number(str(first.casilla_id))
    raise ModeloCalculationBlockedError(
        translated_message=what_locale_key(first.reason),
        context={
            "action": action,
            "calculation_revision_id": revision.calculation_revision_id,
            "reason": first.reason,
            "reasons": ",".join(sorted({issue.reason for issue in blocking})),
            **({} if box is None else {"box": box}),
        },
    )


def require_work_unit_calculation_unblocked(
    *, work_unit: WorkUnit, revision: CalculationRevision, action: str, operation: PinnedAuthorityOperation
) -> None:
    """Refuse ``action`` on ``work_unit`` while its ``revision`` carries a persisted blocking note.

    Raises:
        ModeloCalculationBlockedError: The revision carries a blocking note.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    if not blocking_calculation_issues(revision):
        return
    snapshot = operation.snapshot(
        str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period.registry_token
    )
    require_no_blocking_calculation_notes(revision, action=action, boxes=snapshot_printed_boxes(operation, snapshot))


__all__ = [
    "ModeloCalculationBlockedError",
    "blocking_calculation_issues",
    "require_no_blocking_calculation_notes",
    "require_work_unit_calculation_unblocked",
]

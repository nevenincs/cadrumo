"""Refuse to check, export or record a declaration while its calculation says a filed figure is missing.

A calculation persists the notes that mean a figure from the filer's records
reached no box, or that a filed figure could not be worked out or trusted
(:data:`~.calculation_notes.BLOCKING_REASONS`). While the current calculation
carries one, no entrypoint may produce a complete check, an export file or a
recorded filing from it: a recalculation that clears the note releases them.

A persisted reason that the check itself adjudicates with its own evidence is
left to that check, and a reason whose producer still fires for sources that
do not apply is not refused yet: the selected-scope and annual-partition VAT evidence, an
empty withholdings detail, which the filer may attest, and an unrouted
one-stop-shop row, which the Modelo 369 check reads. Every other blocking
reason is refused here, worded by the same catalogue sentence the editor's
findings list shows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationSourceIssue
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import ModeloPreconditionErrorMixin
from .calculation_notes import BLOCKING_REASONS, printed_box_number, what_locale_key

_ADJUDICATED_BY_THE_CHECK: Final[frozenset[str]] = frozenset(
    {
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
    }
)
"""Blocking reasons a check step of verification reads with its own evidence and decides itself."""
_NOT_YET_ENFORCED: Final[frozenset[str]] = frozenset(
    {"unresolved_binding", "unhandled_binding_source", "source_domain_not_ready", "terminal_origin_mismatch"}
)
"""Blocking reasons whose producers still fire for sources that do not apply to the filer.

They are shown and persisted, but refusing on them would refuse valid declarations: a salaried
filer with no activity ledger, a binding with no resolver yet, a Modelo 720 row that arrives by
its producer. The refusal waits until their producers skip sources that do not apply.
"""


class ModeloCalculationBlockedError(ModeloPreconditionErrorMixin, ModeloError):
    """The current calculation carries a note that withholds this action until a recalculation clears it."""


def _adjudicated_by_the_check(issue: CalculationSourceIssue) -> bool:
    if issue.reason in _ADJUDICATED_BY_THE_CHECK or issue.reason in _NOT_YET_ENFORCED:
        return True
    return issue.reason == "unrouted_observation" and issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION


def blocking_calculation_issues(revision: CalculationRevision) -> tuple[CalculationSourceIssue, ...]:
    """The persisted notes of ``revision`` that withhold checking, exporting and recording it."""
    return tuple(
        issue
        for issue in revision.source_issues
        if issue.reason in BLOCKING_REASONS and not _adjudicated_by_the_check(issue)
    )


def require_no_blocking_calculation_notes(
    revision: CalculationRevision,
    *,
    action: str,
    casillas: Mapping[str, CasillaDefinition] | None = None,
) -> None:
    """Refuse ``action`` while ``revision`` carries a persisted blocking note.

    The refusal is worded by the first note's own catalogue sentence and
    carries every note's reason in its context. ``casillas`` are the
    revision's casilla definitions, used to name the note's box by its printed
    number.

    Raises:
        ModeloCalculationBlockedError: The revision carries a blocking note.
    """
    blocking = blocking_calculation_issues(revision)
    if not blocking:
        return
    first = blocking[0]
    casilla = None if first.casilla_id is None or casillas is None else casillas.get(str(first.casilla_id))
    box = printed_box_number(casilla)
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
    """
    if not blocking_calculation_issues(revision):
        return
    snapshot = operation.snapshot(
        str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period.registry_token
    )
    require_no_blocking_calculation_notes(
        revision,
        action=action,
        casillas={str(casilla.id): casilla for casilla in snapshot.revision.casillas},
    )


__all__ = [
    "ModeloCalculationBlockedError",
    "blocking_calculation_issues",
    "require_no_blocking_calculation_notes",
    "require_work_unit_calculation_unblocked",
]

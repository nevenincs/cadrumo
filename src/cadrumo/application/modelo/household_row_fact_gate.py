"""Refusal for a household row that omits a fact the official design requires of it.

The profile door admits an ascendant before the filer has stated every fact the
declaration needs, because the filer can add the rest later. The Modelo 100 design
requires some of those facts on every row, such as an ascendant's NIF or a descendant's surnames and name, so a
calculation records each omission as a ``household_row_fact_unstated`` note. While
the current calculation carries one, checking, local filing and export refuse with
one typed reason that names the missing fact and the profile door where it is
stated. The refusal never substitutes a placeholder for the fact.

Calculation itself is not refused: the note persists with the revision, and a
recalculation after the profile states the fact clears it.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying the persisted notes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ...domain.modelos.errors import ModeloError
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

HOUSEHOLD_ROW_FACT_UNSTATED_REASON: Final[str] = "household_row_fact_unstated"
"""The persisted note reason this gate refuses on."""

_STAGE_LEAVES: Final[dict[str, str]] = {
    "verify": "modelo.work.verify",
    "file": "modelo.work.file",
    "export": "modelo.export",
}
"""The operator leaf each gated action refuses at."""

_GROUP_DOORS: Final[dict[str, tuple[str, str]]] = {
    "renta_family.ascendiente": ("ascendiente_unstated", "operator.profile.ascendiente"),
    "renta_family.descendiente": ("descendiente_unstated", "operator.profile.descendiente"),
}
"""The declared scenario and profile door of each household group that has a required fact.

The scenario and door are declared with the precondition profiles in :mod:`.preconditions`.
"""

_ROW_DOORS: Final[dict[str, str]] = {
    "renta_family.ascendiente": "ascendiente_row",
}
"""The scenario of a group whose note names the row that omits the fact, so the door edits that row.

The door takes the row's 0-based position, which the note carries, and the fact the filer states,
which only the filer has.
"""
_ROW_DOOR_FACT_ARGUMENT: Final = "ascendiente"


class ModeloHouseholdRowFactUnstatedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a household row omits a fact the official design requires and the profile has not stated it."""


def household_row_fact_unstated_issues(
    issues: Sequence[CalculationSourceIssue],
) -> tuple[CalculationSourceIssue, ...]:
    """The notes among ``issues`` that report a required household fact as unstated."""
    return tuple(issue for issue in issues if issue.reason == HOUSEHOLD_ROW_FACT_UNSTATED_REASON)


def _fact_value(issue: CalculationSourceIssue, name: str) -> str | None:
    if issue.fact is None:
        return None
    return next((value for key, value in issue.fact.values if key == name), None)


def _door_scenario(issue: CalculationSourceIssue, group: str, group_scenario: str) -> tuple[str, int | None]:
    """The scenario that names the refusal's door, and the row it points at when the group has a row door."""
    row = issue.fact.row_refs[0] if issue.fact is not None and issue.fact.row_refs else None
    row_scenario = _ROW_DOORS.get(group)
    if row is None or row_scenario is None:
        return group_scenario, None
    return f"{row_scenario}_unstated", int(row)


def household_row_fact_refusal(
    revision: CalculationRevision,
    issues: Sequence[CalculationSourceIssue],
    *,
    action: str,
) -> ModeloHouseholdRowFactUnstatedError | None:
    """Build the typed refusal for ``action`` on ``revision``, or ``None`` where this gate does not decide it.

    The first unstated fact names the refusal and its door; ``action`` is the
    gated verb (``verify``, ``file`` or ``export``). A note whose group has no
    declared door, or an action this gate does not stand at, is left to the
    calculation-note gate's own refusal, which still blocks.
    """
    leaf = _STAGE_LEAVES.get(action)
    unstated = household_row_fact_unstated_issues(issues)
    if leaf is None or not unstated:
        return None
    first = unstated[0]
    group = _fact_value(first, "group")
    fact_leaf = _fact_value(first, "leaf")
    omitting = _fact_value(first, "omitting")
    recorded = _fact_value(first, "recorded")
    door = None if group is None else _GROUP_DOORS.get(group)
    if group is None or fact_leaf is None or omitting is None or recorded is None or door is None:
        return None
    scenario, row = _door_scenario(first, group, door[0])
    return ModeloHouseholdRowFactUnstatedError(
        translated_message="errors.refused.refused_modelo_household_row_fact_unstated",
        context={
            "action": action,
            "calculation_revision_id": revision.calculation_revision_id,
            "reason": HOUSEHOLD_ROW_FACT_UNSTATED_REASON,
            "field": f"{group}.{fact_leaf}",
            "count": omitting,
        },
        precondition_failure=household_row_fact_unstated_failure(
            revision,
            leaf=leaf,
            scenario=scenario,
            group=group,
            fact_leaf=fact_leaf,
            omitting=int(omitting),
            recorded=int(recorded),
            row=row,
        ),
    )


def household_row_fact_unstated_failure(
    revision: CalculationRevision,
    *,
    leaf: str,
    scenario: str,
    group: str,
    fact_leaf: str,
    omitting: int,
    recorded: int,
    row: int | None = None,
) -> ModeloPreconditionFailure:
    """Build the declared verdict that sends the filer to the profile door that states the fact.

    With ``row``, the door is the edit of that 0-based row, and the fact to state is left to the filer.
    """
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.household_row_facts.{scenario}",
        evidence_id=f"{leaf}.household_row_facts",
        evidence_values={
            "calculation_revision_id": revision.calculation_revision_id,
            "group": group,
            "leaf": fact_leaf,
            "rows_recorded": recorded,
            "rows_omitting": omitting,
            "fact_stated": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=None if row is None else {"index": row},
        missing_action_arguments=() if row is None else (_ROW_DOOR_FACT_ARGUMENT,),
    )


__all__ = [
    "HOUSEHOLD_ROW_FACT_UNSTATED_REASON",
    "ModeloHouseholdRowFactUnstatedError",
    "household_row_fact_refusal",
    "household_row_fact_unstated_failure",
    "household_row_fact_unstated_issues",
]

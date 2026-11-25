"""Refusal of a calculation whose value waits on a household row fact the profile never stated.

The household row fact gate declares, for each household group, the profile door that
states a row's required fact. A derived value that waits on such a fact, such as the
deduccion por maternidad limited by the mother's cotizaciones, leaves its binding
without a value; the calculation then refuses with that group's door and the stored
positions of the rows that omit the fact, instead of asking for the derived value.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.work_unit import WorkUnit
from ..operations.next_step import OperationNextStepWording
from .household_row_fact_gate import GROUP_DOORS, HOUSEHOLD_ROW_FACT_UNSTATED_REASON
from .preconditions import build_modelo_precondition_failure_for_scenario
from .projection_next_steps import open_work_step
from .work_missing_input import ModeloWorkMissingInputError

_MESSAGE_KEY: Final[str] = "errors.refused.refused_modelo_household_row_fact_unstated"
_CALCULATE_LEAF: Final[str] = "modelo.work.calculate"
"""The leaf a calculation refuses at when its value waits on a household row fact."""


class ModeloHouseholdRowFactInputRequiredError(ModeloWorkMissingInputError):
    """A calculation refused before publication because a household row omits a fact its value waits on.

    The binding the engine found without a value is derived from the household rows, so
    the filer states the fact on the row, at the profile door for that household group,
    rather than entering the derived value.
    """

    _group: str
    _fact_leaf: str
    _rows: tuple[int, ...]

    def __init__(
        self,
        source: ModeloWorkMissingInputError,
        *,
        group: str,
        fact_leaf: str,
        rows: tuple[int, ...],
        translated_message: str,
        context: Mapping[str, object],
        precondition_verdict: object,
        next_step: OperationNextStepWording | None,
    ) -> None:
        """Keep the engine refusal as the cause and the household rows as typed facts."""
        self._group = group
        self._fact_leaf = fact_leaf
        self._rows = rows
        super().__init__(
            source,
            binding_id=source.binding_id,
            translated_message=translated_message,
            context=context,
            precondition_verdict=precondition_verdict,
            next_step=next_step,
        )

    @property
    def group(self) -> str:
        """The household group whose rows omit the fact."""
        return self._group

    @property
    def fact_leaf(self) -> str:
        """The row fact the filer states."""
        return self._fact_leaf

    @property
    def rows(self) -> tuple[int, ...]:
        """The stored positions of the rows that omit it, as the profile list shows them."""
        return self._rows


def household_row_fact_input_required(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    group: str,
    fact_leaf: str,
    rows: tuple[int, ...],
) -> ModeloHouseholdRowFactInputRequiredError | None:
    """The refusal of ``missing`` as the household row fact it waits on, or ``None`` where no door is declared.

    ``rows`` are the stored positions of the household rows that omit ``fact_leaf``.
    The scenario and profile door are those the verification gate declares for the group.
    """
    door = GROUP_DOORS.get(group)
    if door is None or not rows:
        return None
    scenario, _ = door
    leaf = _CALCULATE_LEAF
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.household_row_facts.{scenario}",
        evidence_id=f"{leaf}.household_row_facts",
        evidence_values={
            "work_unit_id": work_unit.work_unit_id,
            "group": group,
            "leaf": fact_leaf,
            "rows": ",".join(str(row) for row in rows),
            "rows_omitting": len(rows),
            "fact_stated": False,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    return ModeloHouseholdRowFactInputRequiredError(
        missing,
        group=group,
        fact_leaf=fact_leaf,
        rows=rows,
        translated_message=_MESSAGE_KEY,
        context={
            "action": "calculate",
            "reason": HOUSEHOLD_ROW_FACT_UNSTATED_REASON,
            "field": f"{group}.{fact_leaf}",
            "count": len(rows),
        },
        precondition_verdict=failure.verdict,
        next_step=open_work_step(work_unit),
    )


__all__ = ["ModeloHouseholdRowFactInputRequiredError", "household_row_fact_input_required"]

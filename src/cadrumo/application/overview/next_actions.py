"""Locale-neutral next-action declarations shared by every overview read model.

The overview surfaces used to state their forward guidance as literal ``aeat``
command strings on application records (``next_command``, ``fix_command``) and
inside locale prose. That put executable identity in four translated catalogues
and in three unrelated producers, so a verb rename silently handed the operator
a dead instruction, and the text and JSON surfaces each rebuilt the advice from
different material.

Producers here name a stable catalogue action and the concrete arguments their
own outcome already holds; nothing else. Resolution against the live command
tree and its required inputs belongs to the operator-surface projection, which
refuses a declaration it cannot fully materialise - so an unexecutable step can
never be dressed up as an executable one.

A step whose real continuation needs operator-supplied input the read model
cannot know (which statement file to import, which document to attach) declares
no action at all. That is the honest outcome: the guidance survives as localized
prose, and the executable channel stays empty rather than shipping a
placeholder command.

See Also:
    :class:`~application.operator_actions.DeclaredNextAction`
        The shared producer-side record every declaration here returns.
    :mod:`application.operator_surface`
        Owner of catalogue lookup and live required-input coverage.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ..operator_actions.models import ActionArgumentBinding, ActionReference, DeclaredNextAction

if TYPE_CHECKING:
    from .calendar_models import OverviewStatusReport


def declare_next_action(action_id: str, /, **arguments: str | int) -> DeclaredNextAction:
    """Declare one catalogue action from concrete producer-outcome values.

    Every argument is verdict-context provenance: the value comes from the read
    model's own resolved outcome rather than from operator request input or from
    a failed condition's evidence.

    Args:
        action_id: A namespaced identifier declared in the operator action
            catalogue. An unknown id fails closed at resolution, not here.
        **arguments: Target argument names mapped to the concrete values this
            producer holds. The catalogue must declare a matching
            verdict-context source for each name.

    Returns:
        The producer-side :class:`~application.operator_actions.DeclaredNextAction`.
    """
    return DeclaredNextAction(
        action=ActionReference(action_id=action_id),
        argument_bindings=tuple(
            ActionArgumentBinding(
                argument_name=name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=name,
            )
            for name, value in arguments.items()
        ),
    )


class OverviewStatusNextStepId(StrEnum):
    """Closed identifier for one ``overview status`` forward-guidance row.

    The identifier is the whole presentation contract: the renderer resolves it
    to localized prose, and the executable half rides on the row's optional
    declared action. Neither the identifier nor the producer carries text.

    Attributes:
        CREATE_PROFILE: No active profile exists, so nothing else can be
            scoped until one does.
        RESUME_WORK_UNIT: Work units exist; list them and resume one.
        START_ANOTHER_WORK_UNIT: Work is already under way; a further modelo
            may still need its own work unit.
        START_WORK_UNIT_FROM_LEDGER: Ledger data exists but no work unit does;
            the declaration can be started from that data.
        MODELO_210_SEDE_ONLY: Modelo 210 is discoverable but has no local
            work-unit creation path, so the row diverts to its description.
        REVIEW_LEDGER: Imported rows are waiting for review.
        IMPORT_TRANSACTIONS: The ledger is empty; a bank statement must be
            imported before anything else can proceed.
        REPAIR_STORAGE: Local rows could not be read, so the storage
            diagnostics surface should be run before the numbers are trusted.
        COMMAND_GUIDE: Return to the top-level command guide.
    """

    CREATE_PROFILE = "create_profile"
    RESUME_WORK_UNIT = "resume_work_unit"
    START_ANOTHER_WORK_UNIT = "start_another_work_unit"
    START_WORK_UNIT_FROM_LEDGER = "start_work_unit_from_ledger"
    MODELO_210_SEDE_ONLY = "modelo_210_sede_only"
    REVIEW_LEDGER = "review_ledger"
    IMPORT_TRANSACTIONS = "import_transactions"
    REPAIR_STORAGE = "repair_storage"
    COMMAND_GUIDE = "command_guide"


class OverviewStatusNextStep(BaseModel):
    """One ordered forward-guidance row for ``overview status``.

    Attributes:
        step_id: Closed :class:`OverviewStatusNextStepId` the renderer resolves
            to localized prose.
        next_action: The executable continuation when one exists and every
            required input is already known, otherwise ``None``.
    """

    model_config = _STRICT_FROZEN

    step_id: OverviewStatusNextStepId
    next_action: DeclaredNextAction | None = None


def build_overview_status_next_steps(report: OverviewStatusReport) -> tuple[OverviewStatusNextStep, ...]:
    """Return forward guidance that reflects the actual workspace state.

    A workspace with ledger data already recorded must not be told to import a
    bank statement - that step is done. The guidance walks the operator forward:
    import when the ledger is empty, review and start a declaration once
    transactions exist, resume the modelo flow when work units are already in
    progress. A :class:`~core.Modelo` with no local work-unit creation path is
    diverted to discovery instead of a dead command.

    Args:
        report: The assembled workspace status read model.

    Returns:
        The ordered guidance rows, each carrying its executable continuation
        when one is fully known.
    """
    steps: list[OverviewStatusNextStep] = []
    if report.active_profile_name is None:
        steps.append(
            OverviewStatusNextStep(
                step_id=OverviewStatusNextStepId.CREATE_PROFILE,
                next_action=declare_next_action("operator.profile.create"),
            ),
        )
    steps.extend(_workspace_progress_steps(report))
    if report.unreadable_rows > 0:
        steps.append(
            OverviewStatusNextStep(
                step_id=OverviewStatusNextStepId.REPAIR_STORAGE,
                next_action=declare_next_action("operator.diagnostics.repair"),
            ),
        )
    steps.append(OverviewStatusNextStep(step_id=OverviewStatusNextStepId.COMMAND_GUIDE))
    return tuple(steps)


def _workspace_progress_steps(report: OverviewStatusReport) -> tuple[OverviewStatusNextStep, ...]:
    """Return the rows that follow from how far the workspace has actually got."""
    if report.work_units > 0:
        return (
            OverviewStatusNextStep(
                step_id=OverviewStatusNextStepId.RESUME_WORK_UNIT,
                next_action=declare_next_action("operator.modelo.work.list"),
            ),
            _start_work_unit_step(report, step_id=OverviewStatusNextStepId.START_ANOTHER_WORK_UNIT),
        )
    if report.transactions > 0 or report.invoices > 0:
        return (
            _review_ledger_step(),
            _start_work_unit_step(report, step_id=OverviewStatusNextStepId.START_WORK_UNIT_FROM_LEDGER),
        )
    return (
        OverviewStatusNextStep(step_id=OverviewStatusNextStepId.IMPORT_TRANSACTIONS),
        _review_ledger_step(),
    )


def _review_ledger_step() -> OverviewStatusNextStep:
    return OverviewStatusNextStep(
        step_id=OverviewStatusNextStepId.REVIEW_LEDGER,
        next_action=declare_next_action("operator.ledger.review"),
    )


def _start_work_unit_step(
    report: OverviewStatusReport,
    *,
    step_id: OverviewStatusNextStepId,
) -> OverviewStatusNextStep:
    """Return the work-unit row, diverted when local creation is unsupported.

    Work-unit creation needs a modelo, a year and a period the status surface
    has not been given, so the general row names no executable action. The
    diverted Modelo 210 row does: its description target needs only the modelo
    the diversion itself identified.
    """
    if Modelo.M210.value in report.unsupported_work_create_modelos:
        return OverviewStatusNextStep(
            step_id=OverviewStatusNextStepId.MODELO_210_SEDE_ONLY,
            next_action=declare_next_action("operator.modelo.describe", modelo=Modelo.M210.value),
        )
    return OverviewStatusNextStep(step_id=step_id)


__all__ = [
    "OverviewStatusNextStep",
    "OverviewStatusNextStepId",
    "build_overview_status_next_steps",
    "declare_next_action",
]

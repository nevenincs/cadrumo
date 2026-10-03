"""Observe actual operation review and terminal outcomes through retained public controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .scenario import AcceptanceOutcome
from .tui_contracts import TerminalCondition, TuiJourneyError, TuiOperationBinding, TuiTerminalEvidence, _TuiScreen
from .tui_readback import _rendered_text, _stack_text

if TYPE_CHECKING:
    from textual.pilot import Pilot


def settled_notice_terminal(notice: str) -> tuple[TerminalCondition, AcceptanceOutcome] | None:
    """Classify the notice the workbench leaves after its operation modal dismissed itself.

    The modal closes as soon as the operation is terminal.  The workbench then
    says the declaration was updated -- or, once it has read a recalculated
    declaration again, that no box changed -- or that the operation did not
    complete, alone or followed by one space and the registry's public
    explanation of a settled refusal.  An explanation is only ever given for a
    refusal, so that shape is a refusal; the bare sentence cannot say which
    non-success it was and stays ``not_completed``.  Any other text is not a
    terminal.
    """
    from cadrumo.core.i18n.render import tr

    succeeded = {tr("tui.modelo.workbench.operation.done"), tr("tui.modelo.workbench.result_diff.nothing_changed")}
    not_done = tr("tui.modelo.workbench.operation.not_done")
    if notice in succeeded:
        return "succeeded", AcceptanceOutcome.PROVEN
    if notice == not_done:
        return "not_completed", AcceptanceOutcome.FAILED
    if notice.startswith(f"{not_done} ") and notice[len(not_done) + 1 :].strip():
        return "refused", AcceptanceOutcome.BLOCKED
    return None


async def _apply_visible_operation_review(pilot: Pilot[Any], modal: _TuiScreen, binding: TuiOperationBinding) -> bool:
    """Apply the visible review once when its actual public control is enabled."""
    from textual.css.query import NoMatches
    from textual.widget import Widget

    try:
        apply = modal.query_one("#btn-operation-apply")
    except NoMatches:
        apply = None
    if apply is not None and not isinstance(apply, Widget):
        raise TuiJourneyError(
            f"{binding.operation_id} operation modal Apply control is not a Textual widget ({type(apply).__name__})"
        )
    if apply is not None and not apply.disabled:
        apply.focus()
        await pilot.press("enter")
        return True
    return False


async def _observe_operation_terminal(
    pilot: Pilot[Any],
    *,
    modal: _TuiScreen,
    binding: TuiOperationBinding,
    maximum_polls: int,
) -> TuiTerminalEvidence:
    """Read the terminal widgets retained by the actual modal instance.

    A shared operation may pause at its public REVIEW phase before it can
    settle.  The installed driver answers that phase through the modal's
    ordinary Apply button once.  It never calls an operation controller or
    assumes that opening the modal executed the action.  Once the modal has
    dismissed itself, the workbench's notice carries the settled result.
    """
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr

    expected: dict[str, tuple[TerminalCondition, AcceptanceOutcome]] = {
        tr("operation.modal.terminal.succeeded"): ("succeeded", AcceptanceOutcome.PROVEN),
        tr("operation.modal.terminal.succeeded_partial"): ("succeeded_partial", AcceptanceOutcome.FAILED),
        tr("operation.modal.terminal.refused"): ("refused", AcceptanceOutcome.BLOCKED),
        tr("operation.modal.terminal.failed"): ("failed", AcceptanceOutcome.FAILED),
        tr("operation.modal.terminal.cancelled"): ("cancelled", AcceptanceOutcome.FAILED),
    }
    terminal_result_id = binding.terminal_result_id
    if terminal_result_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no terminal result control")
    review_applied = False
    status: str | None = None
    for _ in range(maximum_polls):
        try:
            status = _rendered_text(modal.query_one(terminal_result_id))
            receipt = _rendered_text(modal.query_one("#operation-modal-receipt"))
            diagnostic = _rendered_text(modal.query_one("#operation-modal-diagnostic"))
        except NoMatches:
            terminal = _settled_terminal(pilot, binding)
            if terminal is not None:
                condition, outcome = terminal
                return TuiTerminalEvidence(
                    operation_id=binding.operation_id,
                    terminal_condition=condition,
                    outcome=outcome,
                    receipt_present=False,
                    diagnostic_present=False,
                )
            await pilot.pause()
            continue
        terminal = expected.get(status)
        if terminal is not None:
            condition, outcome = terminal
            return TuiTerminalEvidence(
                operation_id=binding.operation_id,
                terminal_condition=condition,
                outcome=outcome,
                receipt_present=bool(receipt),
                diagnostic_present=bool(diagnostic),
            )
        if not getattr(modal, "is_mounted", True):
            terminal = _settled_terminal(pilot, binding)
            if terminal is not None:
                condition, outcome = terminal
                return TuiTerminalEvidence(
                    operation_id=binding.operation_id,
                    terminal_condition=condition,
                    outcome=outcome,
                    receipt_present=bool(receipt),
                    diagnostic_present=bool(diagnostic),
                )
        # The generic modal keeps Apply disabled unless its public projection
        # has reached REVIEW.  A single click is the same operator act as the
        # visible button; repeating it while the projected revision catches up
        # would create noisy duplicate attempts rather than exercising the
        # lifecycle once.
        if not review_applied:
            review_applied = await _apply_visible_operation_review(pilot, modal, binding)
        await pilot.pause()
    try:
        apply = modal.query_one("#btn-operation-apply")
        phase = _rendered_text(modal.query_one("#operation-modal-phase"))
        detail = (
            f"status={status!r}, phase={phase!r}, apply_disabled={getattr(apply, 'disabled', None)!r}, "
            f"apply_attempted={review_applied!r}"
        )
    except NoMatches:
        detail = f"modal_unmounted=True, apply_attempted={review_applied!r}"
    raise TuiJourneyError(f"{binding.operation_id} did not expose a terminal operation status ({detail})")


def _settled_terminal(
    pilot: Pilot[Any], binding: TuiOperationBinding
) -> tuple[TerminalCondition, AcceptanceOutcome] | None:
    """Classify the notice the workbench shows once the operation modal has gone."""
    refusal_notice_id = binding.refusal_notice_id
    if refusal_notice_id is None:
        return None
    return settled_notice_terminal(_stack_text(pilot, refusal_notice_id))

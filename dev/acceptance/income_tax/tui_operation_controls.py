"""Visible public income-tax operation activation, review and assumed-value confirmation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from .scenario import AcceptanceOutcome
from .tui_checkbox import _tick
from .tui_contracts import TuiJourneyError, TuiOperationBinding, TuiTerminalEvidence, _TuiScreen
from .tui_lifecycle_contract import _require_operation_binding
from .tui_navigation import (
    _offered_line,
    _require_fresh_notice,
    _require_offered_step,
    _wait_for_visible_tui_control,
    open_review_ready_to_apply,
    wait_for_tui_refresh,
    workbench_offers,
)
from .tui_readback import _query_visible_tui_control, _stack_text, workbench_notice
from .tui_selectors import _BULK_CONFIRM, _BULK_TICK, _NEXT_STEP_KEY
from .tui_terminal_observation import _observe_operation_terminal, settled_notice_terminal

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widget import Widget


async def activate_tui_operation(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int = 600,
) -> TuiTerminalEvidence:
    """Activate one real TUI control and classify its public terminal result.

    This adapter reads only the modal's rendered status, receipt and diagnostic
    widgets and the workbench's notice.  It intentionally does not call an
    operation controller or inspect a private journal, and it cannot turn a
    refreshed screen into success.  The workbench's notice must be empty
    before activation, so a notice left by an earlier operation can never be
    read as this operation's result.
    """
    _require_operation_binding(binding)
    _require_fresh_notice(pilot, label=binding.operation_id, selector=binding.refusal_notice_id)
    if binding.activation_key is not None:
        if binding.offered_step is not None:
            _require_offered_step(pilot, step=binding.offered_step)
        await pilot.press(binding.activation_key)
    elif binding.activation_id is not None:
        activation = _query_visible_tui_control(pilot, binding.activation_id)
        activation.focus()
        await pilot.press("enter")
    await pilot.pause()
    if binding.confirmation_id is not None:
        confirmation = await _wait_for_visible_tui_control(pilot, binding.confirmation_id, maximum_polls=maximum_polls)
        confirmation.focus()
        await pilot.press("enter")
        await pilot.pause()
    modal = await _wait_for_operation_modal_or_refusal(
        pilot,
        binding=binding,
        maximum_polls=maximum_polls,
    )
    if modal is None:
        notice = _stack_text(pilot, binding.refusal_notice_id or "")
        settled = settled_notice_terminal(notice)
        if settled is not None:
            condition, outcome = settled
            return TuiTerminalEvidence(
                operation_id=binding.operation_id,
                terminal_condition=condition,
                outcome=outcome,
                receipt_present=False,
                diagnostic_present=False,
            )
        return TuiTerminalEvidence(
            operation_id=binding.operation_id,
            terminal_condition="refused",
            outcome=AcceptanceOutcome.BLOCKED,
            receipt_present=False,
            diagnostic_present=True,
        )
    return await _observe_operation_terminal(
        pilot,
        modal=modal,
        binding=binding,
        maximum_polls=maximum_polls,
    )


async def confirm_assumed_values(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    seconds: float = 300.0,
    maximum_polls: int = 600,
) -> TuiTerminalEvidence | None:
    """Confirm the assumed values the workbench offers to confirm, then review and apply them.

    An assumed value is one the calculation holds that nobody is recorded as
    having entered; while any remain the workbench offers confirming them
    before it offers verifying.  Nothing is done, and ``None`` returned, when
    the workbench on top offers another step.  Otherwise the next-step key
    opens the confirmation dialog, which is ticked and confirmed; the values
    it keeps are staged, reviewed with ``R`` and applied through ``binding``,
    whose operation recalculates the declaration.  The applied terminal is
    returned; after a succeeded one the workbench is back on top with its
    re-read settled, but still showing the operation's notice, so the caller
    opens the declaration afresh before its next operation.
    """
    from textual.widgets import Button, Checkbox

    if not workbench_offers(pilot, "confirm"):
        return None
    _require_fresh_notice(pilot, label="confirming the assumed values")
    await pilot.press(_NEXT_STEP_KEY)
    tick = await _wait_for_dialog_control(
        pilot, _BULK_TICK, seconds=seconds, label="its confirmation of assumed values"
    )
    if not isinstance(tick, Checkbox):
        raise TuiJourneyError(f"{_BULK_TICK} is not a checkbox ({type(tick).__name__})")
    if tick.disabled:
        raise TuiJourneyError(
            "the workbench offered to confirm assumed values but its dialog lists none it can confirm"
        )
    if not await _tick(pilot, tick):
        raise TuiJourneyError("the confirmation of assumed values did not take the tick")
    confirm = pilot.app.screen.query_one(_BULK_CONFIRM, Button)
    if confirm.disabled:
        raise TuiJourneyError("the confirmation of assumed values kept Confirm unavailable once ticked")
    confirm.focus()
    await pilot.press("enter")
    deadline = time.monotonic() + seconds
    while not workbench_offers(pilot, "apply"):
        notice = workbench_notice(pilot)
        if notice:
            raise TuiJourneyError(f"the workbench did not keep the confirmed values (notice {notice[:240]!r})")
        if time.monotonic() > deadline:
            raise TuiJourneyError(
                f"the workbench did not offer to apply the confirmed values (it offers {_offered_line(pilot)[:200]!r})"
            )
        await pilot.pause()
    await open_review_ready_to_apply(pilot, seconds=seconds)
    terminal = await activate_tui_operation(pilot, binding=binding, maximum_polls=maximum_polls)
    if terminal.outcome is AcceptanceOutcome.PROVEN:
        await wait_for_tui_refresh(pilot, binding=binding, maximum_polls=maximum_polls)
    return terminal


async def _wait_for_dialog_control(pilot: Pilot[Any], selector: str, *, seconds: float, label: str) -> Widget:
    """Wait for a dialog's control on the top screen, refusing at once if the workbench reports a refusal instead."""
    from textual.css.query import NoMatches

    deadline = time.monotonic() + seconds
    while True:
        try:
            return _query_visible_tui_control(pilot, selector)
        except NoMatches:
            notice = workbench_notice(pilot)
            if notice:
                raise TuiJourneyError(f"the workbench did not open {label}: {notice[:240]!r}") from None
            if time.monotonic() > deadline:
                raise TuiJourneyError(f"the workbench did not open {label}") from None
            await pilot.pause()


async def _proceed_past_at_risk_confirmation(pilot: Pilot[Any], selector: str | None) -> bool:
    """Press the pre-recalculation confirmation's proceed control, only while it is the top screen."""
    from textual.css.query import NoMatches

    if selector is None:
        return False
    try:
        proceed = _query_visible_tui_control(pilot, selector)
    except NoMatches:
        return False
    proceed.focus()
    await pilot.press("enter")
    await pilot.pause()
    return True


async def _wait_for_operation_modal_or_refusal(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int,
) -> _TuiScreen | None:
    """Wait for the standard modal or a visible typed pre-submit refusal."""
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    refusal_notice_id = binding.refusal_notice_id
    if refusal_notice_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no visible refusal control")
    for _ in range(maximum_polls):
        current = pilot.app.screen
        if isinstance(current, OperationModal):
            return current
        if await _proceed_past_at_risk_confirmation(pilot, binding.at_risk_proceed_id):
            continue
        if _stack_text(pilot, refusal_notice_id):
            return None
        await pilot.pause()
    raise TuiJourneyError(f"{binding.operation_id} did not open an operation modal or visible refusal")

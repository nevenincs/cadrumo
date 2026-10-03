"""Visible installed M303 filing-evidence form and ordered refusal/calculation stages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
)
from dev.acceptance.income_tax.tui_contracts import TuiOperationBinding, TuiTerminalEvidence
from dev.acceptance.income_tax.tui_operation_controls import activate_tui_operation
from dev.acceptance.income_tax.tui_selectors import WORKBENCH_AT_RISK_PROCEED, WORKBENCH_LIST, WORKBENCH_NOTICE

from .m303_evidence_contracts import _EVIDENCE_SUBMIT_ID, TuiOutcome
from .m303_evidence_navigation import _await_selector, _await_workbench_refresh, _open_work
from .m303_evidence_refusals import _notice_key, _visible_refusal

if TYPE_CHECKING:
    pass


async def _open_evidence_form(pilot: Any, *, work_unit_id: str) -> None:
    """Calculate from the workbench, which first asks the Modelo 303 filing evidence.

    The workbench may ask, before recalculating, to confirm a declaration last
    calculated elsewhere; that confirmation is accepted only while it is the
    top screen.
    """
    import time

    from textual.css.query import NoMatches

    await _open_work(pilot, work_unit_id=work_unit_id)
    await pilot.press("c")
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        screen = pilot.app.screen
        if screen.query(_EVIDENCE_SUBMIT_ID):
            return
        try:
            proceed = screen.query_one(WORKBENCH_AT_RISK_PROCEED)
        except NoMatches:
            pass
        else:
            proceed.focus()
            await pilot.press("enter")
        await pilot.pause(0.2)
    raise InstalledTuiChildError(
        f"installed workbench did not ask the Modelo 303 filing evidence: {_visible_refusal(pilot)}",
        diagnostic=public_surface_diagnostic(pilot),
    )


def _fill_evidence_form(
    pilot: Any,
    *,
    attachment_id: str = "",
    sha256: str = "",
    observed_at: str = "",
    answer: bool = True,
    asks_modelo_390: bool = True,
) -> None:
    from textual.widgets import Input, Select

    if answer:
        cast(Any, query_public_selector(pilot, "#m303-evidence-joint-return-elected", Select)).value = "false"
    if not asks_modelo_390:
        return
    query_public_selector(pilot, "#m303-evidence-attachment-id", Input).value = attachment_id
    query_public_selector(pilot, "#m303-evidence-sha256", Input).value = sha256
    query_public_selector(pilot, "#m303-evidence-observed-at", Input).value = observed_at


_EVIDENCE_SUBMIT: Final = TuiOperationBinding(
    "modelo.work.calculate",
    activation_id=_EVIDENCE_SUBMIT_ID,
    at_risk_proceed_id=WORKBENCH_AT_RISK_PROCEED,
    terminal_result_id="#operation-modal-status",
    refresh_result_id=WORKBENCH_LIST,
    refusal_notice_id=WORKBENCH_NOTICE,
)


async def _submit_evidence(pilot: Any, *, step: str) -> TuiOutcome:
    terminal: TuiTerminalEvidence = await activate_tui_operation(pilot, binding=_EVIDENCE_SUBMIT)
    return TuiOutcome(step=step, terminal_condition=terminal.terminal_condition, visible_notice_key=None)


async def _form_refusals(pilot: Any, *, work_unit_id: str, observed_at: str) -> list[TuiOutcome]:
    """Missing answers stay on the form; cancelling is reported without a request."""
    from textual.widgets import Button

    outcomes: list[TuiOutcome] = []
    await _open_evidence_form(pilot, work_unit_id=work_unit_id)
    _fill_evidence_form(pilot, answer=False, observed_at=observed_at)
    query_public_selector(pilot, _EVIDENCE_SUBMIT_ID, Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    await _await_selector(pilot, _EVIDENCE_SUBMIT_ID)
    outcomes.append(
        TuiOutcome(
            step="missing_booleans",
            terminal_condition="form_refused",
            visible_notice_key=_notice_key(pilot, "#m303-evidence-notice", ("tui.modelo.m303_evidence.required",)),
        )
    )
    query_public_selector(pilot, "#m303-evidence-cancel", Button).focus()
    await pilot.press("enter")
    await _await_selector(pilot, WORKBENCH_NOTICE)
    await pilot.pause()
    outcomes.append(
        TuiOutcome(
            step="cancelled",
            terminal_condition="cancelled_without_request",
            visible_notice_key=_notice_key(pilot, WORKBENCH_NOTICE, ("tui.modelo.m303_evidence.cancelled",)),
        )
    )
    return outcomes


async def _calculate_and_verify(
    pilot: Any, *, work_unit_id: str, form: Mapping[str, str], asks_modelo_390: bool = True
) -> list[TuiOutcome]:
    outcomes: list[TuiOutcome] = []
    await _open_evidence_form(pilot, work_unit_id=work_unit_id)
    _fill_evidence_form(
        pilot,
        attachment_id=form.get("attachment_id", ""),
        sha256=form.get("sha256", ""),
        observed_at=form.get("observed_at", ""),
        asks_modelo_390=asks_modelo_390,
    )
    calculated = await _submit_evidence(pilot, step="calculate")
    outcomes.append(calculated)
    if calculated.terminal_condition != "succeeded":
        raise InstalledTuiChildError(
            f"installed TUI M303 calculation ended {calculated.terminal_condition}: {_visible_refusal(pilot)}"
        )
    await _await_workbench_refresh(pilot, binding=_EVIDENCE_SUBMIT)
    return outcomes

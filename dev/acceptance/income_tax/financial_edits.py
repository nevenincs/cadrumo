"""Bounded public annual casilla editing and review through visible installed widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .financial_contracts import _ANNUAL_EDITS, _EDIT_SECONDS
from .financial_lifecycle import _workbench_notice
from .financial_navigation import open_work
from .installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
)
from .tui_contracts import TuiJourneyError
from .tui_lifecycle_contract import installed_lifecycle_contract
from .tui_navigation import (
    open_review_ready_to_apply,
    wait_for_tui_refresh,
)
from .tui_operation_controls import activate_tui_operation
from .tui_selectors import WORKBENCH_LIST

if TYPE_CHECKING:
    from textual.widgets import Input

    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen


async def _open_visible_casilla_editor(
    pilot: Any, workbench: ModeloWorkbenchScreen, address: tuple[str, str], label: str
) -> None:
    """Open visible casilla editor."""
    from cadrumo.entrypoints.tui.modelo.workbench.casilla_list import CasillaList
    from cadrumo.entrypoints.tui.modelo.workbench.page_items import workbench_pages

    form = workbench.form
    if form is None:
        raise InstalledTuiChildError("the annual workbench has not read its form")
    pages = len(workbench_pages(form))
    casilla_list = workbench.query_one(WORKBENCH_LIST, CasillaList)
    for _ in range(pages):
        await pilot.press("left_square_bracket")
    for _ in range(pages):
        if casilla_list.focus_address(address):
            break
        await pilot.press("right_square_bracket")
        await pilot.pause()
    else:
        raise InstalledTuiChildError(f"the annual workbench shows no {label} on any page")
    casilla_list.focus()
    await pilot.press("enter")


async def _wait_for_casilla_editor(pilot: Any, workbench: ModeloWorkbenchScreen, label: str, deadline: float) -> Input:
    """Wait for casilla editor."""
    import time

    from textual.css.query import NoMatches
    from textual.widgets import Input

    while True:
        try:
            value_input = pilot.app.screen.query_one("#editor-input", Input)
        except NoMatches:
            notice = _workbench_notice(workbench)
            if notice:
                raise InstalledTuiChildError(f"the annual workbench would not edit {label}: {notice[:200]}") from None
            if time.monotonic() > deadline:
                raise InstalledTuiChildError(
                    f"the annual workbench opened no editor for {label}", diagnostic=public_surface_diagnostic(pilot)
                ) from None
            await pilot.pause()
            continue
        break
    return cast("Input", value_input)


async def _stage_workbench_value(
    pilot: Any, *, workbench: ModeloWorkbenchScreen, address: tuple[str, str], lexeme: str
) -> None:
    """Stage one value as a filer does: find its line, open its editor, type it and save it."""
    import time

    from textual.widgets import Button, Static

    from cadrumo.application.modelo.work_form_models import address_key

    label = ":".join(address)
    await _open_visible_casilla_editor(pilot, workbench, address, label)
    deadline = time.monotonic() + _EDIT_SECONDS
    value_input = await _wait_for_casilla_editor(pilot, workbench, label, deadline)
    editor = pilot.app.screen
    value_input.value = lexeme
    save = editor.query_one("#editor-save", Button)
    readback = editor.query_one("#editor-readback", Static)
    while save.disabled:
        if readback.has_class("-refused") or time.monotonic() > deadline:
            raise InstalledTuiChildError(
                f"the annual editor did not accept the value for {label}: {str(readback.render()).strip()[:200]}"
            )
        await pilot.pause()
    save.focus()
    await pilot.press("enter")
    while pilot.app.screen is not workbench:
        if time.monotonic() > deadline:
            raise InstalledTuiChildError(f"the annual editor for {label} did not close")
        await pilot.pause()
    if not any(address_key(change.field.address) == address for change in workbench.staged_changes):
        raise InstalledTuiChildError(
            f"the annual workbench staged no change for {label}: {_workbench_notice(workbench)[:200]}"
        )


async def _apply_annual_edits(pilot: Any, *, work_unit_id: str) -> None:
    """Set explicit annual-only facts in the declaration's workbench, then review and apply them."""
    import re

    from textual.css.query import NoMatches
    from textual.widgets import Static

    workbench = await open_work(pilot, work_unit_id=work_unit_id)
    for address, lexeme in _ANNUAL_EDITS:
        await _stage_workbench_value(pilot, workbench=workbench, address=address, lexeme=lexeme)
    if len(workbench.staged_changes) != len(_ANNUAL_EDITS):
        raise InstalledTuiChildError(
            f"the annual workbench staged {len(workbench.staged_changes)} changes, expected {len(_ANNUAL_EDITS)}"
        )
    try:
        await open_review_ready_to_apply(pilot, seconds=_EDIT_SECONDS)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(
            f"the annual workbench could not apply its changes: {error}", diagnostic=public_surface_diagnostic(pilot)
        ) from error
    binding = installed_lifecycle_contract().apply
    terminal = await activate_tui_operation(pilot, binding=binding)
    if terminal.outcome.value != "proven":
        try:
            log = str(pilot.app.screen.query_one("#operation-modal-log", Static).render())
        except NoMatches:
            log = ""
        public_codes = sorted(set(re.findall(r"\b(?:modelo|operation|calculation)\.[a-z0-9_.-]+\b", log)))
        raise InstalledTuiChildError(
            f"modelo.edit.apply terminal={terminal.terminal_condition}, "
            f"receipt_present={terminal.receipt_present}, diagnostic_present={terminal.diagnostic_present}, "
            f"public_event_codes={public_codes}, notice={_workbench_notice(workbench)[:200]!r}"
        )
    await wait_for_tui_refresh(pilot, binding=binding)

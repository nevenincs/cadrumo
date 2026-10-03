"""Bounded installed M303 declaration and revision navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
    select_public_data_table_row,
)
from dev.acceptance.income_tax.tui_contracts import TuiJourneyError, TuiOperationBinding
from dev.acceptance.income_tax.tui_navigation import (
    wait_for_tui_refresh,
    wait_for_workbench,
)

if TYPE_CHECKING:
    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen


# --------------------------------------------------------------------------- installed TUI child


async def _await_selector(pilot: Any, selector: str, *, seconds: float = 120.0) -> None:
    """Wait on wall-clock time, not a poll count: installed composition speed varies between runs."""
    import time

    from textual.css.query import NoMatches

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            pilot.app.screen.query_one(selector)
        except NoMatches:
            await pilot.pause(0.2)
        else:
            return
    raise InstalledTuiChildError(
        f"installed TUI did not expose {selector} within {seconds:.0f}s", diagnostic=public_surface_diagnostic(pilot)
    )


async def _open_declarations(pilot: Any) -> None:
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    label = tr("tui.search.destination.declarations")
    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            results = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = "declarations"
        for _ in range(180):
            await pilot.pause()
            for index in range(results.option_count):
                if getattr(getattr(results.get_option_at_index(index), "hit", None), "text", None) == label:
                    results.highlighted = index
                    await pilot.press("enter")
                    await _await_selector(pilot, "#declarations-list")
                    return
        break
    raise InstalledTuiChildError(
        "installed command palette did not offer Declarations", diagnostic=public_surface_diagnostic(pilot)
    )


async def _close_modals(pilot: Any) -> None:
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    for _ in range(60):
        if not isinstance(pilot.app.screen, OperationModal):
            return
        await pilot.press("escape")
        await pilot.pause()
    raise InstalledTuiChildError("installed operation modal did not close after its terminal result")


async def _await_workbench_refresh(pilot: Any, *, binding: TuiOperationBinding) -> None:
    """After a succeeded write, wait for the workbench to come back on top and read the declaration again."""
    await _close_modals(pilot)
    try:
        await wait_for_tui_refresh(pilot, binding=binding, maximum_polls=6000)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error


async def _open_work(pilot: Any, *, work_unit_id: str) -> ModeloWorkbenchScreen:
    """Open the selected declaration in a fresh workbench, whose notice starts empty, once it has read its form."""
    await _close_modals(pilot)
    await _open_declarations(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-list", row_key=work_unit_id)
    try:
        return await wait_for_workbench(pilot, seconds=300)
    except TuiJourneyError as error:
        exception = getattr(pilot.app, "_exception", None)
        raise InstalledTuiChildError(
            f"installed declaration workbench did not open: {error} "
            f"app_exception={type(exception).__name__ if exception else None}:{exception!s:.300}",
            diagnostic=public_surface_diagnostic(pilot),
        ) from error


async def _listed_revision(pilot: Any, *, calculation_revision_id: str) -> tuple[bool, str | None]:
    """Return whether Declarations lists the revision as current, and its lifecycle state as shown."""
    from textual.widgets import DataTable

    from cadrumo.core.i18n.render import tr
    from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState

    await _close_modals(pilot)
    await _open_declarations(pilot)
    await select_public_data_table_row(
        pilot=pilot, table_selector="#declarations-navigation", row_key="declarations.revisions"
    )
    await _await_selector(pilot, "#declarations-revisions")
    table = cast("DataTable[Any]", query_public_selector(pilot, "#declarations-revisions", DataTable))
    for row_key in table.rows:
        if row_key.value != calculation_revision_id:
            continue
        cells = table.get_row(row_key)
        state = next(
            (
                member.value
                for member in CalculationRevisionState
                if tr(f"tui.declarations.revision_state.{member.value}") == str(cells[2])
            ),
            None,
        )
        return str(cells[3]) == tr("tui.declarations.value.yes"), state
    return False, None

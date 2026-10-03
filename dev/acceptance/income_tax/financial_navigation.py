"""Bounded installed destination and declaration navigation through public controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
    select_public_data_table_row,
    wait_for_public_selector,
)
from .tui_navigation import (
    wait_for_workbench,
)

if TYPE_CHECKING:
    from textual.widgets import OptionList

    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen


def _highlight_palette_destination(results: OptionList, destination_label: str) -> bool:
    """Focus the exact translated destination offered by the public palette."""
    for index in range(results.option_count):
        option = results.get_option_at_index(index)
        hit = getattr(option, "hit", None)
        if getattr(hit, "text", None) == destination_label:
            results.highlighted = index
            return True
    return False


async def _open_destination(pilot: Any, *, query: str, expected_selector: str) -> None:
    """Open a workbench destination with the normal command-palette keyboard path."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    destination_key = {"ledger": "ledger", "declarations": "declarations"}.get(query)
    if destination_key is None:
        raise InstalledTuiChildError("installed journey requested an unknown workbench destination")
    destination_label = tr(f"tui.search.destination.{destination_key}")

    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = query
        break
    else:
        raise InstalledTuiChildError("installed command palette did not expose its search controls")
    for _ in range(180):
        await pilot.pause()
        try:
            results = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        if not _highlight_palette_destination(results, destination_label):
            await pilot.pause()
            continue
        break
    else:
        raise InstalledTuiChildError(f"command palette did not offer the {query} destination command")
    await pilot.press("enter")
    await wait_for_public_selector(pilot, expected_selector, polls=180)


async def _activate_button(pilot: Any, selector: str) -> None:
    """Activate a visible button by focus so compact terminals remain operable."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.press("enter")


async def _wait_for_refreshed_home(pilot: Any, *, polls: int = 360) -> None:
    """Wait until child dismissal has rebuilt the public workbench generation."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    for _ in range(polls):
        try:
            updating = query_public_selector(pilot, "#root-updating", Static)
            pilot.app.screen.query_one("#home-agenda")
        except NoMatches:
            pass
        else:
            if not updating.display:
                return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed TUI did not complete its public Home refresh",
        diagnostic={
            **public_surface_diagnostic(pilot),
            "worker_states": sorted(
                f"{worker.name}:{worker.state.value}:{type(worker.error).__name__ if worker.error else 'none'}"
                for worker in pilot.app.workers
            ),
        },
    )


async def _create_calendar_work(pilot: Any, *, modelo: str, year: int, period: str) -> None:
    """Create one filing-period work unit through Calendar confirmation."""
    from textual.widgets import Static

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-navigation")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-navigation",
        row_key="declarations.calendar",
    )
    await wait_for_public_selector(pilot, "#declarations-calendar-agenda")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-calendar-agenda",
        row_key=f"{modelo}|{year}|{period}",
    )
    await wait_for_public_selector(pilot, "#btn-confirm-accept")
    await _activate_button(pilot, "#btn-confirm-accept")
    await pilot.app.workers.wait_for_complete()
    notice = str(query_public_selector(pilot, "#declarations-calendar-notice", Static).render()).strip()
    if notice.startswith("Created ") is False:
        if "setup complete" in notice:
            outcome = "setup-incomplete"
        elif "could not be completed" in notice:
            outcome = "recovery-failed"
        else:
            outcome = "unexpected-notice"
        raise InstalledTuiChildError(f"calendar creation did not report success ({outcome})")
    await pilot.press("escape")
    await _wait_for_refreshed_home(pilot)


async def _open_work(pilot: Any, *, work_unit_id: str) -> ModeloWorkbenchScreen:
    """Open the created work's workbench using its public work-unit row key, once it has read its form."""
    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-list", row_key=work_unit_id)
    return await wait_for_workbench(pilot)


async def _work_ids_by_period(pilot: Any, *, year: int) -> dict[str, str]:
    """Resolve opaque work ids from the visible natural-address rows."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    found: dict[str, str] = {}
    for row_key in table.rows:
        rendered = " ".join(str(cell) for cell in table.get_row(row_key))
        for period in ("1T", "2T", "3T", "4T", "0A"):
            modelo = "100" if period == "0A" else "130"
            if modelo in rendered and str(year) in rendered and period in rendered:
                found[period] = str(row_key.value)
    return found

"""Bounded public installed IVA ledger navigation and activation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import OptionList

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
    wait_for_public_selector,
)


async def _open_ledger(pilot: Any) -> None:
    """Reach Ledger through the normal installed command-palette interaction."""
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    destination_label = tr("tui.search.destination.ledger")
    destination_help = tr("tui.search.destination_help.ledger")
    await pilot.press("ctrl+p")
    await pilot.pause()
    search = pilot.app.screen.query_one(Input)
    search.focus()
    await pilot.pause()
    if pilot.app.focused is not search:
        raise InstalledTuiChildError("installed command palette search did not receive keyboard focus")
    discovery_workers = [
        worker
        for worker in pilot.app.workers
        if worker.group == "--textual-command-palette-gather-commands" and not worker.is_cancelled
    ]
    if discovery_workers:
        await pilot.app.workers.wait_for_complete(discovery_workers)
    await pilot.pause()
    for _ in range(180):
        options = pilot.app.screen.query_one(OptionList)
        matches = _ledger_destination_matches(options, destination_label, destination_help)
        if len(matches) > 1:
            raise InstalledTuiChildError("installed command palette offered ambiguous Ledger destinations")
        if matches:
            options.highlighted = matches[0]
            await pilot.press("enter")
            await wait_for_public_selector(pilot, "#ledger-navigation", polls=180)
            return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed command palette did not offer the Ledger destination",
        diagnostic=public_surface_diagnostic(pilot),
    )


def _ledger_destination_matches(options: OptionList, destination_label: str, destination_help: str) -> list[int]:
    """Match both public destination label and help without accepting ambiguous lookalikes."""
    matches: list[int] = []
    for index in range(options.option_count):
        option = options.get_option_at_index(index)
        hit = getattr(option, "hit", None)
        if getattr(hit, "text", None) == destination_label and getattr(hit, "help", None) == destination_help:
            matches.append(index)
    return matches


async def _activate(pilot: Any, selector: str) -> None:
    """Activate a visible public button without a coordinate-dependent click."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.pause()
    if pilot.app.focused is not button:
        raise InstalledTuiChildError(f"installed IVA control {selector} did not receive keyboard focus")
    await pilot.press("enter")


def _visible_text(widget: Any) -> str:
    """Read an already-rendered public status line, never a persistence object."""
    return str(widget.render()).strip()

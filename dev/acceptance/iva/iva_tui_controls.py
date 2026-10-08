"""Bounded public installed IVA ledger navigation and activation."""

from __future__ import annotations

from typing import Any

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
    await pilot.press("ctrl+p")
    await pilot.pause()
    pilot.app.screen.query_one(Input).value = "ledger"
    for _ in range(180):
        options = pilot.app.screen.query_one(OptionList)
        for index in range(options.option_count):
            option = options.get_option_at_index(index)
            if getattr(getattr(option, "hit", None), "text", None) == destination_label:
                options.highlighted = index
                await pilot.press("enter")
                await wait_for_public_selector(pilot, "#ledger-navigation", polls=180)
                return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed command palette did not offer the Ledger destination",
        diagnostic=public_surface_diagnostic(pilot),
    )


async def _activate(pilot: Any, selector: str) -> None:
    """Activate a visible public button without a coordinate-dependent click."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.press("enter")


def _visible_text(widget: Any) -> str:
    """Read an already-rendered public status line, never a persistence object."""
    return str(widget.render()).strip()

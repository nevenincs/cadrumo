"""Every categorisation tool fits the terminal it is given, in both themes, with one scroll owner."""

from __future__ import annotations

from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import DataTable

from .....core.config import override_settings
from .....domain.transactions.classification_rule import LedgerClassificationRule
from .....domain.transactions.enums import BusinessClassification
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ...tests.frame import geometry_band
from ..categorisation_common import CategorisationScreen
from ..categorisation_tools import CATEGORISATION_TOOL_KEYS, ENTRY_LIST_TOOL_KEYS, categorisation_tools
from .categorisation_entry_fixtures import synthetic_participation
from .categorisation_memory_doors import LEDGER_TX_A, MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, settle
from .test_ledger_selection_journey import _WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_SIZES = ((80, 24), (100, 30), (120, 40), (200, 50))


def _seeded_profile() -> MemoryCategorisationProfile:
    profile = MemoryCategorisationProfile()
    profile.rules.rules.extend(
        LedgerClassificationRule.create(
            description_pattern=pattern,
            classification=classification,
            category_id=None,
            priority=priority,
            actor="operator",
        )
        for pattern, classification, priority in (
            ("papelería norte", BusinessClassification.BUSINESS, 10),
            ("supermercado", BusinessClassification.PERSONAL, 20),
        )
    )
    profile.rules.entries[LEDGER_TX_A] = ("Papelería norte factura 12", BusinessClassification.NOT_YET_PROCESSED)
    profile.ledger.participations = (synthetic_participation(1),)
    profile.ratios.overrides["vehiculo"] = "0.5"
    return profile


_REVIEWS = {
    "ledger.tool.categorisation.bulk": ("categorisation-bulk-review", "#categorisation-bulk-changing"),
    "ledger.tool.categorisation.rules": ("categorisation-rule-preview", "#categorisation-rule-matches"),
}
"""Tools whose review shows a further table, and the button that shows it."""


async def _assert_fits(pilot: Pilot[None], app: _WorkspaceHostApp, screen: CategorisationScreen, key: str) -> None:
    for width, height in _SIZES:
        await pilot.resize_terminal(width, height)
        await settle(pilot)
        assert geometry_band(app, width) == [], (key, width)
        # A table hidden until its review is shown has no width to fit; it is measured once shown.
        tables = tuple(table for table in screen.query(DataTable) if table.display)
        assert tables
        assert all(cast("DataTable[str]", table).max_scroll_x == 0 for table in tables), (key, width)
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert all(owner.id == "ledger-page" for owner in owners), (key, width)
        assert not screen.show_vertical_scrollbar


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", [CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME])
@pytest.mark.parametrize("key", CATEGORISATION_TOOL_KEYS)
async def test_each_tool_fits_every_terminal_size_in_both_themes(key: str, theme: str) -> None:
    tool = next(item for item in categorisation_tools(_seeded_profile().doors().bundle()) if item.key == key)
    # Whole-ledger tools open from Entries, where no entry need be selected.
    selected = None if key in ENTRY_LIST_TOOL_KEYS else LEDGER_TX_A
    screen = tool.build(categorisation_controller(selected=selected))
    assert isinstance(screen, CategorisationScreen)
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="es"):
        async with app.run_test(size=_SIZES[0]) as pilot:
            app.theme = theme
            await settle(pilot)
            await _assert_fits(pilot, app, screen, key)
            review = _REVIEWS.get(key)
            if review is not None:
                button, table = review
                await press(pilot, screen, button)
                assert screen.staged is not None
                assert screen.query_one(table, DataTable).display
                await _assert_fits(pilot, app, screen, key)

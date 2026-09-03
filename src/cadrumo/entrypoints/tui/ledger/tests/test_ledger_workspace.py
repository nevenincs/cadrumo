"""Contract, interaction, geometry, locale, and security tests for Ledger screens."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from .....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from .....core.external_constants import OutputLanguage
from .....core.identity import TransactionId
from ....tui.components.host import ScreenHostApp
from ....tui.devtools.frame import geometry_band
from ....tui.navigation import TuiScreenContextV1
from ..controller import LedgerWorkspaceController
from ..entries import LedgerEntriesScreen
from ..overview import LedgerOverviewScreen
from ..review import LedgerReviewScreen
from ..routes import LEDGER_ROUTES, LedgerUnavailableScreen, ledger_screen_factory, resolve_ledger_screen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TX_A = cast("TransactionId", "a" * 64)
_TX_B = cast("TransactionId", "b" * 64)


def _projection(*, unavailable: LedgerWorkspaceArea | None = None) -> LedgerWorkspaceProjectionV1:
    states = []
    counts = {
        LedgerWorkspaceArea.OVERVIEW: 3,
        LedgerWorkspaceArea.ENTRIES: 2,
        LedgerWorkspaceArea.REVIEW: 2,
        LedgerWorkspaceArea.IMPORT: 0,
        LedgerWorkspaceArea.CLASSIFICATION: 2,
        LedgerWorkspaceArea.EVIDENCE: 0,
        LedgerWorkspaceArea.RECONCILIATION: 0,
    }
    for area in LedgerWorkspaceArea:
        blocked = area is unavailable
        states.append(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                availability=LedgerWorkspaceAvailability.LOCKED if blocked else LedgerWorkspaceAvailability.AVAILABLE,
                reason_code="ledger.locked" if blocked else None,
                status=(
                    LedgerWorkspaceStatus.UNMEASURED
                    if area in {LedgerWorkspaceArea.IMPORT, LedgerWorkspaceArea.EVIDENCE}
                    else LedgerWorkspaceStatus.NEEDS_ATTENTION
                ),
                item_count=counts[area],
            )
        )
    entries = (
        LedgerWorkspaceEntryRefV1(transaction_id=_TX_A, review_status="pending"),
        LedgerWorkspaceEntryRefV1(transaction_id=_TX_B, review_status="reviewed"),
    )
    return LedgerWorkspaceProjectionV1(
        bucket_id="synthetic-bucket",
        areas=tuple(states),
        entries=entries,
        review_transaction_ids=(_TX_A, _TX_B),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def _context() -> TuiScreenContextV1:
    return TuiScreenContextV1(destination="workbench.ledger")


def _all_copy(screen: LedgerOverviewScreen | LedgerEntriesScreen | LedgerReviewScreen) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row in range(table.row_count)
        for cell in table.get_row_at(row)
    )
    return "\n".join(values)


def test_routes_cover_all_seven_areas_and_deferred_bodies_are_typed_placeholders() -> None:
    controller = LedgerWorkspaceController(_context(), _projection())
    assert tuple(route.area for route in LEDGER_ROUTES) == tuple(LedgerWorkspaceArea)
    assert tuple(route.destination for route in LEDGER_ROUTES) == (
        "ledger.overview",
        "ledger.entries",
        "ledger.review",
        "ledger.import",
        "ledger.classification",
        "ledger.evidence",
        "ledger.reconciliation",
    )
    for area in (
        LedgerWorkspaceArea.IMPORT,
        LedgerWorkspaceArea.CLASSIFICATION,
        LedgerWorkspaceArea.EVIDENCE,
        LedgerWorkspaceArea.RECONCILIATION,
    ):
        screen = resolve_ledger_screen(controller, controller.route_target(area))
        assert isinstance(screen, LedgerUnavailableScreen)
        assert screen.refusal is not None
        assert screen.refusal.target.area is area


def test_factory_requires_real_outer_context_and_keeps_injected_projection() -> None:
    projection = _projection()
    screen = ledger_screen_factory(projection)(_context())
    assert isinstance(screen, LedgerOverviewScreen)
    assert screen.controller.projection is projection
    with pytest.raises(ValueError, match=r"workbench\.ledger"):
        ledger_screen_factory(projection)(TuiScreenContextV1(destination="workbench.home"))


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_type", (LedgerOverviewScreen, LedgerEntriesScreen, LedgerReviewScreen))
async def test_screens_show_seven_destinations_have_one_scroll_owner_and_no_horizontal_overflow(screen_type: type) -> None:
    screen = screen_type(LedgerWorkspaceController(_context(), _projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        navigation = screen.query_one("#ledger-navigation", DataTable)
        assert navigation.row_count == 7
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget
            for widget in screen.walk_children()
            if widget.display and widget.show_vertical_scrollbar
        )
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "ledger-page" for owner in owners)


@pytest.mark.asyncio
async def test_navigation_refusal_and_review_selection_preserve_semantic_identity() -> None:
    projection = _projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    screen = LedgerReviewScreen(LedgerWorkspaceController(_context(), projection))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        navigation = screen.query_one("#ledger-navigation", DataTable)
        navigation.move_cursor(row=1)
        await pilot.press("enter")
        await pilot.pause()
        assert screen.refusal is not None
        assert screen.refusal.target.area is LedgerWorkspaceArea.ENTRIES
        assert "ledger.locked" not in _all_copy(screen)
        review = screen.query_one("#ledger-review", DataTable)
        review.focus()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert screen.requested_transaction_id == _TX_B
        await pilot.press("escape")
        assert screen.back_requested


@pytest.mark.asyncio
async def test_entry_rows_are_redacted_and_tables_are_each_one_tab_stop() -> None:
    projection = _projection()
    screen = LedgerEntriesScreen(LedgerWorkspaceController(_context(), projection))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert tuple(widget.id for widget in screen.focus_chain) == ("ledger-navigation", "ledger-entries")
        copy = _all_copy(screen)
        assert "a" * 64 not in copy
        assert "b" * 64 not in copy
        assert "aaaaaaaaaaaa" in copy
        assert "SENSITIVE" not in copy


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_every_locale_uses_catalogue_calls_without_raw_internal_vocabulary(locale: OutputLanguage) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language=locale.value):
        screen = LedgerOverviewScreen(LedgerWorkspaceController(_context(), _projection()))
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = _all_copy(screen)
            assert "tui.ledger." not in rendered
            assert "needs_attention" not in rendered
            assert "never_captured" not in rendered
            assert "work_unit" not in rendered.lower()


def test_ledger_tui_has_no_io_adapter_cli_calculation_or_mutation_imports() -> None:
    package = Path(__file__).parents[1]
    production = tuple(path for path in package.glob("*.py") if path.name != "__init__.py")
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in production)
    imports = {
        node.module or ""
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("entrypoints.cli" in name or "adapters" in name or "calculations" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "unlink"} & calls
    assert all("markup=False" in path.read_text(encoding="utf-8") for path in production if path.name in {"entries.py", "review.py"})

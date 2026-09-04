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
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.external_constants import OutputLanguage
from .....core.identity import TransactionId
from .....tests.terminal_sizes import TERMINAL_WIDE
from ....tui.components.host import ScreenHostApp
from ....tui.devtools.frame import geometry_band
from ....tui.navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import LedgerEntrySelected, LedgerWorkspaceController
from ..entries import LedgerEntriesScreen
from ..overview import LedgerOverviewScreen
from ..review import LedgerReviewScreen
from ..routes import LEDGER_ROUTES, LedgerUnavailableScreen, ledger_screen_factory, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TX_A = cast("TransactionId", "a" * 64)
_TX_B = cast("TransactionId", "b" * 64)
_LOCALE_EXPECTED = {
    OutputLanguage.ES: ("Resumen del libro contable", "Filtro: todos los estados de revisión", "Revisado"),
    OutputLanguage.EN: ("Ledger overview", "Filter: all review statuses", "Reviewed"),
    OutputLanguage.CA: ("Resum del llibre comptable", "Filtre: tots els estats de revisió", "Revisat"),
    OutputLanguage.HU: ("Főkönyvi áttekintés", "Szűrő: minden felülvizsgálati állapot", "Felülvizsgálva"),
}


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
        LedgerWorkspaceEntryRefV1(
            transaction_id=_TX_A,
            review_status="pending",
            date="2026-03-14",
            amount="1250.00",
            currency="EUR",
            direction="outgoing",
            counterparty="Suministros Delta SL",
            description="Material de oficina",
            business_classification="business",
        ),
        LedgerWorkspaceEntryRefV1(
            transaction_id=_TX_B,
            review_status="reviewed",
            date="2026-03-02",
            amount="480.50",
            currency="EUR",
            direction="incoming",
            counterparty="Cliente Omega SA",
            description="Servicios de consultoría",
            business_classification="business",
        ),
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


def _review_action() -> ActionReference:
    declaration = lookup_action("operator.ledger.review")
    return ActionReference(action_id=declaration.action_id)


def _controller(
    projection: LedgerWorkspaceProjectionV1,
    context: TuiScreenContextV1 | None = None,
) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        context or _context(), projection, LedgerWorkspaceInjection(review_action=_review_action())
    )


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
    controller = _controller(_projection())
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
    ):
        screen = resolve_ledger_screen(controller, controller.route_target(area))
        assert isinstance(screen, LedgerUnavailableScreen)
        assert screen.refusal is not None
        assert screen.refusal.target.area is area
    assert not isinstance(
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.RECONCILIATION)),
        LedgerUnavailableScreen,
    )


def test_factory_requires_real_outer_context_and_keeps_injected_projection() -> None:
    projection = _projection()
    screen = ledger_screen_factory(projection, review_action=_review_action())(_context())
    assert isinstance(screen, LedgerOverviewScreen)
    assert screen.controller.projection is projection
    with pytest.raises(ValueError, match=r"workbench\.ledger"):
        ledger_screen_factory(projection, review_action=_review_action())(
            TuiScreenContextV1(destination="workbench.home")
        )


def test_factory_refuses_undeclared_or_drifted_review_action_through_real_catalogue() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        ledger_screen_factory(_projection(), review_action=ActionReference(action_id="operator.ledger.absent"))
    classified = lookup_action("operator.ledger.classify")
    with pytest.raises(ValueError, match="canonical review query"):
        ledger_screen_factory(
            _projection(),
            review_action=ActionReference(action_id=classified.action_id),
        )
    review_action = _review_action()
    controller = _controller(_projection())
    assert all(row.action == review_action for row in controller.review_rows())
    assert lookup_action(review_action.action_id).target_command_key == "ledger.review"


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_type", (LedgerOverviewScreen, LedgerEntriesScreen, LedgerReviewScreen))
async def test_screens_show_seven_destinations_have_one_scroll_owner_and_no_horizontal_overflow(
    screen_type: type,
) -> None:
    screen = screen_type(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        navigation = screen.query_one("#ledger-navigation", DataTable)
        assert navigation.row_count == 7
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(widget for widget in screen.walk_children() if widget.display and widget.show_vertical_scrollbar)
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "ledger-page" for owner in owners)


@pytest.mark.asyncio
async def test_navigation_refusal_and_review_selection_preserve_semantic_identity() -> None:
    projection = _projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    screen = LedgerReviewScreen(_controller(projection))
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
async def test_entry_rows_show_the_operator_their_own_facts_and_tables_are_each_one_tab_stop() -> None:
    """The authenticated surface shows the entry, not a coordinate for it.

    This replaces a gate that asserted the opposite -- that the screen printed
    a truncated transaction id and withheld every financial fact. That policy
    is retired: the session is already authenticated against the operator's own
    ledger, so withholding the amount and counterparty withheld nothing from an
    adversary and made the review surface unusable for review.

    What is still asserted, because it is a different concern: the raw 64-char
    identifier is machine addressing and has no business being painted, and the
    two tables remain one tab stop each.
    """
    projection = _projection()
    screen = LedgerEntriesScreen(_controller(projection))
    app = ScreenHostApp[None](screen)
    # The widest supported terminal, because the column SET is responsive: a
    # narrow terminal drops the lowest-priority columns rather than overflowing
    # the right edge. Full disclosure is therefore asserted where every column
    # fits, and the sibling overflow gates own the narrow sizes.
    async with app.run_test(size=TERMINAL_WIDE) as pilot:
        await pilot.pause()
        assert tuple(widget.id for widget in screen.focus_chain) == ("ledger-navigation", "ledger-entries")
        copy = _all_copy(screen)
        for field in (
            "2026-03-14",
            "1250.00",
            "EUR",
            "outgoing",
            "Suministros Delta SL",
            "Material de oficina",
        ):
            assert field in copy, f"the entry's own {field!r} is not shown to the operator"
        assert "a" * 64 not in copy
        assert "b" * 64 not in copy


@pytest.mark.asyncio
async def test_unmeasured_areas_never_render_a_numeric_zero_and_review_discloses_all_statuses() -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language="en"):
        review_screen = LedgerReviewScreen(_controller(_projection()))
        app = ScreenHostApp[None](review_screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            navigation = review_screen.query_one("#ledger-navigation", DataTable)
            import_row = tuple(str(cell) for cell in navigation.get_row("import"))
            evidence_row = tuple(str(cell) for cell in navigation.get_row("evidence"))
            assert import_row[-1] == "Not measured"
            assert evidence_row[-1] == "Not measured"
            assert "0" not in {import_row[-1], evidence_row[-1]}
            rendered = _all_copy(review_screen)
            assert "Filter: all review statuses" in rendered
            assert "Pending" in rendered
            assert "Reviewed" in rendered
            assert "all pending review rows" not in rendered

        overview_screen = LedgerOverviewScreen(_controller(_projection()))
        overview_app = ScreenHostApp[None](overview_screen)
        async with overview_app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            quality = overview_screen.query_one("#ledger-quality", DataTable)
            evidence_row = tuple(str(cell) for cell in quality.get_row("evidence"))
            assert evidence_row == ("Evidence", "Not measured", "Not measured")
            assert "0" not in evidence_row


@pytest.mark.asyncio
async def test_transaction_focus_restores_by_identity_after_row_reordering() -> None:
    projection = _projection()
    reordered = projection.model_copy(update={"entries": tuple(reversed(projection.entries))})
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger",
            semantic_key="ledger.transaction",
            restore_token=_TX_A,
        ),
    )
    screen = LedgerEntriesScreen(_controller(reordered, context))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#ledger-entries", DataTable)
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == _TX_A
        await pilot.press("enter")
        await pilot.pause()
        assert screen.selected_transaction_id == _TX_A


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_every_locale_uses_catalogue_calls_without_raw_internal_vocabulary(locale: OutputLanguage) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language=locale.value):
        overview = LedgerOverviewScreen(_controller(_projection()))
        overview_app = ScreenHostApp[None](overview)
        async with overview_app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = _all_copy(overview)
            assert _LOCALE_EXPECTED[locale][0] in rendered
            assert "tui.ledger." not in rendered
            assert "needs_attention" not in rendered
            assert "never_captured" not in rendered
            assert "work_unit" not in rendered.lower()
            assert tuple(
                row.key.value for row in overview.query_one("#ledger-navigation", DataTable).ordered_rows
            ) == tuple(area.value for area in LedgerWorkspaceArea)
        review = LedgerReviewScreen(_controller(_projection()))
        review_app = ScreenHostApp[None](review)
        async with review_app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = _all_copy(review)
            assert _LOCALE_EXPECTED[locale][1] in rendered
            assert _LOCALE_EXPECTED[locale][2] in rendered
            assert tuple(row.key.value for row in review.query_one("#ledger-review", DataTable).ordered_rows) == (
                _TX_A,
                _TX_B,
            )


def test_ledger_locale_copy_is_genuinely_distinct_across_supported_languages() -> None:
    assert len({expected[0] for expected in _LOCALE_EXPECTED.values()}) == len(OutputLanguage)
    assert len({expected[1] for expected in _LOCALE_EXPECTED.values()}) == len(OutputLanguage)


def test_ledger_tui_has_no_io_adapter_cli_calculation_or_mutation_imports() -> None:
    package = Path(__file__).parents[1]
    production = tuple(path for path in package.glob("*.py") if path.name != "__init__.py")
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in production)
    imports = {node.module or "" for tree in trees for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for tree in trees for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("entrypoints.cli" in name or "adapters" in name or "calculations" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "unlink"} & calls
    assert all(
        "markup=False" in path.read_text(encoding="utf-8")
        for path in production
        if path.name in {"entries.py", "review.py"}
    )

@pytest.mark.asyncio
async def test_selecting_an_entry_makes_the_classification_area_reachable() -> None:
    """A destination the session can never open should not be offered at all.

    Classification is entered WITH a chosen row, and the target used to be
    fixed when the workspace was composed -- before the operator had chosen
    anything. So in a real session the area was permanently refused: the
    navigation table listed a destination that could not open, and the
    selection made on the entries screen went nowhere.

    Asserts the refusal BEFORE and its absence AFTER, because either half
    alone proves nothing: a screen that always admits classification would pass
    the second, and one that never does would pass the first.
    """
    projection = _projection()
    controller = _controller(projection)
    screen = LedgerEntriesScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=TERMINAL_WIDE) as pilot:
        await pilot.pause()
        assert controller.refusal_for(LedgerWorkspaceArea.CLASSIFICATION) is not None, (
            "classification was already reachable, so this cannot show a selection changed anything"
        )

        chosen = projection.entries[0].transaction_id
        screen.post_message(LedgerEntrySelected(chosen))
        await pilot.pause()

        assert controller.classification_target == chosen
        assert controller.refusal_for(LedgerWorkspaceArea.CLASSIFICATION) is None, (
            "the operator chose an entry and classification is still refused, so the selection "
            "carried nowhere"
        )
        app.exit(None)


def test_a_classification_target_outside_the_visible_projection_is_refused() -> None:
    """A target the snapshot does not contain would open on an invisible row."""
    controller = _controller(_projection())
    with pytest.raises(ValueError, match="absent from the visible Ledger projection"):
        controller.select_classification_target("f" * 64)

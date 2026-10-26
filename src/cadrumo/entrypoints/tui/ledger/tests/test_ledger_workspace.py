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
    LedgerWorkspaceAvailability,
    LedgerWorkspaceProjectionV1,
)
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....application.user_profile.language_resolver import adopt_profile_output_language, register_language_resolver
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.identity.transaction_ids import TransactionId
from .....tests.terminal_sizes import TERMINAL_WIDE
from ...components.host import ScreenHostApp
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ...tests.frame import geometry_band
from ...tests.settling import settle
from ..controller import LEDGER_TRANSACTION_FOCUS
from ..entries import LedgerEntriesScreen
from ..overview import LedgerOverviewScreen
from ..review import LedgerReviewScreen
from ..routes import LEDGER_ROUTES, LedgerUnavailableScreen, ledger_screen_factory, resolve_ledger_screen
from .workspace_fixtures import (
    LEDGER_TX_A,
    LEDGER_TX_B,
    ledger_context,
    ledger_controller,
    ledger_evidence_action,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALE_EXPECTED = {
    OutputLanguage.ES: ("Registros: resumen", "Filtro: todos los estados de revisión", "Revisado"),
    OutputLanguage.EN: ("Records: overview", "Filter: all review statuses", "Reviewed"),
    OutputLanguage.CA: ("Registres: resum", "Filtre: tots els estats de revisió", "Revisat"),
    OutputLanguage.HU: ("Nyilvántartás: áttekintés", "Szűrő: minden felülvizsgálati állapot", "Felülvizsgálva"),
}


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
    controller = ledger_controller(ledger_projection())
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
    projection = ledger_projection()
    screen = ledger_screen_factory(projection, review_action=ledger_review_action())(ledger_context())
    assert isinstance(screen, LedgerOverviewScreen)
    assert screen.controller.projection is projection
    with pytest.raises(ValueError, match=r"workbench\.ledger"):
        ledger_screen_factory(projection, review_action=ledger_review_action())(
            TuiScreenContextV1(destination="workbench.home")
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", (LEDGER_TX_B, cast("TransactionId", "f" * 64)), ids=("shown", "not-shown"))
async def test_a_selection_landing_on_the_overview_because_entries_are_unavailable_says_it_was_dropped(
    selected: TransactionId,
) -> None:
    projection = ledger_projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    factory = ledger_screen_factory(projection, review_action=ledger_review_action())
    screen = factory(ledger_focused_context(selected))
    assert isinstance(screen, LedgerOverviewScreen)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        notice = str(screen.query_one("#ledger-refusal", Static).render())
    assert notice == tr("tui.ledger.overview.selection_dropped")
    assert notice != "tui.ledger.overview.selection_dropped"


@pytest.mark.asyncio
async def test_an_overview_opened_without_a_selection_carries_no_notice() -> None:
    projection = ledger_projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    screen = ledger_screen_factory(projection, review_action=ledger_review_action())(ledger_context())
    assert isinstance(screen, LedgerOverviewScreen)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        assert str(screen.query_one("#ledger-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_a_refused_area_picked_by_an_action_carries_no_entries_notice_even_with_a_selection() -> None:
    projection = ledger_projection(unavailable=LedgerWorkspaceArea.EVIDENCE)
    evidence = ledger_evidence_action()
    factory = ledger_screen_factory(projection, review_action=ledger_review_action(), evidence_action=evidence)
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger", semantic_key=LEDGER_TRANSACTION_FOCUS, restore_token=LEDGER_TX_B
        ),
        action_candidate_id=evidence.action_id,
    )
    screen = factory(context)
    assert isinstance(screen, LedgerOverviewScreen)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        assert str(screen.query_one("#ledger-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_the_dropped_selection_notice_is_reworded_when_the_language_changes() -> None:
    projection = ledger_projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    screen = ledger_screen_factory(projection, review_action=ledger_review_action())(
        ledger_focused_context(LEDGER_TX_B)
    )
    assert isinstance(screen, LedgerOverviewScreen)
    with override_settings(cadrumo_output_language=""):
        register_language_resolver()
        adopt_profile_output_language(OutputLanguage.EN)
        try:
            async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
                await settle(pilot)
                english = str(screen.query_one("#ledger-refusal", Static).render())
                adopt_profile_output_language(OutputLanguage.ES)
                await screen.refresh_language()
                await settle(pilot)
                spanish = str(screen.query_one("#ledger-refusal", Static).render())
                expected = tr("tui.ledger.overview.selection_dropped")
        finally:
            adopt_profile_output_language(None)
    assert english != spanish
    assert spanish == expected
    assert spanish != "tui.ledger.overview.selection_dropped"


def _whole_ledger_unavailable() -> LedgerWorkspaceProjectionV1:
    """A projection whose every area, the overview included, is locked."""
    projection = ledger_projection()
    return projection.model_copy(
        update={
            "areas": tuple(
                state.model_copy(
                    update={"availability": LedgerWorkspaceAvailability.LOCKED, "reason_code": "ledger.locked"}
                )
                for state in projection.areas
            )
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", (True, False), ids=("with-selection", "without-selection"))
async def test_an_unavailable_ledger_says_the_selected_entry_is_not_shown_only_when_one_was_selected(
    selected: bool,
) -> None:
    factory = ledger_screen_factory(_whole_ledger_unavailable(), review_action=ledger_review_action())
    screen = factory(ledger_focused_context(LEDGER_TX_B) if selected else ledger_context())
    assert isinstance(screen, LedgerUnavailableScreen)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        clause = screen.query("#ledger-selection-dropped")
        refusal = str(screen.query_one("#ledger-refusal", Static).render())
        if selected:
            text = str(cast(Static, clause.first()).render())
            assert text == tr("tui.ledger.unavailable.selection_dropped")
            assert text != "tui.ledger.unavailable.selection_dropped"
        else:
            assert not clause
    assert refusal == tr("tui.ledger.refusal.application_state")


def test_factory_refuses_undeclared_or_drifted_review_action_through_real_catalogue() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        ledger_screen_factory(ledger_projection(), review_action=ActionReference(action_id="operator.ledger.absent"))
    classified = lookup_action("operator.ledger.classify")
    with pytest.raises(ValueError, match="canonical review query"):
        ledger_screen_factory(
            ledger_projection(),
            review_action=ActionReference(action_id=classified.action_id),
        )
    review_action = ledger_review_action()
    assert ledger_controller(ledger_projection()).review_action == review_action
    assert lookup_action(review_action.action_id).target_command_key == "ledger.review"


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_type", (LedgerOverviewScreen, LedgerEntriesScreen, LedgerReviewScreen))
async def test_screens_show_seven_destinations_have_one_scroll_owner_and_no_horizontal_overflow(
    screen_type: type,
) -> None:
    screen = screen_type(ledger_controller(ledger_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        navigation = screen.query_one("#ledger-navigation", DataTable)
        assert navigation.row_count == 7
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(widget for widget in screen.walk_children() if widget.display and widget.show_vertical_scrollbar)
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "ledger-page" for owner in owners)


@pytest.mark.asyncio
async def test_navigation_refusal_and_review_selection_preserve_semantic_identity() -> None:
    projection = ledger_projection(unavailable=LedgerWorkspaceArea.ENTRIES)
    screen = LedgerReviewScreen(ledger_controller(projection))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        navigation = screen.query_one("#ledger-navigation", DataTable)
        navigation.move_cursor(row=1)
        await pilot.press("enter")
        await settle(pilot)
        assert screen.refusal is not None
        assert screen.refusal.target.area is LedgerWorkspaceArea.ENTRIES
        assert "ledger.locked" not in _all_copy(screen)
        review = screen.query_one("#ledger-review", DataTable)
        review.focus()
        await pilot.press("down", "enter")
        await settle(pilot)
        assert screen.requested_transaction_id == LEDGER_TX_B
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
    projection = ledger_projection()
    screen = LedgerEntriesScreen(ledger_controller(projection))
    app = ScreenHostApp[None](screen)
    # The widest supported terminal, because the column SET is responsive: a
    # narrow terminal drops the lowest-priority columns rather than overflowing
    # the right edge. Full disclosure is therefore asserted where every column
    # fits, and the sibling overflow gates own the narrow sizes.
    async with app.run_test(size=TERMINAL_WIDE) as pilot:
        await settle(pilot)
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
    with override_settings(cadrumo_output_language="en"):
        review_screen = LedgerReviewScreen(ledger_controller(ledger_projection()))
        app = ScreenHostApp[None](review_screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
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

        overview_screen = LedgerOverviewScreen(ledger_controller(ledger_projection()))
        overview_app = ScreenHostApp[None](overview_screen)
        async with overview_app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            quality = overview_screen.query_one("#ledger-quality", DataTable)
            evidence_row = tuple(str(cell) for cell in quality.get_row("evidence"))
            assert evidence_row == ("Supporting documents", "Not measured", "Not measured")
            assert "0" not in evidence_row


@pytest.mark.asyncio
async def test_transaction_focus_restores_by_identity_after_row_reordering() -> None:
    projection = ledger_projection()
    reordered = projection.model_copy(update={"entries": tuple(reversed(projection.entries))})
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger",
            semantic_key="ledger.transaction",
            restore_token=LEDGER_TX_A,
        ),
    )
    screen = LedgerEntriesScreen(ledger_controller(reordered, context))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        table = screen.query_one("#ledger-entries", DataTable)
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == LEDGER_TX_A
        await pilot.press("enter")
        await settle(pilot)
        assert screen.selected_transaction_id == LEDGER_TX_A


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_every_locale_uses_catalogue_calls_without_raw_internal_vocabulary(locale: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=locale.value):
        overview = LedgerOverviewScreen(ledger_controller(ledger_projection()))
        overview_app = ScreenHostApp[None](overview)
        async with overview_app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            rendered = _all_copy(overview)
            assert _LOCALE_EXPECTED[locale][0] in rendered
            assert "tui.ledger." not in rendered
            assert "needs_attention" not in rendered
            assert "never_captured" not in rendered
            assert "work_unit" not in rendered.lower()
            assert tuple(
                row.key.value for row in overview.query_one("#ledger-navigation", DataTable).ordered_rows
            ) == tuple(area.value for area in LedgerWorkspaceArea)
        review = LedgerReviewScreen(ledger_controller(ledger_projection()))
        review_app = ScreenHostApp[None](review)
        async with review_app.run_test(size=(80, 24)) as pilot:
            await settle(pilot)
            rendered = _all_copy(review)
            assert _LOCALE_EXPECTED[locale][1] in rendered
            assert _LOCALE_EXPECTED[locale][2] in rendered
            assert tuple(row.key.value for row in review.query_one("#ledger-review", DataTable).ordered_rows) == (
                LEDGER_TX_A,
                LEDGER_TX_B,
            )


def test_ledger_locale_copy_is_genuinely_distinct_across_supported_languages() -> None:
    assert len({expected[0] for expected in _LOCALE_EXPECTED.values()}) == len(OutputLanguage)
    assert len({expected[1] for expected in _LOCALE_EXPECTED.values()}) == len(OutputLanguage)


def test_ledger_tui_has_no_io_adapter_cli_calculation_or_mutation_imports() -> None:
    package = Path(__file__).parents[1]
    production = tuple(path for path in package.glob("*.py") if path.name != "__init__.py")
    assert production, (
        f"the sweep of {package} matched no production module; a walk that reads nothing "
        "reports no forbidden adapter or calculation import because it reads no import at all"
    )
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

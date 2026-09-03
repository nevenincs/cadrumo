"""Calendar filtering, interaction, locale, geometry, and security contracts."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Input, Select, Static

from .....application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from .....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from .....application.overview.home import HomeAvailability
from .....application.overview.next_actions import declare_next_action
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.deadlines.models import ObligationStatus
from ...components.host import ScreenHostApp
from ...devtools.frame import geometry_band
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..calendar import DeclarationsCalendarScreen
from ..controller import DeclarationsCalendarController, calendar_focus_key
from ..models import DeclarationsCalendarScopeV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_EXPECTED = {
    OutputLanguage.ES: ("Agenda de declaraciones", "Vencida", "Legal:", "Abrir esta declaración"),
    OutputLanguage.EN: ("Declarations agenda", "Overdue", "Legal:", "Open this declaration"),
    OutputLanguage.CA: ("Agenda de declaracions", "Vençuda", "Legal:", "Obre aquesta declaració"),
    OutputLanguage.HU: ("Bevallási napirend", "Lejárt", "Jogi:", "Bevallás megnyitása"),
}


def _row(
    modelo: str,
    period_code: str,
    closes: date,
    legal: ObligationStatus,
    user: OverviewPeriodState,
    *,
    local: OverviewLocalFilingState | None = OverviewLocalFilingState.READY_TO_FILE,
    aeat: OverviewAeatSubmissionState | None = OverviewAeatSubmissionState.NOT_OBSERVED,
) -> DeclarationsCalendarEntryRefV1:
    return DeclarationsCalendarEntryRefV1(
        modelo=modelo,
        filing_year=2026,
        period=Period.from_year_and_code(2026, period_code),
        opens_on=closes.replace(day=1),
        adjusted_closes_on=closes,
        payment_cutoff_on=closes.replace(day=max(1, closes.day - 5)),
        legal_status=legal,
        user_state=user,
        local_filing_state=local,
        aeat_submission_state=aeat,
        justificante_verified=None if aeat is None else False,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )


def _projection(*, evidence_unobservable: bool = False) -> DeclarationsCalendarProjectionV1:
    rows = (
        _row("130", "1T", date(2026, 4, 20), ObligationStatus.OVERDUE, OverviewPeriodState.LATE),
        _row(
            "303",
            "2T",
            date(2026, 7, 20),
            ObligationStatus.FILED,
            OverviewPeriodState.FILED,
            local=OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED,
        ),
        _row("111", "3T", date(2026, 10, 20), ObligationStatus.UPCOMING, OverviewPeriodState.DUE),
    )
    if evidence_unobservable:
        rows = tuple(row.model_copy(update={"aeat_submission_state": None, "justificante_verified": None}) for row in rows)
    return DeclarationsCalendarProjectionV1(
        as_of=date(2026, 9, 3),
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        sources=(
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.SCHEDULE,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=3,
            ),
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.LOCAL_FILING,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=2,
            ),
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.AEAT_EVIDENCE,
                availability=(
                    HomeAvailability.NEVER_CAPTURED
                    if evidence_unobservable
                    else HomeAvailability.AVAILABLE
                ),
                observed_at=None if evidence_unobservable else _NOW,
                reason_code="calendar.aeat.never" if evidence_unobservable else None,
                item_count=None if evidence_unobservable else 0,
            ),
        ),
        entries=rows,
    )


def _controller(
    projection: DeclarationsCalendarProjectionV1,
    *,
    handoff=None,
    recovery_handoff=None,
    context: TuiScreenContextV1 | None = None,
) -> DeclarationsCalendarController:
    return DeclarationsCalendarController(
        context or TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        entry_handoff=handoff,
        recovery_handoff=recovery_handoff,
    )


def _rendered(screen: DeclarationsCalendarScreen) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row in range(table.row_count)
        for cell in table.get_row_at(row)
    )
    return "\n".join(values)


def test_exact_scope_overlap_and_evidence_unknown_uses_source_observability() -> None:
    controller = _controller(_projection())
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.ALL, "")] == [
        "130",
        "303",
        "111",
    ]
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.PAST, "")] == [
        "130",
        "303",
    ]
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.OVERDUE, "")] == ["130"]
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.FILED, "")] == ["303"]
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.UPCOMING, "")] == ["111"]
    assert controller.visible_entries(DeclarationsCalendarScopeV1.EVIDENCE_UNKNOWN, "") == ()
    unknown = _controller(_projection(evidence_unobservable=True))
    assert len(unknown.visible_entries(DeclarationsCalendarScopeV1.EVIDENCE_UNKNOWN, "")) == 3


def test_unicode_and_search_uses_only_safe_localized_fields() -> None:
    controller = _controller(_projection())
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.ALL, "VENCIDA 130")] == ["130"]
    assert [row.modelo for row in controller.visible_entries(DeclarationsCalendarScopeV1.ALL, "20/10/2026 111")] == ["111"]
    assert controller.visible_entries(DeclarationsCalendarScopeV1.ALL, "private-work-name nif-token") == ()


def test_recovery_action_must_match_catalogue_and_natural_address() -> None:
    base = _projection()
    wrong_action = base.entries[0].model_copy(
        update={"recovery_action": declare_next_action("operator.modelo.work.list")}
    )
    with pytest.raises(ValueError, match="canonical create action"):
        _controller(base.model_copy(update={"entries": (wrong_action, *base.entries[1:])}))
    wrong_address = base.entries[0].model_copy(
        update={
            "recovery_action": declare_next_action(
                "operator.modelo.work.create", modelo="303", year=2026, period="1T"
            )
        }
    )
    with pytest.raises(ValueError, match="natural address"):
        _controller(base.model_copy(update={"entries": (wrong_address, *base.entries[1:])}))


@pytest.mark.asyncio
async def test_three_control_focus_chain_semantic_restore_callback_and_geometry() -> None:
    selected: list[DeclarationsCalendarEntryRefV1] = []
    screen = DeclarationsCalendarScreen(_controller(_projection(), handoff=selected.append))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        search = screen.query_one("#declarations-calendar-search", Input)
        scope = screen.query_one("#declarations-calendar-scope", Select)
        table = screen.query_one("#declarations-calendar-agenda", DataTable)
        assert app.focused is search
        await pilot.press("tab")
        assert app.focused is scope
        await pilot.press("tab")
        assert app.focused is table
        table.move_cursor(row=1)
        chosen_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        search.value = "303"
        await pilot.pause()
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen_key
        search.value = ""
        await pilot.pause()
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen_key
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert selected == [_projection().entries[1]]
        assert geometry_band(app, 80) == []
        assert table.max_scroll_x == 0
        owners = tuple(
            widget
            for widget in screen.walk_children()
            if widget.display and getattr(widget, "show_vertical_scrollbar", False)
        )
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "declarations-calendar-page" for owner in owners)


@pytest.mark.asyncio
async def test_missing_handoff_refuses_and_escape_dismisses_only_child() -> None:
    screen = DeclarationsCalendarScreen(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-calendar-agenda", DataTable)
        table.focus()
        await pilot.press("enter")
        assert "destino" in str(screen.query_one("#declarations-calendar-notice", Static).render()).lower()
        await pilot.press("escape")
        await pilot.pause()
        assert app.return_value is None


@pytest.mark.asyncio
async def test_recovery_row_has_explicit_verb_and_only_calls_canonical_recovery() -> None:
    base = _projection()
    recovery_row = base.entries[0].model_copy(
        update={
            "recovery_action": declare_next_action(
                "operator.modelo.work.create", modelo="130", year=2026, period="1T"
            )
        }
    )
    projection = base.model_copy(update={"entries": (recovery_row, *base.entries[1:])})
    ordinary: list[object] = []
    recovered: list[object] = []
    screen = DeclarationsCalendarScreen(
        _controller(
            projection,
            handoff=ordinary.append,
            recovery_handoff=lambda action, row: recovered.append((action, row)),
        )
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        rendered = _rendered(screen)
        assert "Crear o recuperar esta declaración" in rendered
        table = screen.query_one("#declarations-calendar-agenda", DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert ordinary == []
        assert recovered == [(recovery_row.recovery_action, recovery_row)]

    refused = DeclarationsCalendarScreen(_controller(projection, handoff=ordinary.append))
    refused_app = ScreenHostApp[None](refused)
    async with refused_app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        refused.query_one("#declarations-calendar-agenda", DataTable).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert ordinary == []
        assert str(refused.query_one("#declarations-calendar-notice", Static).render())


@pytest.mark.asyncio
async def test_available_without_timestamp_is_not_rendered_as_never_observed() -> None:
    base = _projection()
    sources = tuple(
        state.model_copy(update={"observed_at": None})
        if state.source is DeclarationsCalendarSource.SCHEDULE
        else state
        for state in base.sources
    )
    screen = DeclarationsCalendarScreen(_controller(base.model_copy(update={"sources": sources})))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        rendered = _rendered(screen)
        assert "Actual y disponible; hora de observación no registrada" in rendered
        assert "Nunca observado" not in rendered


@pytest.mark.asyncio
async def test_context_focus_hidden_filter_reorder_resize_and_child_return_restore_exact_row() -> None:
    projection = _projection()
    target = projection.entries[1]
    context = TuiScreenContextV1(
        destination="workbench.declarations",
        focus=TuiFocusIdentityV1(
            destination="workbench.declarations",
            semantic_key=calendar_focus_key(target),
        ),
    )
    screen = DeclarationsCalendarScreen(_controller(projection, context=context))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 18)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-calendar-agenda", DataTable)
        assert app.focused is table
        target_key = "303|2026|2T"
        assert table.ordered_rows[table.cursor_row].key.value == target_key

        screen.query_one("#declarations-calendar-search", Input).value = "111"
        await pilot.pause()
        assert table.ordered_rows[table.cursor_row].key.value == "111|2026|3T"
        screen.query_one("#declarations-calendar-search", Input).value = ""
        await pilot.pause()
        assert table.ordered_rows[table.cursor_row].key.value == target_key

        reordered = projection.model_copy(update={"entries": tuple(reversed(projection.entries))})
        screen.replace_projection(reordered)
        await pilot.resize_terminal(100, 22)
        await pilot.pause()
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == target_key
        assert table.scroll_offset.y <= table.cursor_row
        assert table.cursor_row < table.scroll_offset.y + table.scrollable_content_region.height

        child = Screen[None]()
        await app.push_screen(child)
        child.dismiss(None)
        await pilot.pause()
        assert app.screen is screen
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == target_key


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_real_locales_change_copy_but_not_natural_semantics(locale: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=locale.value):
        screen = DeclarationsCalendarScreen(_controller(_projection()))
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = _rendered(screen)
            for expected in _EXPECTED[locale]:
                assert expected in rendered
            assert "Modelo 130 · 2026 · 1T" in rendered
            assert "tui.declarations" not in rendered
            assert "not_observed" not in rendered


def test_calendar_module_has_no_io_adapter_cli_or_protected_search_fields() -> None:
    module = Path(__file__).parents[1] / "calendar.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not {"open", "Path", "repository", "adapter", "cli"}.intersection(imports)
    source = module.read_text(encoding="utf-8").lower()
    for forbidden in ("work_unit_id", "filing_record_id", "calculation_revision_id", "nif", "url"):
        assert forbidden not in source

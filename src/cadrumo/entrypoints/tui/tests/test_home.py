"""Focused compositor and authority-boundary proof for the production Home."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewFilingStatus,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....application.overview.filing_status_words import filing_status_words
from ....application.overview.home import HomeAgendaEntry, HomeAvailability, HomeProjectionV1, HomeZoneState
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....application.workbench_generation_home_words import serve_home_projection
from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..home import HomeLinkSelected, HomeLinkV1, HomeScreen
from .frame import geometry_band, screen_text
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .settling import settle

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _english_surface():
    """Assert against one named language rather than the ambient default.

    Home renders through the locale catalogue, so its words follow whichever
    language the environment resolves. Pinning English here keeps these
    assertions about LAYOUT and CONCEPT; the per-language coverage is the
    catalogue parity gate's job, not this module's.
    """
    with override_settings(cadrumo_output_language=OutputLanguage.EN.value):
        yield


@pytest.mark.asyncio
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
@pytest.mark.parametrize("theme", (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME))
async def test_home_renders_the_selected_due_driven_projection_without_overflow(
    size: tuple[int, int], theme: str
) -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=size) as pilot:
        await settle(pilot)
        app.theme = theme
        await settle(pilot)
        assert geometry_band(app, size[0]) == []
        assert not screen.show_vertical_scrollbar
        assert all(cast("DataTable[str]", table).max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget
            for widget in screen.walk_children(VerticalScroll)
            if widget.display and widget.show_vertical_scrollbar
        )
        assert all(isinstance(owner, VerticalScroll) and owner.id == "home-page" for owner in owners)
        assert len(owners) <= 1
        assert tuple(widget.id for widget in screen.focus_chain) == (
            "home-actions",
            "home-declarations",
            "home-links",
            "home-account-links",
            "home-agenda",
        )
        assert app.focused is not None and app.focused.id == "home-actions"
        rendered = screen_text(app, *size)
        # The session line belongs to the root's account bar, which reads the
        # live session; a bare host has none, so the bar names the account only.
        assert tr("tui.root.account.default_profile") in rendered
        assert "Active local session" not in rendered
        assert str(screen.query_one("#home-ledger", Static).render()).startswith("Available -")
        assert str(screen.query_one("#home-agenda-state", Static).render()).startswith("Available")
        assert len(projection.actions) <= 3
        action_table = screen.query_one("#home-actions", DataTable)
        assert tuple(
            cast("DataTable[str]", action_table).get_row_at(index)[0] for index in range(action_table.row_count)
        ) == tuple(item.action_words for item in projection.actions)
        assert all(item.action_words is not None for item in projection.actions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected"),
    (
        (
            HomeFixtureScenario.READY,
            {
                "M130": OverviewFilingStatus.SUBMITTED,
                "M303": OverviewFilingStatus.RECORDED_LOCALLY,
                "M390": OverviewFilingStatus.RECEIPT_VERIFIED,
            },
        ),
        (
            HomeFixtureScenario.BLOCKED,
            {
                "M130": OverviewFilingStatus.SUBMITTED,
                "M303": OverviewFilingStatus.DUE,
                "M390": OverviewFilingStatus.ACCEPTED,
            },
        ),
    ),
)
async def test_home_agenda_rows_carry_one_filing_status_each(
    scenario: HomeFixtureScenario, expected: dict[str, OverviewFilingStatus]
) -> None:
    screen = HomeScreen(build_home_projection_fixture(scenario))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#home-agenda", DataTable))
        rows = tuple(str(table.get_row_at(index)[0]) for index in range(table.row_count))
        evidence = screen.query_one("#home-evidence", Static)
        text = "\n".join(str(widget.render()) for widget in screen.query(Static) if widget.display)
    statuses = {row.split(" · ")[1].split()[0]: row.split(" · ", 2)[2] for row in rows}
    assert statuses == {address: filing_status_words(status, OutputLanguage.EN) for address, status in expected.items()}
    assert not evidence.display
    assert "Local:" not in text
    assert "observed" not in text


type _RowAxes = tuple[OverviewPeriodState, OverviewLocalFilingState, OverviewAeatSubmissionState]

_AXES_BY_AGENDA: tuple[tuple[_RowAxes, ...], ...] = (
    (
        (
            OverviewPeriodState.LATE,
            OverviewLocalFilingState.NOT_READY_TO_FILE,
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
        ),
        (OverviewPeriodState.DUE, OverviewLocalFilingState.NOT_READY_TO_FILE, OverviewAeatSubmissionState.ACCEPTED),
        (
            OverviewPeriodState.FILED,
            OverviewLocalFilingState.NOT_READY_TO_FILE,
            OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        ),
    ),
    (
        (
            OverviewPeriodState.FILED,
            OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED,
            OverviewAeatSubmissionState.NOT_OBSERVED,
        ),
        (OverviewPeriodState.DUE, OverviewLocalFilingState.READY_TO_FILE, OverviewAeatSubmissionState.NOT_OBSERVED),
        (
            OverviewPeriodState.FILED,
            OverviewLocalFilingState.NOT_READY_TO_FILE,
            OverviewAeatSubmissionState.NOT_OBSERVED,
        ),
    ),
    (
        (OverviewPeriodState.DUE, OverviewLocalFilingState.NOT_READY_TO_FILE, OverviewAeatSubmissionState.NOT_OBSERVED),
        (
            OverviewPeriodState.LATE,
            OverviewLocalFilingState.NOT_READY_TO_FILE,
            OverviewAeatSubmissionState.NOT_OBSERVED,
        ),
        (
            OverviewPeriodState.UNKNOWN,
            OverviewLocalFilingState.NOT_READY_TO_FILE,
            OverviewAeatSubmissionState.NOT_OBSERVED,
        ),
    ),
)
"""Evidence axes for three previewed agendas, which between them the projection serves every filing status for."""


def _served_agenda(axes: tuple[_RowAxes, ...]) -> HomeProjectionV1:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    agenda = tuple(
        HomeAgendaEntry.worded(
            modelo=entry.modelo,
            filing_year=entry.filing_year,
            period=entry.period,
            due_on=entry.due_on,
            period_state=period,
            local_filing_state=local,
            aeat_submission_state=aeat,
            language=entry.words_language,
        )
        for entry, (period, local, aeat) in zip(projection.agenda, axes, strict=True)
    )
    return projection.model_copy(update={"agenda": agenda})


def test_the_home_agendas_cover_every_filing_status_the_projection_serves() -> None:
    served = {entry.filing_status for axes in _AXES_BY_AGENDA for entry in _served_agenda(axes).agenda}
    assert served == set(OverviewFilingStatus)


@pytest.mark.asyncio
@pytest.mark.parametrize("axes", _AXES_BY_AGENDA)
async def test_home_agenda_words_each_row_by_the_filing_status_the_projection_serves(
    axes: tuple[_RowAxes, ...],
) -> None:
    """Home says the status the projection decided for each row; it ranks no evidence of its own."""
    projection = _served_agenda(axes)
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#home-agenda", DataTable))
        rows = tuple(str(table.get_row_at(index)[0]) for index in range(table.row_count))
    assert len(rows) == len(projection.agenda)
    assert {row.split(" · ")[1].split()[0]: row.split(" · ", 2)[2] for row in rows} == {
        f"M{entry.modelo}": filing_status_words(entry.filing_status, OutputLanguage.EN) for entry in projection.agenda
    }


@pytest.mark.asyncio
async def test_home_agenda_says_the_served_date_and_period_words() -> None:
    """Home shows the date and period words the projection serves; it formats neither itself."""
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#home-agenda", DataTable))
        rows = tuple(str(table.get_row_at(index)[0]) for index in range(table.row_count))
    assert rows == tuple(
        f"{entry.due_on_text} · M{entry.modelo} {entry.period_words} · "
        f"{filing_status_words(entry.filing_status, OutputLanguage.EN)}"
        for entry in projection.agenda
    )


@pytest.mark.asyncio
async def test_home_says_the_words_the_projection_served_for_every_code_it_carries() -> None:
    """Actions, reasons, declaration states, periods and the ledger counts are the served words, not Home's own."""
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        declarations = cast("DataTable[str]", screen.query_one("#home-declarations", DataTable))
        rows = tuple(str(declarations.get_row_at(index)[0]) for index in range(declarations.row_count))
        contexts = str(screen.query_one("#home-action-contexts", Static).render())
        ledger = str(screen.query_one("#home-ledger", Static).render())
    assert rows == tuple(
        f"M{item.modelo} {item.period_words} · {item.name} · {item.state_words}" for item in projection.declarations
    )
    for item in projection.actions:
        assert item.action_words is not None and item.reason_words is not None
        assert f"{item.action_words} - {item.reason_words}" in contexts
    assert projection.ledger is not None and projection.ledger.summary_words is not None
    assert ledger == tr(
        "tui.home.availability.available_empty",
        label=tr("tui.home.availability.available"),
        detail=projection.ledger.summary_words,
    )


@pytest.mark.asyncio
async def test_home_serves_the_reason_a_zone_is_not_showing_its_data() -> None:
    reason = "workbench.home.actions_projector_unavailable"
    base = build_home_projection_fixture(HomeFixtureScenario.UNAVAILABLE)
    unavailable = HomeZoneState(availability=HomeAvailability.UNAVAILABLE, reason_code=reason)
    projection = serve_home_projection(
        base.model_copy(update={"actions_state": unavailable}), OutputLanguage(output_language())
    )
    served = projection.actions_state.reason_words
    assert served is not None
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        shown = str(screen.query_one("#home-actions-state", Static).render())
        generic = str(screen.query_one("#home-declarations-state", Static).render())
    assert shown == served
    assert generic == tr("tui.home.availability.unavailable")


@pytest.mark.asyncio
async def test_home_meets_a_projection_with_no_served_words_in_its_own_generic_words() -> None:
    """Words the projection did not serve are absent or generic, never a catalogue key or an identifier."""
    served = build_home_projection_fixture(HomeFixtureScenario.READY)
    bare = served.model_copy(
        update={
            "actions": tuple(
                item.model_copy(
                    update={"action_words": None, "reason_words": None, "period_words": None, "words_language": None}
                )
                for item in served.actions
            ),
            "declarations": tuple(
                item.model_copy(update={"state_words": None, "period_words": None, "words_language": None})
                for item in served.declarations
            ),
            "ledger": None
            if served.ledger is None
            else served.ledger.model_copy(update={"summary_words": None, "words_language": None}),
        }
    )
    screen = HomeScreen(bare)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        actions = cast("DataTable[str]", screen.query_one("#home-actions", DataTable))
        action_rows = tuple(str(actions.get_row_at(index)[0]) for index in range(actions.row_count))
        declarations = cast("DataTable[str]", screen.query_one("#home-declarations", DataTable))
        declaration_rows = tuple(str(declarations.get_row_at(index)[0]) for index in range(declarations.row_count))
        contexts = str(screen.query_one("#home-action-contexts", Static).render())
        ledger = str(screen.query_one("#home-ledger", Static).render())
    assert action_rows == (tr("tui.search.action.unknown"),) * len(bare.actions)
    assert tr("tui.home.action.reason") in contexts
    assert declaration_rows == tuple(f"M{item.modelo} · {item.name}" for item in bare.declarations)
    assert ledger == tr("tui.home.availability.available")


def test_home_module_reads_no_filing_evidence_axis() -> None:
    module = Path(__file__).parents[1] / "home.py"
    source = module.read_text(encoding="utf-8")
    for axis in (
        "OverviewAeatSubmissionState",
        "OverviewLocalFilingState",
        "OverviewPeriodState",
        "tui.home.filing_status",
        "overview.filing_status.",
    ):
        assert axis not in source, axis


@pytest.mark.asyncio
async def test_home_names_an_unread_aeat_source_under_the_agenda() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.NEVER_CAPTURED))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        evidence = screen.query_one("#home-evidence", Static)
        assert evidence.display
        assert str(evidence.render()).startswith("AEAT data: Not read yet")


@pytest.mark.asyncio
async def test_home_selection_and_escape_are_host_requests_not_business_calls() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert screen.selected_target == screen.highlighted_target
        await pilot.press("escape")
        await settle(pilot)
    assert screen.back_requested


@pytest.mark.asyncio
async def test_home_keeps_unknown_ledger_and_messages_as_unknown_not_zero() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.LOCKED))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        text = "\n".join(str(widget.render()) for widget in screen.query(Static))
    assert "Records readiness\nLocked" in text
    assert "Messages\nLocked" in text
    assert "Available - 0" not in text


class _LinkRecordingHost(ScreenHostApp[None]):
    """A bare host that keeps every link Home asks it to open, in order."""

    def __init__(self, screen: HomeScreen) -> None:
        super().__init__(screen)
        self.links: list[HomeLinkV1] = []

    def on_home_link_selected(self, event: HomeLinkSelected) -> None:
        self.links.append(event.link)


def _link_rows(screen: HomeScreen, table_id: str) -> tuple[str, ...]:
    table = cast("DataTable[str]", screen.query_one(table_id, DataTable))
    return tuple(str(table.get_row_at(index)[0]) for index in range(table.row_count))


@pytest.mark.asyncio
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
async def test_home_lists_every_page_and_account_door_with_the_key_that_opens_it(size: tuple[int, int]) -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=size) as pilot:
        await settle(pilot)
        links = _link_rows(screen, "#home-links")
        account = _link_rows(screen, "#home-account-links")
        keys = screen.query_one("#home-link-keys", Static)
        rendered = screen_text(app, *size)
        keys_text = str(keys.render())
        keys_shown = keys.display and keys.region.height > 0
    assert links == (
        "d   Declarations",
        "+   New declaration",
        "/   Search declarations",
        "c   Filing calendar",
        "r   Records",
        "a   AEAT Sync",
        "    Reference",
    )
    assert account == ("p   Profile", "F10 Sign out")
    if size == (120, 40):
        # Wide, the links head the side column and are on screen on arrival.
        assert "Go to" in rendered
        assert "Filing calendar" in rendered
        assert "F10 Sign out" in rendered
        assert not keys_shown
    else:
        # At the floor the side column is below the fold, so one line of keys
        # at the top names every link before the operator scrolls.
        assert keys_shown
        for label in ("d Declarations", "+ New declaration", "/ Search declarations", "c Filing calendar"):
            assert label in keys_text
        assert "r Records" in keys_text
        assert "p Profile" in keys_text
        assert "F10 Sign out" in keys_text
        assert "d Declarations" in rendered


@pytest.mark.asyncio
async def test_home_keeps_a_closed_page_listed_with_its_reason_and_promises_no_key_for_it() -> None:
    screen = HomeScreen(
        build_home_projection_fixture(HomeFixtureScenario.READY),
        link_states={
            HomeLinkV1.LEDGER: WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            HomeLinkV1.SIGN_OUT: WorkbenchDestinationAdmissionState.UNAVAILABLE,
        },
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        links = _link_rows(screen, "#home-links")
        account = _link_rows(screen, "#home-account-links")
        keys_text = str(screen.query_one("#home-link-keys", Static).render())
    assert "r   Records\n    Not read yet" in links
    assert "F10 Sign out\n    Unavailable" in account
    assert "Records" not in keys_text
    assert "Sign out" not in keys_text
    assert "a AEAT Sync" in keys_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "expected"),
    (
        ("d", HomeLinkV1.DECLARATIONS),
        ("plus", HomeLinkV1.NEW_DECLARATION),
        ("slash", HomeLinkV1.SEARCH_DECLARATIONS),
        ("c", HomeLinkV1.CALENDAR),
        ("r", HomeLinkV1.LEDGER),
        ("a", HomeLinkV1.AEAT_SYNC),
        ("p", HomeLinkV1.PROFILE),
    ),
)
async def test_each_home_key_asks_the_host_for_its_link(key: str, expected: HomeLinkV1) -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = _LinkRecordingHost(screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await pilot.press(key)
        await settle(pilot)
    assert app.links == [expected]
    assert screen.selected_target is None


@pytest.mark.asyncio
async def test_choosing_a_link_row_asks_for_it_without_moving_the_remembered_home_row() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = _LinkRecordingHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        remembered = screen.highlighted_target
        assert remembered is not None
        links = screen.query_one("#home-account-links", DataTable)
        links.focus()
        links.move_cursor(row=1)
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert screen.highlighted_target == remembered
    assert app.links == [HomeLinkV1.SIGN_OUT]


@pytest.mark.asyncio
async def test_an_empty_home_lands_on_its_links_so_the_keyboard_has_somewhere_to_go() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.EMPTY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        assert app.focused is not None and app.focused.id == "home-links"
        assert screen.query_one("#home-page", VerticalScroll).scroll_y == 0


def test_home_is_projection_only_and_does_not_import_the_dev_harness_or_application_actions() -> None:
    path = Path(__file__).parents[1] / "home.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("harness" in name or "adapters" in name or "entrypoints.cli" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "Path"} & calls

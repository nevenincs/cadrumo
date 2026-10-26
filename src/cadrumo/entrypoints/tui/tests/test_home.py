"""Focused compositor and authority-boundary proof for the production Home."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
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
        ) == (
            "View earlier calculations",
            "Classify records",
            "Review supporting documents",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected"),
    (
        (
            HomeFixtureScenario.READY,
            {
                "M130 2T": "Filed with AEAT",
                "M303 3T": "Marked as filed, not yet confirmed by AEAT",
                "M390 0A": "Filed, AEAT receipt verified",
            },
        ),
        (
            HomeFixtureScenario.BLOCKED,
            {
                "M130 2T": "Filed with AEAT",
                "M303 3T": "Not filed yet",
                "M390 0A": "Filed, accepted by AEAT",
            },
        ),
    ),
)
async def test_home_agenda_rows_carry_one_filing_status_each(
    scenario: HomeFixtureScenario, expected: dict[str, str]
) -> None:
    screen = HomeScreen(build_home_projection_fixture(scenario))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        table = cast("DataTable[str]", screen.query_one("#home-agenda", DataTable))
        rows = tuple(str(table.get_row_at(index)[0]) for index in range(table.row_count))
        evidence = screen.query_one("#home-evidence", Static)
        text = "\n".join(str(widget.render()) for widget in screen.query(Static) if widget.display)
    statuses = {row.split(" · ")[1]: row.split(" · ", 2)[2] for row in rows}
    assert statuses == expected
    assert not evidence.display
    assert "Local:" not in text
    assert "observed" not in text


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

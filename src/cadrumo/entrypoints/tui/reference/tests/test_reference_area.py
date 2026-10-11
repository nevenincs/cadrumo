"""The reference area lists every read, shows each read's whole result, and follows its rows onward."""

from __future__ import annotations

import json

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...components.widgets import DisclosureGroup
from ...installation.tests.runtime_support import until
from ...tests.frame import screen_text
from ..destination import ReferenceScreen
from ..read_screen import ReferenceReadScreen
from ..reads import ReferenceQuery, ReferenceRead, read_reference
from ..texts import filter_label, read_label
from ..views import view_of

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZE = (140, 50)


async def _answered(pilot: Pilot[None], *, after: ReferenceReadScreen | None = None) -> ReferenceReadScreen:
    """Wait for the read screen in front, other than ``after``, to hold an answer."""
    await until(
        pilot,
        lambda: (
            isinstance(pilot.app.screen, ReferenceReadScreen)
            and pilot.app.screen is not after
            and pilot.app.screen.result is not None
        ),
        seconds=40,
    )
    screen = pilot.app.screen
    assert isinstance(screen, ReferenceReadScreen)
    return screen


def _status(screen: ReferenceReadScreen) -> PinnedStatusBar:
    return screen.query_one("#reference-status", PinnedStatusBar)


def _document(screen: ReferenceReadScreen) -> object:
    result = screen.result
    assert result is not None
    return json.loads(result.model_dump_json())


@pytest.mark.asyncio
async def test_the_area_lists_every_read_and_a_row_leads_to_the_read_that_describes_it() -> None:
    area = ReferenceScreen()
    app = ScreenHostApp(area)
    async with app.run_test(size=_SIZE) as pilot:
        await until(pilot, lambda: bool(area.query("#reference-hint")))
        listing = area.query_one("#reference-reads", DataTable)
        assert [str(row.key.value) for row in listing.ordered_rows] == [read.value for read in ReferenceRead]
        painted = screen_text(app, *_SIZE)
        for read in ReferenceRead:
            assert read_label(read) in painted

        await pilot.press("enter")
        modelos = await _answered(pilot)
        expected = read_reference(ReferenceQuery(ReferenceRead.MODELOS))
        assert _document(modelos) == json.loads(expected.model_dump_json())
        table = modelos.query_one("#reference-table-0", DataTable)
        rows = view_of(ReferenceQuery(ReferenceRead.MODELOS), expected).tables[0].rows
        assert table.row_count == len(rows) > 10
        assert tuple(str(cell) for cell in table.get_row_at(0)) == rows[0]
        assert [str(column.label) for column in table.columns.values()][:3] == ["code", "title", "cadence"]

        # Enter on a modelo opens its description, asked for by the code on that row.
        await until(pilot, lambda: app.focused is table)
        await pilot.press("enter")
        described = await _answered(pilot, after=modelos)
        first_code = rows[0][0]
        assert _document(described) == json.loads(
            read_reference(ReferenceQuery(ReferenceRead.DESCRIBE, modelo=first_code)).model_dump_json()
        )
        facts = str(described.query_one("#reference-facts", Static).content)
        assert first_code in facts
        # It arrived with its coordinates, so they are folded away and still say what was asked.
        assert described.query_one("#reference-filters", DisclosureGroup).collapsed
        assert described.query_one("#reference-filter-modelo", Input).value == first_code

        # From a description, the casillas of the same modelo are one press away.
        shown_links = {button.id for button in described.query("#reference-links Button") if button.display}
        assert shown_links == {"reference-link-casillas", "reference-link-formulas", "reference-link-bindings"}
        described.query_one("#reference-link-casillas", Button).press()
        casillas = await _answered(pilot, after=described)
        assert _document(casillas) == json.loads(
            read_reference(ReferenceQuery(ReferenceRead.CASILLAS, modelo=first_code)).model_dump_json()
        )

        casillas.action_close()
        await until(pilot, lambda: app.screen is described)
        described.action_close()
        await until(pilot, lambda: app.screen is modelos)


@pytest.mark.asyncio
async def test_a_read_asks_for_its_coordinates_and_shows_what_the_reference_refuses() -> None:
    area = ReferenceScreen()
    app = ScreenHostApp(area)
    async with app.run_test(size=_SIZE) as pilot:
        await until(pilot, lambda: bool(area.query("#reference-hint")))
        area.open_read(ReferenceRead.CASILLA)
        await until(
            pilot,
            lambda: isinstance(app.screen, ReferenceReadScreen) and bool(app.screen.query("#reference-table-1")),
        )
        asking = app.screen
        assert isinstance(asking, ReferenceReadScreen)
        # Nothing is read until the read has what it cannot do without.
        assert asking.result is None and not asking.query_one("#reference-filters", DisclosureGroup).collapsed

        asking.query_one("#reference-show", Button).press()
        await until(pilot, lambda: _status(asking).tone == "error")
        assert _status(asking).message.endswith(f"{filter_label('modelo')}, {filter_label('casilla')}.")

        asking.query_one("#reference-filter-modelo", Input).value = "130"
        asking.query_one("#reference-filter-casilla", Input).value = "01"
        asking.query_one("#reference-filter-year", Input).value = "2024"
        asking.query_one("#reference-show", Button).press()
        await until(pilot, lambda: filter_label("period") in _status(asking).message)
        assert asking.result is None

        asking.query_one("#reference-filter-period", Input).value = "1T"
        asking.query_one("#reference-show", Button).press()
        answered = await _answered(pilot)
        assert answered is asking
        assert _document(asking) == json.loads(
            read_reference(
                ReferenceQuery(ReferenceRead.CASILLA, modelo="130", casilla="01", year=2024, period="1T")
            ).model_dump_json()
        )

        asking.query_one("#reference-filter-modelo", Input).value = "600"
        asking.query_one("#reference-show", Button).press()
        await until(pilot, lambda: asking.result is None and _status(asking).tone == "error")
        # The ceded-tax redirect the command prints, not a bare "not found".
        assert "600" in _status(asking).message
        assert str(asking.query_one("#reference-facts", Static).content) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "read",
    [
        ReferenceRead.SUPPORT_MATRIX,
        ReferenceRead.CATEGORIES,
        ReferenceRead.PORTALS,
        ReferenceRead.AUTH_PROVIDERS,
        ReferenceRead.APODERADO_SCOPES,
    ],
)
async def test_a_read_with_no_required_coordinate_answers_as_soon_as_it_opens(read: ReferenceRead) -> None:
    area = ReferenceScreen()
    app = ScreenHostApp(area)
    async with app.run_test(size=_SIZE) as pilot:
        await until(pilot, lambda: bool(area.query("#reference-hint")))
        area.open_read(read)
        screen = await _answered(pilot)

        expected = read_reference(ReferenceQuery(read))
        assert _document(screen) == json.loads(expected.model_dump_json())
        view = view_of(ReferenceQuery(read), expected)
        for slot, shown in enumerate(view.tables):
            table = screen.query_one(f"#reference-table-{slot}", DataTable)
            assert table.display and table.row_count == len(shown.rows)
            assert [str(column.label) for column in table.columns.values()] == list(shown.columns)
        assert _status(screen).tone == "success"


@pytest.mark.asyncio
async def test_a_portal_row_opens_the_portal_with_the_address_its_command_prints() -> None:
    portals = ReferenceReadScreen(ReferenceQuery(ReferenceRead.PORTALS, category="auth"))
    app = ScreenHostApp(portals)
    async with app.run_test(size=_SIZE) as pilot:
        await _answered(pilot)
        table = portals.query_one("#reference-table-0", DataTable)
        await until(pilot, lambda: app.focused is table)
        await pilot.press("enter")
        portal = await _answered(pilot, after=portals)

        document = _document(portal)
        assert isinstance(document, dict)
        assert document["portal"] == str(table.get_row_at(0)[0])
        # The command prints a portal's address without its path, and so does this.
        assert document["url"] == f"https://{document['subdomain']}"
        assert f"url            {document['url']}" in str(portal.query_one("#reference-facts", Static).content)

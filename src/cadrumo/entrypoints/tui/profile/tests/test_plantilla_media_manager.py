"""The profile manager declares, replaces and withdraws average-workforce years.

The doors here are observable fakes of the shared application service: they
record exactly what the page asked for and hand back a page projected from
what they now hold. The service's own storage and validation behaviour is
proven against the real encrypted record by its own tests; this file proves
that the manager parses the dialog into typed values, sends them to the right
door, repaints from the answer, and shows a refusal instead of a success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, OptionList, Static

from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.i18n.render import tr
from .....domain.user_profile.errors import ProfileSchemaValidationError, UserProfileValidationError
from .....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...tests.manager_pilot import wait_until_settled
from ..overview import ProfileManagerScreen
from ..plantilla_media import PlantillaMediaScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (120, 60)
_PROFILE = "00000000-0000-4000-8000-0000000000c3"
_DIALOG_OPEN_LIMIT = 200


@dataclass
class _FakePlantillaMediaDoors:
    """Holds declared years like the service does and records every call."""

    years: dict[int, PlantillaMediaYear] = field(default_factory=dict)
    revision: int = 3
    calls: list[tuple[str, object]] = field(default_factory=list)

    def overview(self) -> ProfileOverview:
        declared = sorted(self.years.values(), key=lambda item: item.year)
        instance_rows = tuple(
            ProfileFieldView(
                path=f"irpf.plantilla_media.{index}.{leaf}",
                label=f"Average workforce by calendar year ({leaf})",
                value=value,
                masked=False,
                required=False,
                row_index=str(index),
            )
            for index, item in enumerate(declared)
            for leaf, value in (
                ("year", str(item.year)),
                ("average_workforce", str(item.average_workforce)),
                ("state", item.state.value),
            )
        )
        regime = ProfileFieldView(
            path="irpf.special_regime",
            label="Special regime",
            value=None,
            masked=False,
            required=False,
        )
        return ProfileOverview(
            profile_id=_PROFILE,
            record_revision=self.revision,
            content_digest=f"{self.revision:064x}",
            label="Synthetic profile",
            setup_state=ProfileSetupState.INCOMPLETE,
            sections=(ProfileSectionView(key="irpf", title="IRPF", repeatable=False, fields=(regime, *instance_rows)),),
        )

    def list_years(self) -> tuple[PlantillaMediaYear, ...]:
        self.calls.append(("list", None))
        return tuple(sorted(self.years.values(), key=lambda item: item.year))

    def set_year(self, year: int, average_workforce: Decimal, state: PlantillaMediaState) -> ProfileOverview:
        self.calls.append(("set", (year, average_workforce, state)))
        exponent = average_workforce.as_tuple().exponent
        if average_workforce < 0 or not isinstance(exponent, int) or exponent < -2:
            raise ProfileSchemaValidationError(context={"path": "irpf.plantilla_media.0.average_workforce"})
        self.years[year] = PlantillaMediaYear(year=year, average_workforce=average_workforce, state=state)
        self.revision += 1
        return self.overview()

    def remove_year(self, year: int) -> ProfileOverview:
        self.calls.append(("remove", year))
        if year not in self.years:
            raise UserProfileValidationError(f"the average workforce of {year} is not declared")
        del self.years[year]
        self.revision += 1
        return self.overview()


def _screen(doors: _FakePlantillaMediaDoors) -> ProfileManagerScreen:
    def unreachable_persist(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
        raise AssertionError("a year is written through its own door, never the scalar field door")

    return ProfileManagerScreen(
        doors.overview(),
        persist=unreachable_persist,
        list_plantilla_media=doors.list_years,
        set_plantilla_media=doors.set_year,
        remove_plantilla_media=doors.remove_year,
    )


async def _open_dialog(screen: ProfileManagerScreen, pilot: Pilot[None]) -> PlantillaMediaScreen:
    """Press the section's button and wait for the listing read to open the dialog."""
    screen.query_one("#manager-plantilla-media", Button).press()
    for _ in range(_DIALOG_OPEN_LIMIT):
        await pilot.pause()
        dialog = pilot.app.screen
        if isinstance(dialog, PlantillaMediaScreen) and screen._pending_listing is None:
            await pilot.pause()
            return dialog
    raise AssertionError("the average-workforce dialog never opened")


def _fill(
    dialog: PlantillaMediaScreen,
    *,
    year: str,
    average_workforce: str = "",
    state: PlantillaMediaState | None = None,
) -> None:
    dialog.query_one("#plantilla-year", Input).value = year
    dialog.query_one("#plantilla-workforce", Input).value = average_workforce
    dialog.query_one("#plantilla-state", OptionList).highlighted = (
        None if state is None else tuple(PlantillaMediaState).index(state)
    )


def _declared_prompts(dialog: PlantillaMediaScreen) -> list[str]:
    if not dialog.query("#plantilla-declared"):
        return []
    options = dialog.query_one("#plantilla-declared", OptionList)
    return [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]


def _rendered_values(screen: ProfileManagerScreen) -> dict[str, str]:
    table: DataTable[str] = screen._table_by_section["irpf"]
    return {str(row_key.value): str(table.get_row(row_key)[2]) for row_key in table.rows}


def _status(screen: ProfileManagerScreen) -> PinnedStatusBar:
    return screen.query_one("#manager-status", PinnedStatusBar)


@pytest.mark.asyncio
async def test_a_year_is_declared_replaced_and_withdrawn_and_the_page_follows_storage() -> None:
    """Each answer reaches its door as typed values and the page repaints from the result."""
    doors = _FakePlantillaMediaDoors()
    screen = _screen(doors)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()

        dialog = await _open_dialog(screen, pilot)
        assert _declared_prompts(dialog) == []
        _fill(dialog, year="2024", average_workforce="12.50", state=PlantillaMediaState.OBSERVED)
        dialog.query_one("#btn-plantilla-save", Button).press()
        await wait_until_settled(screen, pilot)

        assert doors.calls[-1] == ("set", (2024, Decimal("12.50"), PlantillaMediaState.OBSERVED))
        assert isinstance(doors.calls[-1][1], tuple)
        assert isinstance(doors.calls[-1][1][1], Decimal)
        assert screen.overview.record_revision == 4
        assert _rendered_values(screen)["irpf.plantilla_media.0.average_workforce"] == "12.50"
        assert _status(screen).tone == "success"
        assert _status(screen).message == tr("flows.manager.edit.saved")

        dialog = await _open_dialog(screen, pilot)
        prompts = _declared_prompts(dialog)
        assert len(prompts) == 1
        assert "2024" in prompts[0]
        assert "12.50" in prompts[0]
        _fill(dialog, year="2024", average_workforce="13", state=PlantillaMediaState.COMMITTED)
        dialog.query_one("#btn-plantilla-save", Button).press()
        await wait_until_settled(screen, pilot)

        assert doors.calls[-1] == ("set", (2024, Decimal(13), PlantillaMediaState.COMMITTED))
        assert list(doors.years) == [2024]
        rendered = _rendered_values(screen)
        assert rendered["irpf.plantilla_media.0.average_workforce"] == "13"
        assert rendered["irpf.plantilla_media.0.state"] == "committed"
        assert screen.overview.record_revision == 5

        dialog = await _open_dialog(screen, pilot)
        _fill(dialog, year="2024")
        dialog.query_one("#btn-plantilla-remove", Button).press()
        await wait_until_settled(screen, pilot)

        assert doors.calls[-1] == ("remove", 2024)
        assert doors.years == {}
        assert not any(path.startswith("irpf.plantilla_media.") for path in _rendered_values(screen))
        assert screen.overview.record_revision == 6
        assert _status(screen).tone == "success"

        dialog = await _open_dialog(screen, pilot)
        assert _declared_prompts(dialog) == []
        dialog.query_one("#btn-plantilla-cancel", Button).press()
        await pilot.pause()
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_declared_year_selected_in_the_listing_fills_the_dialog() -> None:
    """Replacing a year starts from what the profile holds for it."""
    doors = _FakePlantillaMediaDoors(
        years={
            2023: PlantillaMediaYear(year=2023, average_workforce=Decimal("7.25"), state=PlantillaMediaState.OBSERVED),
            2025: PlantillaMediaYear(year=2025, average_workforce=Decimal(9), state=PlantillaMediaState.COMMITTED),
        }
    )
    screen = _screen(doors)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        dialog = await _open_dialog(screen, pilot)
        assert len(_declared_prompts(dialog)) == 2

        dialog.query_one("#plantilla-declared", OptionList).highlighted = 1
        await pilot.pause()

        assert dialog.query_one("#plantilla-year", Input).value == "2025"
        assert dialog.query_one("#plantilla-workforce", Input).value == "9"
        assert dialog.query_one("#plantilla-state", OptionList).highlighted == tuple(PlantillaMediaState).index(
            PlantillaMediaState.COMMITTED
        )
        dialog.query_one("#btn-plantilla-cancel", Button).press()
        await pilot.pause()
        assert [name for name, _ in doors.calls] == ["list"]
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_value_the_service_refuses_is_shown_and_the_page_is_not_repainted() -> None:
    """A third decimal place reaches the service unrounded and its refusal stays visible."""
    doors = _FakePlantillaMediaDoors()
    screen = _screen(doors)
    opened = screen.overview
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        dialog = await _open_dialog(screen, pilot)
        _fill(dialog, year="2024", average_workforce="12.505", state=PlantillaMediaState.OBSERVED)
        dialog.query_one("#btn-plantilla-save", Button).press()
        await wait_until_settled(screen, pilot)

        assert doors.calls[-1] == ("set", (2024, Decimal("12.505"), PlantillaMediaState.OBSERVED))
        assert doors.years == {}
        assert screen.overview == opened
        assert _status(screen).tone == "error"
        assert _status(screen).message
        assert _status(screen).message != tr("flows.manager.edit.saved")
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_withdrawing_an_undeclared_year_is_refused_without_a_success() -> None:
    """The service decides a year is not declared; the page reports its refusal."""
    doors = _FakePlantillaMediaDoors()
    screen = _screen(doors)
    opened = screen.overview
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        dialog = await _open_dialog(screen, pilot)
        _fill(dialog, year="2019")
        dialog.query_one("#btn-plantilla-remove", Button).press()
        await wait_until_settled(screen, pilot)

        assert doors.calls[-1] == ("remove", 2019)
        assert screen.overview == opened
        assert _status(screen).tone == "error"
        assert "2019" in _status(screen).message
        pilot.app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("year", "average_workforce", "state", "refusal_key"),
    [
        ("20x4", "3", PlantillaMediaState.OBSERVED, "flows.manager.plantilla_media.year_not_whole"),
        ("-2024", "3", PlantillaMediaState.OBSERVED, "flows.manager.plantilla_media.year_not_whole"),
        ("2024", "three", PlantillaMediaState.OBSERVED, "flows.manager.plantilla_media.workforce_not_number"),
        ("2024", "NaN", PlantillaMediaState.OBSERVED, "flows.manager.plantilla_media.workforce_not_number"),
        ("2024", "3", None, "flows.manager.plantilla_media.state_required"),
    ],
)
async def test_an_unparseable_answer_is_refused_in_the_dialog_and_no_write_starts(
    year: str,
    average_workforce: str,
    state: PlantillaMediaState | None,
    refusal_key: str,
) -> None:
    """Text that is not a year, a number or a chosen state never reaches a door."""
    doors = _FakePlantillaMediaDoors()
    screen = _screen(doors)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        dialog = await _open_dialog(screen, pilot)
        _fill(dialog, year=year, average_workforce=average_workforce, state=state)
        dialog.query_one("#btn-plantilla-save", Button).press()
        await pilot.pause()

        assert pilot.app.screen is dialog
        assert str(dialog.query_one("#plantilla-refusal", Static).render()) == tr(refusal_key)
        assert [name for name, _ in doors.calls] == ["list"]
        assert screen._pending_write is None
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_the_section_offers_no_dialog_when_the_host_wires_no_doors() -> None:
    """A host without the doors shows no button that could only refuse."""
    doors = _FakePlantillaMediaDoors()

    def unreachable_persist(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
        raise AssertionError("no write is expected")

    screen = ProfileManagerScreen(doors.overview(), persist=unreachable_persist)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert not screen.query("#manager-plantilla-media")
        pilot.app.exit(None)

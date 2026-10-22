"""The prorrata register screen over the registered operations' own request and projection models."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.operations.public_scalar import PublicDecimal
from .....application.prorrata_register.operation_requests import (
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from .....application.prorrata_register.projection_contracts import (
    ProrrataFindingProjection,
    ProrrataRefusalProjection,
    ProrrataSectorDefinitionProjection,
)
from .....core.config import override_settings
from .....core.i18n.render import tr
from ..controller import LedgerWorkspaceController
from ..registers_presentation import REGISTER_PAGE_SIZE
from ..registers_prorrata import (
    PRORRATA_TOOL_KEY,
    LedgerProrrataRegisterDoorV1,
    LedgerProrrataRegisterScreen,
    prorrata_entry_key,
    prorrata_refusal_text,
    prorrata_register_tool,
)
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import REGISTERS_PROFILE_ID, MemoryProrrataRegisterDoor, synthetic_prorrata_entry
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(door: MemoryProrrataRegisterDoor) -> LedgerProrrataRegisterScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerProrrataRegisterScreen(controller, cast(LedgerProrrataRegisterDoorV1, door))


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: LedgerProrrataRegisterScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


def _text(screen: LedgerProrrataRegisterScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerProrrataRegisterScreen, table_id: str) -> list[str]:
    table = screen.query_one(f"#{table_id}", DataTable)
    return [str(row.key.value) for row in table.ordered_rows]


async def _choose_action(pilot: Pilot[None], screen: LedgerProrrataRegisterScreen, action: str) -> None:
    cast("Select[str]", screen.query_one("#prorrata-action", Select)).value = action
    await pilot.pause()


def _fill(screen: LedgerProrrataRegisterScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#prorrata-{name.replace('_', '-')}", Input).value = value


@pytest.mark.asyncio
async def test_the_register_lists_entries_and_a_confirmed_election_shows_in_the_refreshed_register() -> None:
    door = MemoryProrrataRegisterDoor(
        entries=(synthetic_prorrata_entry(2024), synthetic_prorrata_entry(2025, sector_id="S1")),
        sectors=(ProrrataSectorDefinitionProjection(sector_id="S1", letra="a", member_activity_codes=("A01",)),),
    )
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            assert door.requests == [ProrrataListRequest(profile_id=REGISTERS_PROFILE_ID)]
            assert _keys(screen, "prorrata-entries") == ["2024|", "2025|S1"]
            assert _keys(screen, "prorrata-sectors") == ["S1"]
            assert _text(screen, "#ledger-flow-status") == ""

            await _choose_action(pilot, screen, "elect_general")
            _fill(screen, ejercicio="2026", percentage="82", provenance="synthetic_operator_estimate")
            await _press(pilot, screen, "register-review")
            staged = _text(screen, "#register-staged")
            assert screen.staged == ProrrataElectGeneralRequest(
                profile_id=REGISTERS_PROFILE_ID,
                ejercicio=2026,
                percentage=PublicDecimal(decimal="82"),
                provenance="synthetic_operator_estimate",
            )
            assert "82" in staged
            assert screen.query_one("#register-decision").display
            assert len(door.requests) == 1

            await _press(pilot, screen, "register-confirm")
            assert isinstance(door.requests[1], ProrrataElectGeneralRequest)
            assert isinstance(door.requests[2], ProrrataListRequest)
            assert _keys(screen, "prorrata-entries") == ["2024|", "2025|S1", "2026|"]
            table = screen.query_one("#prorrata-entries", DataTable)
            assert table.get_row_at(2)[3] == "82"
            assert str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value) == "2026|"
            assert tr("tui.ledger.registers.prorrata.done.elect_general") in _text(screen, "#register-result")
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.records.saved")
            assert screen.staged is None
            assert not screen.query_one("#register-decision").display


@pytest.mark.asyncio
async def test_an_election_the_register_refuses_shows_its_registered_refusal_and_stays_staged() -> None:
    door = MemoryProrrataRegisterDoor(entries=(synthetic_prorrata_entry(2025),))
    door.refusal = ProrrataRefusalProjection(
        code="REFUSED_PRORRATA_ELECTION",
        reason="provenance_required",
        detail="synthetic: a provisional provenance is required",
        ejercicio=2026,
        accepted_provenances=("synthetic_a", "synthetic_b"),
    )
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            await _choose_action(pilot, screen, "elect_especial")
            _fill(screen, ejercicio="2026", percentage="60")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            refusal = _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.registers.prorrata.refusal.provenance_required") in refusal
            assert "synthetic: a provisional provenance is required" in refusal
            accepted = tr("tui.ledger.registers.prorrata.accepted_provenances", values="synthetic_a, synthetic_b")
            assert accepted in refusal
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.records.failed")
            assert isinstance(screen.staged, ProrrataElectEspecialRequest)
            assert not screen.query_one("#register-confirm", Button).disabled
            # Nothing was applied, so the register is not re-read.
            assert [type(request) for request in door.requests] == [ProrrataListRequest, ProrrataElectEspecialRequest]
            assert _keys(screen, "prorrata-entries") == ["2025|"]

            await _press(pilot, screen, "register-cancel")
            assert screen.staged is None
            assert not screen.query_one("#register-decision").display
            assert not screen.query_one("#prorrata-percentage", Input).disabled


@pytest.mark.asyncio
async def test_seed_findings_and_source_are_shown_as_the_operation_reported_them() -> None:
    door = MemoryProrrataRegisterDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.registers.prorrata.empty")
            assert _keys(screen, "prorrata-entries") == []
            await _choose_action(pilot, screen, "seed")
            assert screen.query_one("#prorrata-ejercicio-field").display
            assert not screen.query_one("#prorrata-percentage-field").display
            _fill(screen, ejercicio="2026")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            assert door.requests[1] == ProrrataSeedRequest(profile_id=REGISTERS_PROFILE_ID, ejercicio=2026)
            result = _text(screen, "#register-result")
            assert tr("tui.ledger.registers.prorrata.done.seed") in result
            expected_source = tr(
                "tui.ledger.registers.prorrata.result.seed_source", modelo="303", year=2025, period="4T"
            )
            assert expected_source in result
            assert screen.query_one("#prorrata-entries", DataTable).get_row_at(0)[3] == "87.25"


@pytest.mark.parametrize(
    ("action", "values", "expected"),
    [
        (
            "declare_sector",
            {"sector": "S2", "letra": "b", "activities": "A01, A02"},
            ProrrataDeclareSectorRequest(
                profile_id=REGISTERS_PROFILE_ID, sector_id="S2", letra="b", member_activity_codes=("A01", "A02")
            ),
        ),
        (
            "revoke_especial",
            {"ejercicio": "2026", "percentage": "60", "evidence": "EV-1"},
            ProrrataRevokeEspecialRequest(
                profile_id=REGISTERS_PROFILE_ID,
                ejercicio=2026,
                percentage=PublicDecimal(decimal="60"),
                evidence_reference="EV-1",
            ),
        ),
        (
            "seed_sector",
            {"ejercicio": "2026", "sector": "S1"},
            ProrrataSeedSectorRequest(profile_id=REGISTERS_PROFILE_ID, ejercicio=2026, sector_id="S1"),
        ),
        (
            "settle_sector",
            {"ejercicio": "2026", "sector": "S1", "con_derecho": "7500.00", "sin_derecho": "2500"},
            ProrrataSettleSectorRequest(
                profile_id=REGISTERS_PROFILE_ID,
                ejercicio=2026,
                sector_id="S1",
                con_derecho_volume=PublicDecimal(decimal="7500.00"),
                sin_derecho_volume=PublicDecimal(decimal="2500"),
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_each_change_submits_its_own_typed_request(action: str, values: dict[str, str], expected: object) -> None:
    door = MemoryProrrataRegisterDoor(settled_definitive="75")
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            await _choose_action(pilot, screen, action)
            _fill(screen, **values)
            await _press(pilot, screen, "register-review")
            assert screen.staged == expected, _text(screen, "#ledger-refusal")
            await _press(pilot, screen, "register-confirm")
            assert door.requests[1] == expected
            assert tr(f"tui.ledger.registers.prorrata.done.{action}") in _text(screen, "#register-result")
            if action == "settle_sector":
                # The definitive figure is the operation's own, shown unchanged.
                assert screen.query_one("#prorrata-entries", DataTable).get_row_at(0)[4] == "75"
            if action == "declare_sector":
                assert _keys(screen, "prorrata-sectors") == ["S2"]


@pytest.mark.parametrize(
    ("action", "values", "message"),
    [
        (
            "elect_general",
            {"ejercicio": "2026", "percentage": "1.000,5"},
            ("tui.ledger.registers.invalid_decimal", "percentage", "1.000,5"),
        ),
        (
            "elect_general",
            {"ejercicio": "20x6", "percentage": "80"},
            ("tui.ledger.registers.invalid_number", "ejercicio", "20x6"),
        ),
        (
            "revoke_especial",
            {"ejercicio": "2026", "percentage": "60"},
            ("tui.ledger.registers.required", "evidence_reference", ""),
        ),
        ("declare_sector", {"letra": "a"}, ("tui.ledger.registers.required", "sector_id", "")),
    ],
)
@pytest.mark.asyncio
async def test_an_incomplete_or_ambiguous_form_is_refused_before_anything_is_sent(
    action: str, values: dict[str, str], message: tuple[str, str, str]
) -> None:
    door = MemoryProrrataRegisterDoor()
    screen = _screen(door)
    key, field, value = message
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            await _choose_action(pilot, screen, action)
            _fill(screen, **values)
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            field_name = tr(f"tui.ledger.registers.prorrata.field.{field}")
            assert _text(screen, "#ledger-refusal") == tr(key, field=field_name, value=value)
            assert [type(request) for request in door.requests] == [ProrrataListRequest]


@pytest.mark.asyncio
async def test_choosing_an_entry_prefills_the_election_from_it() -> None:
    entry = synthetic_prorrata_entry(2025, sector_id="S1", provisional="64.5")
    door = MemoryProrrataRegisterDoor(entries=(entry,))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            table = screen.query_one("#prorrata-entries", DataTable)
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await _settle(pilot)
            assert screen.selected_key == prorrata_entry_key(2025, "S1")
            assert screen.query_one("#prorrata-ejercicio", Input).value == "2025"
            assert screen.query_one("#prorrata-sector", Input).value == "S1"
            assert screen.query_one("#prorrata-percentage", Input).value == "64.5"
            assert _text(screen, "#register-detail") == tr(
                "tui.ledger.registers.prorrata.result.entry",
                ejercicio=2025,
                sector="S1",
                regime="general",
                provisional="64.5",
                definitive="-",
            )


@pytest.mark.asyncio
async def test_the_register_holds_one_page_of_a_thousand_entries_and_pages_both_ways() -> None:
    entries = tuple(synthetic_prorrata_entry(2000, sector_id=f"S{index:04d}") for index in range(1050))
    door = MemoryProrrataRegisterDoor(entries=entries)
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            table = screen.query_one("#prorrata-entries", DataTable)
            assert REGISTER_PAGE_SIZE <= 200
            assert table.row_count == REGISTER_PAGE_SIZE
            assert _keys(screen, "prorrata-entries")[0] == "2000|S0000"
            assert screen.query_one("#prorrata-entries-previous", Button).disabled
            await _press(pilot, screen, "prorrata-entries-next")
            assert _keys(screen, "prorrata-entries")[0] == f"2000|S{REGISTER_PAGE_SIZE:04d}"
            assert table.row_count == REGISTER_PAGE_SIZE
            for _ in range(20):
                if screen.query_one("#prorrata-entries-next", Button).disabled:
                    break
                await _press(pilot, screen, "prorrata-entries-next")
            assert table.row_count == 1050 % REGISTER_PAGE_SIZE
            assert _keys(screen, "prorrata-entries")[-1] == "2000|S1049"
            assert screen.query_one("#prorrata-entries-next", Button).disabled
            await _press(pilot, screen, "prorrata-entries-previous")
            assert table.row_count == REGISTER_PAGE_SIZE
            expected_page = tr("tui.ledger.registers.page", page=10, pages=11, total=1050)
            assert _text(screen, "#prorrata-entries-page") == expected_page


@pytest.mark.asyncio
async def test_the_screen_discards_register_facts_when_the_session_is_lost() -> None:
    door = MemoryProrrataRegisterDoor(entries=(synthetic_prorrata_entry(2025),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            _fill(screen, ejercicio="2026", percentage="80")
            await _press(pilot, screen, "register-review")
            door.expired = True
            await _press(pilot, screen, "register-confirm")
            assert screen.entries == ()
            assert screen.staged is None
            assert screen.query_one("#prorrata-entries", DataTable).row_count == 0
            assert screen.query_one("#prorrata-percentage", Input).value == ""


def test_the_tool_attaches_to_the_overview_and_builds_the_register_screen() -> None:
    door = MemoryProrrataRegisterDoor()
    tool = prorrata_register_tool(cast(LedgerProrrataRegisterDoorV1, door))
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=(tool,)),
    )
    assert tool.key == PRORRATA_TOOL_KEY
    assert controller.tools_for(tool.area) == (tool,)
    assert isinstance(tool.build(controller), LedgerProrrataRegisterScreen)


def test_a_seed_refusal_lists_only_its_blocking_findings() -> None:
    def finding(code: str, *, blocking: bool) -> ProrrataFindingProjection:
        return ProrrataFindingProjection(
            code=code,
            blocking=blocking,
            message=f"synthetic {code}",
            source_modelo="303",
            source_filing_year=2025,
            source_period="4T",
            stamped_revision_id="synthetic-revision",
            selected_revision_id=None,
        )

    text = prorrata_refusal_text(
        ProrrataRefusalProjection(
            code="REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
            reason="seed_source_blocked",
            detail="synthetic detail",
            findings=(finding("BLOCK", blocking=True), finding("NOTE", blocking=False)),
        )
    )
    assert tr("tui.ledger.registers.prorrata.refusal.seed_source_blocked") in text
    assert "[BLOCK] synthetic BLOCK" in text
    assert "NOTE" not in text

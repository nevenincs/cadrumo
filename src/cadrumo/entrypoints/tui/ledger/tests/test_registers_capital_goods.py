"""The capital-goods register screen over the registered operations' own request and projection models."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from .....application.operations.public_scalar import PublicDecimal
from .....core.config import override_settings
from .....core.i18n.render import tr
from ..controller import LedgerWorkspaceController
from ..registers_capital_goods import (
    CAPITAL_GOODS_TOOL_KEY,
    LedgerCapitalGoodsDoorV1,
    LedgerCapitalGoodsScreen,
    capital_goods_tool,
)
from ..registers_presentation import REGISTER_PAGE_SIZE
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import REGISTERS_PROFILE_ID, MemoryCapitalGoodsDoor, synthetic_capital_good
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(door: MemoryCapitalGoodsDoor) -> LedgerCapitalGoodsScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerCapitalGoodsScreen(controller, cast(LedgerCapitalGoodsDoorV1, door))


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: LedgerCapitalGoodsScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


def _text(screen: LedgerCapitalGoodsScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerCapitalGoodsScreen) -> list[str]:
    return [str(row.key.value) for row in screen.query_one("#capital-goods", DataTable).ordered_rows]


def _fill(screen: LedgerCapitalGoodsScreen, identifier: str = "BI-02", year: str = "2025") -> None:
    for selector, value in (
        ("#capital-identifier", identifier),
        ("#capital-description", "Synthetic delivery van"),
        ("#capital-year", year),
        ("#capital-ledger-id", "tx-synthetic-02"),
        ("#capital-cuota", "4200.00"),
        ("#capital-prorrata", "80"),
        ("#capital-kind", "synthetic_kind"),
    ):
        screen.query_one(selector, Input).value = value


@pytest.mark.asyncio
async def test_a_declared_capital_good_round_trips_into_the_listed_register() -> None:
    door = MemoryCapitalGoodsDoor(records=(synthetic_capital_good("BI-01"),), deduction="3360.00")
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            assert door.requests == [BienesInversionListRequest(profile_id=REGISTERS_PROFILE_ID)]
            assert _keys(screen) == ["BI-01"]

            _fill(screen)
            cast("Select[str]", screen.query_one("#capital-art108", Select)).value = "no"
            await _press(pilot, screen, "register-review")
            expected = BienesInversionDeclareRequest(
                profile_id=REGISTERS_PROFILE_ID,
                identifier="BI-02",
                description="Synthetic delivery van",
                acquisition_year=2025,
                acquisition_ledger_id="tx-synthetic-02",
                cuota_soportada=PublicDecimal(decimal="4200.00"),
                prorrata_inicial_pct=PublicDecimal(decimal="80"),
                kind="synthetic_kind",
                art108_elegible=False,
            )
            assert screen.staged == expected, _text(screen, "#ledger-refusal")
            assert "4200.00" in _text(screen, "#register-staged")

            await _press(pilot, screen, "register-confirm")
            assert door.requests[1] == expected
            assert isinstance(door.requests[2], BienesInversionListRequest)
            assert _keys(screen) == ["BI-01", "BI-02"]
            table = screen.query_one("#capital-goods", DataTable)
            # The deduction is the one the operation reported, never one the screen derived.
            assert table.get_row_at(1)[4] == "3360.00"
            assert str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value) == "BI-02"
            assert tr("tui.ledger.registers.capital_goods.declared", count=2) in _text(screen, "#register-result")


@pytest.mark.asyncio
async def test_a_duplicate_identifier_shows_the_registered_refusal() -> None:
    door = MemoryCapitalGoodsDoor(records=(synthetic_capital_good("BI-01"),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            _fill(screen, identifier="BI-01")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            refusal = _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.registers.capital_goods.refusal.duplicate_identifier") in refusal
            assert tr("tui.ledger.registers.capital_goods.refusal_identifier", identifier="BI-01") in refusal
            assert isinstance(screen.staged, BienesInversionDeclareRequest)
            assert len(door.records) == 1


@pytest.mark.asyncio
async def test_an_out_of_range_year_is_refused_by_the_request_model_before_anything_is_sent() -> None:
    door = MemoryCapitalGoodsDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.registers.capital_goods.empty")
            _fill(screen, year="2100")
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal")
            assert door.requests == [BienesInversionListRequest(profile_id=REGISTERS_PROFILE_ID)]


@pytest.mark.asyncio
async def test_choosing_a_good_shows_its_reported_detail() -> None:
    record = synthetic_capital_good("BI-01")
    door = MemoryCapitalGoodsDoor(records=(record,))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            table = screen.query_one("#capital-goods", DataTable)
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await _settle(pilot)
            assert screen.selected_key == "BI-01"
            assert _text(screen, "#register-detail") == tr(
                "tui.ledger.registers.capital_goods.detail",
                identifier="BI-01",
                description=record.description,
                year=2024,
                kind="synthetic_kind",
                cuota="2100.00",
                prorrata="80",
                deduction="1680.00",
                ledger="tx-BI-01",
                disposal="-",
            )


@pytest.mark.asyncio
async def test_the_register_holds_one_page_of_a_thousand_goods_and_pages_both_ways() -> None:
    door = MemoryCapitalGoodsDoor(records=tuple(synthetic_capital_good(f"BI-{index:04d}") for index in range(1001)))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            table = screen.query_one("#capital-goods", DataTable)
            assert table.row_count == REGISTER_PAGE_SIZE
            await _press(pilot, screen, "capital-goods-next")
            assert _keys(screen)[0] == f"BI-{REGISTER_PAGE_SIZE:04d}"
            await _press(pilot, screen, "capital-goods-previous")
            assert _keys(screen)[0] == "BI-0000"


def test_the_capital_goods_tool_attaches_to_the_overview() -> None:
    tool = capital_goods_tool(cast(LedgerCapitalGoodsDoorV1, MemoryCapitalGoodsDoor()))
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=(tool,)),
    )
    assert tool.key == CAPITAL_GOODS_TOOL_KEY
    assert isinstance(tool.build(controller), LedgerCapitalGoodsScreen)

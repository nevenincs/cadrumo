"""Browse entries over the real ``ledger.*`` request and result models.

The doors answer from an in-memory ledger with the operations' own
projections, so the page window, lifecycle and history validators check every
answer the screen renders.
"""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from .....application.ledger.history_operation import LedgerHistoryRequest
from .....application.ledger.list_operation import LedgerListRequest
from .....application.ledger.merge_operation import LedgerMergeRequest
from .....application.ledger.remove_operation import LedgerRemoveRequest
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...components.dialogs import ConfirmScreen
from ...tests.settling import settle
from ..entries_browse import BROWSE_PAGE_SIZE, LedgerBrowseStateV1, LedgerEntriesBrowseScreen
from ..entries_common import entry_label, joined
from ..entries_trace import LedgerEntryTraceScreen
from .entries_door_fixtures import (
    ENTRIES_PROFILE_ID,
    ENTRIES_REFUSAL_KEY,
    MemoryEntriesLedger,
    entries_controller,
    entry_id,
    lifecycle_requests,
)
from .workspace_fixtures import WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(ledger: MemoryEntriesLedger, state: LedgerBrowseStateV1 | None = None) -> LedgerEntriesBrowseScreen:
    return LedgerEntriesBrowseScreen(entries_controller(), ledger.doors(), state=state)


async def _press(pilot: Pilot[None], screen: LedgerEntriesBrowseScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


async def _choose(pilot: Pilot[None], screen: LedgerEntriesBrowseScreen, row: int) -> None:
    table = screen.query_one("#entries-browse", DataTable)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


async def _answer(pilot: Pilot[None], *, accept: bool) -> str:
    dialog = pilot.app.screen
    assert isinstance(dialog, ConfirmScreen)
    message = str(dialog.query_one("#confirm-message", Static).render())
    dialog.query_one("#btn-confirm-accept" if accept else "#btn-confirm-cancel", Button).press()
    await settle(pilot)
    return message


def _text(screen: LedgerEntriesBrowseScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerEntriesBrowseScreen) -> list[str]:
    table = cast("DataTable[str]", screen.query_one("#entries-browse", DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


def _list_requests(ledger: MemoryEntriesLedger) -> list[LedgerListRequest]:
    return [cast(LedgerListRequest, request) for request in ledger.requested("list")]


@pytest.mark.asyncio
async def test_a_thousand_entries_show_one_page_and_page_forward_and_back() -> None:
    ledger = MemoryEntriesLedger.with_entries(1000)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert screen.page is not None
            assert len(screen.page.rows) == BROWSE_PAGE_SIZE
            assert _keys(screen) == [entry_id(index) for index in range(BROWSE_PAGE_SIZE)]
            assert _text(screen, "#entries-browse-window") == tr(
                "tui.ledger.entry_tools.browse.window", first=1, last=200, total=1000
            )
            assert screen.query_one("#entries-browse-previous", Button).disabled

            await _press(pilot, screen, "entries-browse-next")
            assert _keys(screen)[0] == entry_id(200)
            assert len(_keys(screen)) == BROWSE_PAGE_SIZE
            await _press(pilot, screen, "entries-browse-previous")
            assert _keys(screen)[0] == entry_id(0)

    requests = _list_requests(ledger)
    assert [request.offset for request in requests] == [0, 200, 0]
    assert all(request.limit == BROWSE_PAGE_SIZE for request in requests)


@pytest.mark.asyncio
async def test_the_last_page_holds_the_remainder_and_offers_no_next_page() -> None:
    ledger = MemoryEntriesLedger.with_entries(1000)
    screen = _screen(
        ledger,
        LedgerBrowseStateV1(
            request=LedgerListRequest(profile_id=ENTRIES_PROFILE_ID, limit=BROWSE_PAGE_SIZE, offset=800)
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert _keys(screen)[-1] == entry_id(999)
            assert screen.query_one("#entries-browse-next", Button).disabled
            assert not screen.query_one("#entries-browse-previous", Button).disabled


@pytest.mark.asyncio
async def test_an_empty_ledger_says_so_and_offers_no_action() -> None:
    ledger = MemoryEntriesLedger()
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert _keys(screen) == []
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.entry_tools.browse.empty")
            assert screen.query_one("#entries-browse-archive", Button).disabled
            assert screen.query_one("#entries-browse-merge", Button).disabled


@pytest.mark.asyncio
async def test_archive_is_confirmed_by_name_and_the_selection_survives_the_reread() -> None:
    ledger = MemoryEntriesLedger.with_entries(1000)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 5)
            assert screen.selected_id == entry_id(5)
            screen.query_one("#entries-browse-reason", Input).value = "duplicate import"
            await _press(pilot, screen, "entries-browse-archive")
            row = screen.page.rows[5] if screen.page is not None else None
            assert row is not None
            message = await _answer(pilot, accept=True)
            assert message == joined(
                (
                    tr("tui.ledger.entry_tools.browse.consequence.archive", entry=entry_label(row.transaction)),
                    tr("tui.ledger.entry_tools.browse.reason_line", reason="duplicate import"),
                )
            )

            [request] = lifecycle_requests(ledger, "ledger.archive")
            assert request.transaction_id == entry_id(5)
            assert request.reason == "duplicate import"
            assert screen.selected_id == entry_id(5)
            table = cast("DataTable[str]", screen.query_one("#entries-browse", DataTable))
            assert table.ordered_rows[table.cursor_row].key.value == entry_id(5)
            assert screen.page is not None
            assert screen.page.rows[5].transaction.lifecycle_state == "ARCHIVED"
            assert len(_list_requests(ledger)) == 2


@pytest.mark.asyncio
async def test_a_declined_confirmation_writes_nothing() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 1)
            for button_id in ("entries-browse-archive", "entries-browse-stash", "entries-browse-exclude"):
                await _press(pilot, screen, button_id)
                await _answer(pilot, accept=False)
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.entry_tools.browse.cancelled")
    assert [name for name, _ in ledger.requests] == ["list"]


@pytest.mark.asyncio
async def test_restore_and_exclude_submit_through_their_own_operations() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 0)
            await _press(pilot, screen, "entries-browse-stash")
            await _answer(pilot, accept=True)
            await _press(pilot, screen, "entries-browse-restore")
            await _answer(pilot, accept=True)
            await _press(pilot, screen, "entries-browse-exclude")
            await _answer(pilot, accept=True)
            assert screen.page is not None
            assert screen.page.rows[0].transaction.business_classification == "REVIEWED_EXCLUDED"
    assert [name for name, _ in ledger.requests if name != "list"] == [
        "ledger.stash",
        "ledger.restore",
        "ledger.exclude",
    ]


@pytest.mark.asyncio
async def test_a_lifecycle_validation_refusal_is_shown_and_writes_nothing() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    ledger.validation_refusals.add("ledger.archive")
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 0)
            await _press(pilot, screen, "entries-browse-archive")
            await _answer(pilot, accept=True)
            refusal = _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.entry_tools.browse.refused") in refusal
            assert "entry is cited by a filed declaration" in refusal
            assert screen.page is not None
            assert screen.page.rows[0].transaction.lifecycle_state == "ACTIVE"
            assert not screen.busy


@pytest.mark.asyncio
async def test_a_refused_page_read_shows_the_registered_refusal() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    ledger.refuse_with_registered_error("list")
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert _text(screen, "#ledger-refusal") == tr(ENTRIES_REFUSAL_KEY)
            assert _keys(screen) == []


@pytest.mark.asyncio
async def test_removal_is_previewed_by_a_dry_run_before_the_confirmed_run() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 2)
            assert screen.page is not None
            label = entry_label(screen.page.rows[2].transaction)
            await _press(pilot, screen, "entries-browse-remove")
            message = await _answer(pilot, accept=True)
            assert tr("tui.ledger.entry_tools.browse.remove_consequence", entry=label) in message
            assert entry_id(2) not in _keys(screen)
            assert screen.selected_id is None
    removals = [cast(LedgerRemoveRequest, request) for request in ledger.requested("remove")]
    assert [(request.transaction_id, request.dry_run) for request in removals] == [
        (entry_id(2), True),
        (entry_id(2), False),
    ]


@pytest.mark.asyncio
async def test_a_declined_removal_runs_only_its_dry_run() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 2)
            await _press(pilot, screen, "entries-browse-remove")
            await _answer(pilot, accept=False)
            assert entry_id(2) in _keys(screen)
    assert [cast(LedgerRemoveRequest, request).dry_run for request in ledger.requested("remove")] == [True]


@pytest.mark.asyncio
async def test_merge_submits_every_marked_entry_and_chooses_the_merged_one() -> None:
    ledger = MemoryEntriesLedger.with_entries(4)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert screen.query_one("#entries-browse-merge", Button).disabled
            for row in (1, 3):
                await _choose(pilot, screen, row)
                await _press(pilot, screen, "entries-browse-mark")
            assert set(screen.marked) == {entry_id(1), entry_id(3)}
            assert screen.page is not None
            labels = [entry_label(screen.page.rows[row].transaction) for row in (1, 3)]
            await _press(pilot, screen, "entries-browse-merge")
            message = await _answer(pilot, accept=True)
            assert all(label in message for label in labels)
            assert screen.marked == {}
            assert screen.selected_id is not None
            assert screen.selected_id in _keys(screen)
    [request] = [cast(LedgerMergeRequest, request) for request in ledger.requested("merge")]
    assert set(request.child_ids) == {entry_id(1), entry_id(3)}


@pytest.mark.asyncio
async def test_the_filters_build_the_operations_own_request() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            cast("Select[str]", screen.query_one("#entries-browse-status", Select)).value = "pending"
            cast("Select[str]", screen.query_one("#entries-browse-direction", Select)).value = "outgoing"
            cast("Select[str]", screen.query_one("#entries-browse-period", Select)).value = "2T"
            screen.query_one("#entries-browse-year", Input).value = "2026"
            screen.query_one("#entries-browse-text", Input).value = "office"
            cast("Select[str]", screen.query_one("#entries-browse-sort", Select)).value = "amount"
            cast("Select[str]", screen.query_one("#entries-browse-order", Select)).value = "desc"
            screen.query_one("#entries-browse-hide-rejected", Checkbox).value = True
            await _press(pilot, screen, "entries-browse-apply")

            screen.query_one("#entries-browse-account", Input).value = "ES9121000418450200051332"
            await _press(pilot, screen, "entries-browse-apply")
            assert _text(screen, "#ledger-refusal") == tr("tui.ledger.entry_tools.browse.filters_invalid")
            assert "ES9121000418450200051332" not in _text(screen, "#ledger-refusal")

    requests = _list_requests(ledger)
    assert len(requests) == 2
    applied = requests[1]
    assert applied.filters == ("status=pending", "direction=outgoing", "period=2T", "year=2026", "text=office")
    assert applied.sort_by is LedgerSortField.AMOUNT
    assert applied.sort_order is LedgerSortOrder.DESC
    assert applied.exclude_llm_rejected
    assert applied.offset == 0


@pytest.mark.asyncio
async def test_a_period_without_a_year_is_refused_before_any_read() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            cast("Select[str]", screen.query_one("#entries-browse-period", Select)).value = "1T"
            await _press(pilot, screen, "entries-browse-apply")
            assert _text(screen, "#ledger-refusal") == tr("tui.ledger.entry_tools.period.pair")
    assert len(_list_requests(ledger)) == 1


@pytest.mark.asyncio
async def test_history_and_lineage_open_for_the_chosen_entry_and_back_returns_to_it() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    app = WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 1)
            await _press(pilot, screen, "entries-browse-trace")
            await settle(pilot)
            trace = app.screen
            assert isinstance(trace, LedgerEntryTraceScreen)
            assert tr("tui.ledger.entry_tools.trace.manual") in str(
                trace.query_one("#entries-trace-track", Static).render()
            )
            assert tr("tui.ledger.entry_tools.trace.withheld", count=1) == str(
                trace.query_one("#entries-trace-withheld", Static).render()
            )
            history = cast("DataTable[str]", trace.query_one("#entries-trace-history", DataTable))
            assert history.row_count == 2
            assert "quoted from the document" not in str(history.get_row_at(1))

            trace.query_one("#entries-trace-full", Button).press()
            await settle(pilot)
            assert "quoted from the document" in str(history.get_row_at(1))

            await pilot.press("escape")
            await settle(pilot)
            back = app.screen
            assert isinstance(back, LedgerEntriesBrowseScreen)
            assert back.selected_id == entry_id(1)
    histories = [cast(LedgerHistoryRequest, request) for request in ledger.requested("history_typed")]
    assert [request.transaction_prefix for request in histories] == [entry_id(1)]
    assert len(ledger.requested("track")) == 1
    assert len(ledger.requested("history")) == 1


@pytest.mark.asyncio
async def test_a_lost_session_discards_every_entry_on_screen() -> None:
    ledger = MemoryEntriesLedger.with_entries(3)
    screen = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, 0)
            ledger.expire("ledger.archive")
            await _press(pilot, screen, "entries-browse-archive")
            await _answer(pilot, accept=True)
            assert screen.page is None
            assert screen.selected_id is None
            assert _keys(screen) == []

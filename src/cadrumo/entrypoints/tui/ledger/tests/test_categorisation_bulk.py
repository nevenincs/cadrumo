"""Bulk classification of a filtered page: every reviewed row is sent, and the operation reports what changed."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import cast

import pytest
from textual.widgets import DataTable, Select

from .....application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection, LedgerBulkClassifyRequest
from .....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from .....application.ledger.models import BulkClassifyFailure, BulkClassifyResult
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.transactions.enums import BusinessClassification
from ...tests.settling import settle
from ..categorisation_bulk import BULK_PAGE_SIZE, LedgerBulkClassifyScreen
from ..categorisation_common import short_id
from ..categorisation_doors import LedgerBulkClassifyDoorV1, LedgerSelectionDoorV1
from .categorisation_entry_fixtures import MemoryLedger
from .categorisation_fixtures import CATEGORISATION_REFUSAL_KEY, MemoryDoor, synthetic_id
from .categorisation_memory_doors import categorisation_controller
from .categorisation_pilot import keys, press, text, type_into
from .workspace_fixtures import WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

type BulkHandler = Callable[[LedgerBulkClassifyRequest], LedgerBulkClassifyProjection]


def _screen(
    ledger: MemoryLedger,
    bulk_handler: BulkHandler | None = None,
) -> tuple[
    LedgerBulkClassifyScreen,
    MemoryDoor[LedgerListRequest, LedgerListProjection],
    MemoryDoor[LedgerBulkClassifyRequest, LedgerBulkClassifyProjection],
]:
    selection = MemoryDoor(ledger.list_page)
    bulk = MemoryDoor(bulk_handler or ledger.bulk_classify)
    screen = LedgerBulkClassifyScreen(
        categorisation_controller(),
        selection_door=cast(LedgerSelectionDoorV1, selection),
        bulk_door=cast(LedgerBulkClassifyDoorV1, bulk),
    )
    return screen, selection, bulk


def _answers(result: BulkClassifyResult) -> BulkHandler:
    """An operation that reports ``result`` for the batch it receives, whatever the screen sent."""

    def answer(request: LedgerBulkClassifyRequest) -> LedgerBulkClassifyProjection:
        return LedgerBulkClassifyProjection(profile_id=request.profile_id, outcome="classified", result=result)

    return answer


def _sent_ids(request: LedgerBulkClassifyRequest) -> list[str]:
    return [row["transaction_id"] for row in csv.DictReader(io.StringIO(request.csv_text))]


def _classifications(ledger: MemoryLedger) -> dict[str, str]:
    return {key: entry.business_classification for key, entry in ledger.entries.items()}


@pytest.mark.asyncio
async def test_the_review_lists_every_row_of_the_page_and_every_row_is_sent() -> None:
    ledger = MemoryLedger.with_entries(6)
    screen, selection, bulk = _screen(ledger)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert len(keys(screen, "#categorisation-bulk-entries")) == 6
            cast("Select[str]", screen.query_one("#categorisation-bulk-status", Select)).value = "pending"
            await press(pilot, screen, "categorisation-bulk-read")
            assert selection.requests[-1].filters == ("status=pending",)
            pending = [synthetic_id(index) for index in (1, 3, 5)]
            assert keys(screen, "#categorisation-bulk-entries") == pending

            type_into(screen, "#categorisation-bulk-category", "suministros_oficina")
            await press(pilot, screen, "categorisation-bulk-review")
            assert bulk.requests == []
            assert keys(screen, "#categorisation-bulk-changing") == pending
            assert screen.query_one("#categorisation-bulk-changing", DataTable).display
            assert text(screen, "#categorisation-staged") == tr(
                "tui.ledger.categorisation.bulk.stage",
                count=3,
                classification=tr("tui.ledger.categorisation.classification.business"),
                category="suministros_oficina",
            )

            await press(pilot, screen, "categorisation-confirm")
            sent = list(csv.DictReader(io.StringIO(bulk.requests[0].csv_text)))
            assert [row["transaction_id"] for row in sent] == pending
            assert {row["classification"] for row in sent} == {"BUSINESS"}
            assert {row["category_id"] for row in sent} == {"suministros_oficina"}
            assert all(
                ledger.entries[key].business_classification == BusinessClassification.BUSINESS.value for key in pending
            )
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.bulk.done", applied=3, skipped=0, failed=0
            )
            assert keys(screen, "#categorisation-bulk-entries") == []


@pytest.mark.asyncio
async def test_a_page_that_already_matches_is_sent_and_the_operation_reports_it_unchanged() -> None:
    ledger = MemoryLedger.with_entries(3, classification=BusinessClassification.BUSINESS)
    before = _classifications(ledger)
    screen, _selection, bulk = _screen(ledger, _answers(BulkClassifyResult(total=3, applied=0, skipped=3)))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            page = keys(screen, "#categorisation-bulk-entries")
            assert page == [synthetic_id(index) for index in (1, 2, 3)]
            await press(pilot, screen, "categorisation-bulk-review")
            assert screen.staged is not None
            assert text(screen, "#ledger-refusal") == ""
            assert keys(screen, "#categorisation-bulk-changing") == page

            await press(pilot, screen, "categorisation-confirm")
            assert len(bulk.requests) == 1
            assert _sent_ids(bulk.requests[0]) == page
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.bulk.done", applied=0, skipped=3, failed=0
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")
            assert _classifications(ledger) == before


@pytest.mark.asyncio
async def test_a_mixed_page_sends_every_row_and_shows_the_operations_own_report() -> None:
    ledger = MemoryLedger.with_entries(6)
    refused_entry = synthetic_id(5)
    reason = "a finalised calculation uses this entry"
    report = BulkClassifyResult(
        total=6,
        applied=2,
        skipped=3,
        failures=(BulkClassifyFailure(row_index=4, transaction_id=refused_entry, reason=reason),),
        bucket_event_ids=("event-1", "event-2"),
    )
    screen, _selection, bulk = _screen(ledger, _answers(report))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            page = keys(screen, "#categorisation-bulk-entries")
            assert sorted(page) == sorted(synthetic_id(index) for index in range(1, 7))
            matching = {key for key in page if ledger.entries[key].business_classification == "BUSINESS"}
            assert matching
            assert matching != set(page)

            await press(pilot, screen, "categorisation-bulk-review")
            assert keys(screen, "#categorisation-bulk-changing") == page
            assert text(screen, "#categorisation-staged") == tr(
                "tui.ledger.categorisation.bulk.stage",
                count=6,
                classification=tr("tui.ledger.categorisation.classification.business"),
                category="-",
            )

            await press(pilot, screen, "categorisation-confirm")
            assert _sent_ids(bulk.requests[0]) == page
            assert text(screen, "#categorisation-outcome") == "\n".join(
                (
                    tr("tui.ledger.categorisation.bulk.done", applied=2, skipped=3, failed=1),
                    tr(
                        "tui.ledger.categorisation.bulk.failure",
                        row=4,
                        entry=short_id(refused_entry),
                        reason=reason,
                    ),
                )
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.saved")


@pytest.mark.asyncio
async def test_a_refusal_by_the_operation_is_said_on_the_screen_and_changes_nothing() -> None:
    ledger = MemoryLedger.with_entries(2)
    before = _classifications(ledger)
    message = "category_id is not a declared spending category"

    def refuse(request: LedgerBulkClassifyRequest) -> LedgerBulkClassifyProjection:
        return LedgerBulkClassifyProjection(
            profile_id=request.profile_id, outcome="validation_error", validation_messages=(message,)
        )

    screen, _selection, bulk = _screen(ledger, refuse)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-bulk-category", "unknown_category")
            await press(pilot, screen, "categorisation-bulk-review")
            await press(pilot, screen, "categorisation-confirm")
            assert len(bulk.requests) == 1
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.bulk.refused", messages=message
            )
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")
            assert _classifications(ledger) == before

            bulk.refusing = True
            await press(pilot, screen, "categorisation-bulk-review")
            await press(pilot, screen, "categorisation-confirm")
            assert len(bulk.requests) == 2
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
            assert _classifications(ledger) == before


@pytest.mark.asyncio
async def test_a_share_is_refused_unless_the_classification_is_mixed() -> None:
    screen, _selection, bulk = _screen(MemoryLedger.with_entries(2))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            type_into(screen, "#categorisation-bulk-pct", "0.5")
            await press(pilot, screen, "categorisation-bulk-review")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.bulk.share_mixed_only")
            assert bulk.requests == []


@pytest.mark.asyncio
async def test_an_empty_ledger_and_a_refused_read_are_said_on_the_screen() -> None:
    screen, selection, bulk = _screen(MemoryLedger())
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.bulk.empty")
            assert text(screen, "#categorisation-bulk-page") == tr("tui.ledger.categorisation.page.empty")
            await press(pilot, screen, "categorisation-bulk-review")
            assert screen.staged is None
            assert text(screen, "#ledger-refusal") == tr("tui.ledger.categorisation.bulk.empty")
            assert bulk.requests == []
            selection.refusing = True
            await press(pilot, screen, "categorisation-bulk-read")
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)


@pytest.mark.asyncio
async def test_a_thousand_entries_are_read_one_page_at_a_time() -> None:
    screen, selection, _bulk = _screen(MemoryLedger.with_entries(1000))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert BULK_PAGE_SIZE <= 200
            assert all(request.limit == BULK_PAGE_SIZE for request in selection.requests)
            assert len(keys(screen, "#categorisation-bulk-entries")) == BULK_PAGE_SIZE
            assert len(screen.rows) == BULK_PAGE_SIZE
            await press(pilot, screen, "categorisation-bulk-previous")
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.page.none")
            for _ in range(4):
                await press(pilot, screen, "categorisation-bulk-next")
            assert selection.requests[-1].offset == 4 * BULK_PAGE_SIZE
            assert keys(screen, "#categorisation-bulk-entries")[0] == synthetic_id(4 * BULK_PAGE_SIZE + 1)
            assert text(screen, "#categorisation-bulk-page") == tr(
                "tui.ledger.categorisation.page.window", first=801, last=1000, total=1000
            )
            await press(pilot, screen, "categorisation-bulk-next")
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.page.none")
            await press(pilot, screen, "categorisation-bulk-previous")
            assert selection.requests[-1].offset == 3 * BULK_PAGE_SIZE
            assert len(screen.rows) == BULK_PAGE_SIZE

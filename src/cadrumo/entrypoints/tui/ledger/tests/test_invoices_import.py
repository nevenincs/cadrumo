"""Mounted invoice book import: review by digest, import exactly the reviewed file, report every row."""

from __future__ import annotations

from pathlib import Path
from typing import cast, override

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static
from textual.worker import NoActiveWorker, get_current_worker

from .....application.invoices.catalogue_intake_contracts import InvoiceImportProjection, InvoiceImportRequest
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.invoices.errors import InvoiceValidationError
from .....domain.iva.schema import InvoiceKind
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController
from ..invoices_import import LedgerInvoiceImportScreen, LedgerInvoiceImportSourceV1
from ..models import LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from ..workspace_presentation import door_refusal_text
from .invoices_fixtures import (
    SYNTHETIC_SOURCE_PATH,
    SYNTHETIC_SOURCE_SHA256,
    MemoryInvoiceImportDoor,
    ReplacingHostApp,
    import_outcome,
)
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

MISSING_PATH = str(Path(Path.cwd().anchor, "synthetic", "missing.xlsx"))

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _screen(door: MemoryInvoiceImportDoor) -> LedgerInvoiceImportScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerInvoiceImportScreen(controller, door)


def _text(screen: LedgerInvoiceImportScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: LedgerInvoiceImportScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


async def _review(pilot: Pilot[None], screen: LedgerInvoiceImportScreen, path: str = SYNTHETIC_SOURCE_PATH) -> None:
    cast("Select[str]", screen.query_one("#ledger-invoices-import-kind", Select)).value = InvoiceKind.ISSUED.value
    screen.query_one("#ledger-invoices-import-path", Input).value = path
    screen.query_one("#ledger-invoices-import-country", Input).value = "es"
    await _press(pilot, screen, "ledger-invoices-import-review")


@pytest.mark.asyncio
async def test_the_import_is_bound_to_the_reviewed_digest_and_reports_a_partial_outcome() -> None:
    door = MemoryInvoiceImportDoor()
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _review(pilot, screen)
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        assert door.requests == []
        summary = _text(screen, "#ledger-invoices-import-summary")
        assert tr("tui.ledger.invoices.import.summary.digest", digest=SYNTHETIC_SOURCE_SHA256) in summary
        assert tr("tui.ledger.invoices.import.summary.file", name="facturas-recibidas.xlsx", size="18432") in summary
        assert screen.query_one("#ledger-invoices-import-path", Input).disabled
        await _press(pilot, screen, "ledger-invoices-import-confirm")
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert door.requests == [
            InvoiceImportRequest(
                profile_id=door.profile_id,
                kind=InvoiceKind.ISSUED,
                source_path=SYNTHETIC_SOURCE_PATH,
                source_sha256=SYNTHETIC_SOURCE_SHA256,
                country="ES",
            )
        ]
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.invoices.import.partial")
        assert tr("tui.ledger.invoices.import.counts", rows="4", created="2", skipped="1", refused="1") in _text(
            screen, "#ledger-invoices-import-outcome"
        )
        refused = cast("DataTable[str]", screen.query_one("#ledger-invoices-import-refused", DataTable))
        assert refused.display
        assert [str(row.key.value) for row in refused.ordered_rows] == ["5:invoice_date:1"]
        assert refused.get_row_at(0) == ["5", "invoice_date", "must be a date"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "headline"),
    [
        (import_outcome(created=3, skipped=0, refused=0), "tui.ledger.invoices.import.succeeded"),
        (import_outcome(created=0, skipped=2, refused=0), "tui.ledger.invoices.import.nothing_created"),
    ],
)
async def test_a_whole_or_empty_import_is_named_as_such(outcome: InvoiceImportProjection, headline: str) -> None:
    door = MemoryInvoiceImportDoor(outcome)
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-import-confirm")
        assert _text(screen, "#ledger-flow-status") == tr(headline)
        assert not screen.query_one("#ledger-invoices-import-refused", DataTable).display


@pytest.mark.asyncio
async def test_a_file_that_changed_after_review_is_refused_on_screen() -> None:
    door = MemoryInvoiceImportDoor()
    # What the worker raises when the bytes it reads differ from the reviewed digest.
    refusal = InvoiceValidationError("bulk invoice import source differs from its submitted digest")
    door.apply_refusal = refusal
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-import-confirm")
        assert screen.flow_state is LedgerFlowState.FAILED
        assert _text(screen, "#ledger-refusal") == door_refusal_text(refusal)
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.invoices.import.failed")
        assert screen.query_one("#ledger-invoices-import-again", Button).display


@pytest.mark.asyncio
async def test_an_unreadable_path_is_refused_before_review_and_a_blank_one_is_asked_for() -> None:
    door = MemoryInvoiceImportDoor()
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _press(pilot, screen, "ledger-invoices-import-review")
        assert _text(screen, "#ledger-refusal") == tr("tui.ledger.invoices.import.path_required")
        assert door.previews == []
        await _review(pilot, screen, MISSING_PATH)
        assert screen.flow_state is LedgerFlowState.EDITING
        assert _text(screen, "#ledger-refusal") == tr(
            "application.invoices.bulk_import.errors.file_read_failed",
            path_name=MISSING_PATH,
            error_type="FileNotFoundError",
        )
        assert door.requests == []


@pytest.mark.asyncio
async def test_cancelling_the_reviewed_import_writes_nothing_and_starting_again_keeps_the_form() -> None:
    door = MemoryInvoiceImportDoor()
    screen = _screen(door)
    screen.back_area = LedgerWorkspaceArea.OVERVIEW
    async with ReplacingHostApp(screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-import-cancel")
        assert screen.flow_state is LedgerFlowState.CANCELLED
        assert door.requests == []
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.invoices.import.cancelled")
        await _press(pilot, screen, "ledger-invoices-import-again")
        await _settle(pilot)
        fresh = pilot.app.screen
        assert isinstance(fresh, LedgerInvoiceImportScreen)
        assert fresh is not screen
        assert fresh.flow_state is LedgerFlowState.EDITING
        assert fresh.back_area is LedgerWorkspaceArea.OVERVIEW
        assert fresh.query_one("#ledger-invoices-import-path", Input).value == SYNTHETIC_SOURCE_PATH


class _WorkerOnlyImportDoor(MemoryInvoiceImportDoor):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, bool]] = []

    def _enter(self, name: str) -> None:
        try:
            get_current_worker()
        except NoActiveWorker:
            self.calls.append((name, False))
        else:
            self.calls.append((name, True))

    @override
    async def preview(self, source_path: str) -> LedgerInvoiceImportSourceV1:
        self._enter("preview")
        return await super().preview(source_path)

    @override
    async def apply(self, request: InvoiceImportRequest) -> InvoiceImportProjection:
        self._enter("apply")
        return await super().apply(request)


@pytest.mark.asyncio
async def test_the_import_door_runs_only_in_workers() -> None:
    door = _WorkerOnlyImportDoor()
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-import-confirm")
    assert door.calls == [("preview", True), ("apply", True)]


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (100, 30), (120, 40), (200, 50)))
async def test_the_import_screen_fits_every_supported_terminal(theme: str, size: tuple[int, int]) -> None:
    door = MemoryInvoiceImportDoor()
    screen = _screen(door)
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await _settle(pilot)
            await _review(pilot, screen)
            await _press(pilot, screen, "ledger-invoices-import-confirm")
            assert geometry_band(app, size[0]) == []
            assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
            owners = [w for w in screen.query(VerticalScroll) if w.display and w.show_vertical_scrollbar]
            assert all(owner.id == "ledger-page" for owner in owners)

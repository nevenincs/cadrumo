"""Classification continuation through actual public Ledger screen replacement."""

from __future__ import annotations

import asyncio
from threading import Event
from typing import Any

import pytest
from textual.widgets import DataTable

from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.overview import LedgerOverviewScreen
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    ClassificationDoor,
    WorkspaceHostApp,
    ledger_classify_action,
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from cadrumo.entrypoints.tui.tests.settling import settle

from .. import iva_tui_import
from ..iva_tui_scenario import _synthetic_rows

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_classification_waits_for_public_overview_after_refresh_replaces_its_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal departing-screen worker cancellation cannot abort continuation."""
    projection = ledger_projection()
    release = Event()
    refresh_started = Event()
    door = ClassificationDoor()

    def refresh() -> LedgerWorkspaceRefreshV1:
        refresh_started.set()
        assert release.wait(timeout=10)
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=None)

    async def already_in_ledger(_pilot: Any) -> None:
        return None

    monkeypatch.setattr(iva_tui_import, "_open_ledger", already_in_ledger)
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ledger_classify_action(),
            classification_submitter=door,
            refresh=refresh,
        ),
    )
    app = WorkspaceHostApp(LedgerOverviewScreen(controller))
    async with app.run_test(size=(160, 60)) as pilot:
        await settle(pilot, workers=False)

        async def finish_refresh() -> None:
            assert await asyncio.to_thread(refresh_started.wait, 10)
            # Hold the read long enough to expose a global wait on the departing worker.
            await asyncio.sleep(0.05)
            release.set()

        completion = asyncio.create_task(finish_refresh())
        try:
            await iva_tui_import._classify_transaction(
                pilot,
                transaction_id=str(projection.entries[0].transaction_id),
                scenario_row=_synthetic_rows(2025)[0],
            )
            assert isinstance(app.screen, LedgerOverviewScreen)
            assert app.screen.query_one("#ledger-quality", DataTable).row_count > 0
            assert len(door.calls) == 1
        finally:
            release.set()
            await completion

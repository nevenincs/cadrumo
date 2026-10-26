"""A statement file only the local AI reads offers the local AI's setup beside the import's preview and result.

The import door reports each refused file with the setup action its reader's
verdict named. The screen reads that item's quick-status row the way the TUI
root reads it: an absent row's action sets the item up, so the offer opens the
setup page on it; a row this build cannot set up shows its own sentence and
offers nothing; a status without the row offers nothing. A refused file whose
verdict names no setup reads no row. The screen runs under Textual's pilot.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Static

from .....adapters.outbound.components.tests.recorded_rows import not_in_this_build_row, recorded_absent_row
from .....application.dependency_contracts import DependencyStatusRow
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...setup.offer import SetupItemOffer
from ...tests.settling import settle, settle_until
from ..controller import LedgerWorkspaceController
from ..import_flow import LedgerImportScreen
from ..models import (
    LedgerFlowState,
    LedgerImportFileRefusalV1,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportSourceBindingV1,
)
from ..workspace_injection import LedgerWorkspaceInjection
from .setup_status_fixtures import LOCAL_AI_DESKTOP, LOCAL_AI_HELD, SetupStatusWorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_DIGEST = "e" * 64


class _ReaderRefusingImportDoor:
    """One statement imports and one is refused because its reader could not be asked."""

    def __init__(self, recovery_action_id: str | None) -> None:
        self.recovery_action_id = recovery_action_id
        self.applied: list[LedgerImportRequestV1] = []

    def _refused(self) -> LedgerImportFileRefusalV1:
        key = "reader_unavailable" if self.recovery_action_id is not None else "reader_unavailable_here"
        return LedgerImportFileRefusalV1(
            file_name="scanned.pdf",
            reason=tr(f"tui.ledger.import.refusal.{key}"),
            recovery_action_id=self.recovery_action_id,
        )

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=True,
            files=2,
            rows=2,
            imported=2,
            skipped=0,
            refused_files=(self._refused(),),
            sources=(LedgerImportSourceBindingV1(path=request.path, sha256=_DIGEST),),
        )

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.applied.append(request)
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=False,
            files=2,
            rows=2,
            imported=2,
            skipped=0,
            refused_files=(self._refused(),),
        )


def _screen(door: _ReaderRefusingImportDoor) -> LedgerImportScreen:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), import_door=door),
    )
    return LedgerImportScreen(controller)


async def _import(
    tmp_path: Path, door: _ReaderRefusingImportDoor, rows: tuple[DependencyStatusRow, ...]
) -> tuple[SetupStatusWorkspaceHostApp, dict[str, tuple[bool, str, str | None]], str]:
    """Preview and apply a folder, reading the offer after each step, and press the offer when it is a button."""
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "statement.csv").write_text("synthetic", encoding="utf-8")
    screen = _screen(door)
    host = SetupStatusWorkspaceHostApp(screen, rows=rows)
    seen: dict[str, tuple[bool, str, str | None]] = {}
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=(110, 70)) as pilot:
            await settle(pilot)
            offer = screen.query_one("#ledger-import-setup", SetupItemOffer)
            assert not offer.display, "nothing is offered before an import is read"
            screen.query_one("#ledger-import-path", Input).value = str(folder)
            screen.query_one("#ledger-import-preview-button", Button).press()
            await settle_until(pilot, lambda: screen.flow_state is LedgerFlowState.CONFIRMING, "the preview")
            await settle(pilot)
            seen["preview"] = _offer_shown(offer)
            screen.query_one("#ledger-import-confirm", Button).press()
            await settle_until(pilot, lambda: screen.flow_state is LedgerFlowState.SUCCEEDED, "the import")
            await settle(pilot)
            seen["result"] = _offer_shown(offer)
            outcome = str(screen.query_one("#ledger-import-preview", Static).render())
            button = offer.query_one(Button)
            if offer.display and button.display:
                button.press()
                await settle(pilot)
    return host, seen, outcome


def _offer_shown(offer: SetupItemOffer) -> tuple[bool, str, str | None]:
    button = offer.query_one(Button)
    label = str(button.label) if offer.display and button.display else None
    return offer.display, str(offer.query_one(Static).render()), label


@pytest.mark.asyncio
async def test_a_file_only_the_local_ai_reads_points_to_the_desktop_app_beside_the_preview_and_the_result(
    tmp_path: Path,
) -> None:
    host, seen, outcome = await _import(
        tmp_path, _ReaderRefusingImportDoor(LOCAL_AI_PROVISION_ACTION_ID), (recorded_absent_row("local_ai"),)
    )

    with override_settings(cadrumo_output_language="en"):
        assert tr("tui.ledger.import.refusal.reader_unavailable") in outcome
    assert seen["preview"] == (True, LOCAL_AI_DESKTOP, None)
    assert seen["result"] == (True, LOCAL_AI_DESKTOP, None)
    assert host.row_reads == ["local_ai", "local_ai"]
    assert host.requested == []


@pytest.mark.asyncio
async def test_a_local_ai_this_build_cannot_set_up_shows_its_sentence_and_offers_nothing(tmp_path: Path) -> None:
    host, seen, _outcome = await _import(
        tmp_path, _ReaderRefusingImportDoor(LOCAL_AI_PROVISION_ACTION_ID), (not_in_this_build_row("local_ai"),)
    )

    assert seen["result"] == (True, LOCAL_AI_HELD, None)
    assert host.requested == []


@pytest.mark.asyncio
async def test_an_unreadable_setup_status_offers_nothing(tmp_path: Path) -> None:
    host, seen, _outcome = await _import(tmp_path, _ReaderRefusingImportDoor(LOCAL_AI_PROVISION_ACTION_ID), ())

    assert seen["preview"][0] is False
    assert seen["result"][0] is False
    assert host.row_reads == ["local_ai", "local_ai"]
    assert host.requested == []


@pytest.mark.asyncio
async def test_a_reader_this_computer_cannot_run_is_worded_apart_and_reads_no_row(tmp_path: Path) -> None:
    host, seen, outcome = await _import(tmp_path, _ReaderRefusingImportDoor(None), (recorded_absent_row("local_ai"),))

    with override_settings(cadrumo_output_language="en"):
        assert tr("tui.ledger.import.refusal.reader_unavailable_here") in outcome
        assert tr("tui.ledger.import.refusal.reader_unavailable") not in outcome
    assert seen["result"][0] is False
    assert host.row_reads == []
    assert host.requested == []

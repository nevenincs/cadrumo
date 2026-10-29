"""Bulk intake of one folder: reviewed first, then each document's outcome, and a partial batch said so.

A batch whose reader paused it says so in its outcome, whatever the pause's
verdict. The pause verdicts are the probe no-recovery verdicts.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import DataTable, Input, Select

from .....application.ledger.batch_ingest import InferencePause
from .....application.ledger.evidence_ingestion_contracts import LedgerEvidenceBatchRequest
from .....application.probe_outcomes import ProbePreconditionCondition, probe_no_recovery_verdict
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.model_roles import ModelRole
from .....domain.iva.schema import InvoiceKind
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..evidence_files_batch import LedgerEvidenceFilesBatchScreen
from ..evidence_files_write import LedgerEvidenceFilesWriteScreen
from ..models import LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from .evidence_files_fixtures import EVIDENCE_FILES_REFUSAL_KEY, MemoryEvidenceFilesStore, press, text_of
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(store: MemoryEvidenceFilesStore) -> LedgerEvidenceFilesBatchScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerEvidenceFilesBatchScreen(controller, store.doors())


async def _stage(pilot: Pilot[None], directory: str, direction: InvoiceKind = InvoiceKind.RECEIVED) -> None:
    screen = pilot.app.screen
    screen.query_one("#evidence-files-batch-directory", Input).value = directory
    cast("Select[str]", screen.query_one("#evidence-files-batch-direction", Select)).value = direction.value
    await press(pilot, "evidence-files-batch-review")


def _outcome_rows(pilot: Pilot[None]) -> list[list[object]]:
    table = pilot.app.screen.query_one("#evidence-files-outcome-rows", DataTable)
    return [list(table.get_row_at(index)) for index in range(table.row_count)]


@pytest.mark.asyncio
async def test_a_partial_batch_reports_each_document_and_says_it_was_partial(tmp_path: Path) -> None:
    store = MemoryEvidenceFilesStore()
    store.batch_documents = (("factura-a.pdf", "ingested"), ("factura-b.pdf", "refused"))
    store.batch_unreadable = ("factura-c.pdf",)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _stage(pilot, str(tmp_path), InvoiceKind.ISSUED)
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert text_of(write, "#evidence-files-review").startswith(
                tr(
                    "tui.ledger.evidence_files.batch.stage",
                    directory=str(tmp_path),
                    direction=tr("tui.ledger.invoice.kind.issued"),
                )
            )
            assert store.requests_of(LedgerEvidenceBatchRequest) == []

            await press(pilot, "evidence-files-confirm")
            [request] = store.requests_of(LedgerEvidenceBatchRequest)
            assert request.sources == (str(tmp_path),)
            assert request.source_directory == str(tmp_path)
            assert request.direction is InvoiceKind.ISSUED
            assert write.flow_state is LedgerFlowState.SUCCEEDED
            assert text_of(write, "#ledger-flow-status") == tr("tui.ledger.evidence_files.write.partial")
            assert tr("tui.ledger.evidence_files.batch.outcome.partial") in text_of(write, "#evidence-files-outcome")
            rows = sorted(_outcome_rows(pilot), key=lambda row: str(row[0]))
            assert rows == [
                ["factura-a.pdf", tr("tui.ledger.evidence_files.batch.status.ingested"), "-"],
                ["factura-b.pdf", tr("tui.ledger.evidence_files.batch.status.refused"), "unsupported_document"],
                ["factura-c.pdf", tr("tui.ledger.evidence_files.batch.status.unreadable"), "unreadable_source"],
            ]
            # The unreadable source is named by its file alone, never by the folder typed for the batch.
            assert all(str(tmp_path) not in str(cell) for row in rows for cell in row)

            await press(pilot, "evidence-files-done")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesBatchScreen)


@pytest.mark.asyncio
async def test_a_complete_batch_is_not_called_partial(tmp_path: Path) -> None:
    store = MemoryEvidenceFilesStore()
    store.batch_documents = (("factura-a.pdf", "ingested"), ("factura-b.pdf", "no_op"))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _stage(pilot, str(tmp_path))
            await press(pilot, "evidence-files-confirm")
            write = pilot.app.screen
            assert text_of(write, "#ledger-flow-status") == tr("tui.ledger.evidence_files.write.saved")
            assert tr("tui.ledger.evidence_files.batch.outcome.partial") not in text_of(
                write, "#evidence-files-outcome"
            )


@pytest.mark.asyncio
async def test_a_relative_or_blank_folder_is_refused_before_anything_is_sent() -> None:
    store = MemoryEvidenceFilesStore()
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await press(pilot, "evidence-files-batch-review")
            screen = pilot.app.screen
            assert isinstance(screen, LedgerEvidenceFilesBatchScreen)
            assert text_of(screen, "#ledger-refusal") == tr("tui.ledger.evidence_files.batch.directory_required")
            await _stage(pilot, "facturas")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesBatchScreen)
            assert "absolute" in text_of(screen, "#ledger-refusal")
            assert store.requests_of(LedgerEvidenceBatchRequest) == []


@pytest.mark.asyncio
async def test_a_refused_batch_is_shown_on_the_write_step(tmp_path: Path) -> None:
    store = MemoryEvidenceFilesStore()
    store.refusing.add("batch")
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _stage(pilot, str(tmp_path))
            await press(pilot, "evidence-files-confirm")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert write.flow_state is LedgerFlowState.FAILED
            assert text_of(write, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)


def _model_pause() -> InferencePause:
    """The pause a refused read gives when the role's selected model is not installed."""
    verdict = probe_no_recovery_verdict(
        ProbePreconditionCondition.ROLE_MODEL_INSTALLED,
        facts={"role": ModelRole.TEXT_EXTRACTION.value, "role_model_installed": False},
    )
    return InferencePause(facts={"role_model_installed": False}, precondition_verdict=verdict)


def _unselected_pause() -> InferencePause:
    """A pause for a role with no selected model."""
    return InferencePause(
        facts={"role_model_selected": False},
        precondition_verdict=probe_no_recovery_verdict(
            ProbePreconditionCondition.SELECTED_MODEL_AVAILABLE,
            facts={"role": ModelRole.TEXT_EXTRACTION.value, "role_model_selected": False},
        ),
    )


def _paused_store(pause: InferencePause) -> MemoryEvidenceFilesStore:
    store = MemoryEvidenceFilesStore()
    store.batch_documents = (("factura-a.pdf", "ingested"), ("ticket-b.jpg", "paused"))
    store.batch_pause = pause
    return store


@pytest.mark.asyncio
@pytest.mark.parametrize("pause", [_model_pause, _unselected_pause], ids=["model-not-installed", "no-selection"])
async def test_a_paused_batch_says_so_in_its_outcome(tmp_path: Path, pause: Callable[[], InferencePause]) -> None:
    store = _paused_store(pause())
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _stage(pilot, str(tmp_path))
            await press(pilot, "evidence-files-confirm")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            outcome = text_of(write, "#evidence-files-outcome")
            assert tr("tui.ledger.evidence_files.batch.outcome.paused") in outcome

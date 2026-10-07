"""Selected history controls dispatch typed requests through registered runtime operations."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from textual.screen import Screen

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....core.modelo_export_artefact import ModeloExportArtefact
from .....core.operations import profile_operation_subject
from .....core.payment_election import PaymentElection
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from ...components.host import ScreenHostApp
from ...modelo.workbench.ports import WorkbenchExportRequest
from .. import historical_export, reconciliation_export

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("historical", [True, False])
async def test_selected_history_export_submits_exact_saved_identity(
    monkeypatch, tmp_path: Path, historical: bool
) -> None:
    profile = UUID("22222222-2222-4222-8222-222222222222")
    client = SimpleNamespace(profile_id=profile, session_id=UUID("33333333-3333-4333-8333-333333333333"))
    submitted = []

    class Controller:
        async def start(self):
            return None

        @classmethod
        async def submit(cls, submitted_client, **kwargs):
            assert submitted_client is client
            submitted.append(kwargs)
            return cls()

    module = historical_export if historical else reconciliation_export
    screen_type = (
        historical_export.HistoricalFilingExportScreen
        if historical
        else reconciliation_export.ReconciliationExportScreen
    )
    monkeypatch.setattr(screen_type, "on_mount", lambda _self: None)
    monkeypatch.setattr(module, "RuntimeOperationController", Controller)
    monkeypatch.setattr(module, "OperationModal", lambda _controller: Screen())
    screen = screen_type(cast(RuntimeFrontendClient, client), "a" * 64)
    if isinstance(screen, historical_export.HistoricalFilingExportScreen):
        screen._revision_id = "b" * 64
    request = WorkbenchExportRequest(
        output_path=str(tmp_path / "saved.xlsx"),
        artefact=ModeloExportArtefact.CALCULATION_REVIEW_XLSX,
        refund_election=RefundElection.COMPENSAR,
        payment_election=PaymentElection.INGRESO,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        replace_existing=True,
    )
    async with ScreenHostApp[None](screen).run_test() as pilot:
        await screen._publish(request)
        await pilot.pause()
    assert len(submitted) == 1
    call = submitted[0]
    assert call["subject_ref"] == profile_operation_subject(str(profile))
    assert call["expected_session_id"] == client.session_id
    payload = call["payload"]
    assert payload.profile_id == profile
    assert payload.output_path == request.output_path
    assert payload.replace_existing
    if historical:
        assert call["definition_id"] == "export.calculation-review-xlsx"
        assert payload.calculation_revision_id == "b" * 64
        assert payload.filing_record_id == "a" * 64
    else:
        assert call["definition_id"] == "modelo.reconcile.export-xlsx"
        assert payload.work_unit_id == "a" * 64
        assert not payload.all_history
        assert payload.event_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_historical_tui_resolves_saved_filing_before_offering_export(monkeypatch, available: bool) -> None:
    profile = UUID("22222222-2222-4222-8222-222222222222")
    client = SimpleNamespace(profile_id=profile, session_id=UUID("33333333-3333-4333-8333-333333333333"))
    reads = []

    async def read(_client, **kwargs):
        reads.append(kwargs)
        return SimpleNamespace(
            profile_id=profile,
            filing_record_id="a" * 64,
            record=SimpleNamespace(filing_record_id="a" * 64, calculation_revision_id="b" * 64),
            historical_content=SimpleNamespace(
                calculation_revision_id="b" * 64, availability="available" if available else "missing"
            ),
            observation_layers=SimpleNamespace(effective_revision="c" * 64),
        )

    monkeypatch.setattr(historical_export, "read_runtime_workbench_operation", read)
    screen = historical_export.HistoricalFilingExportScreen(cast(RuntimeFrontendClient, client), "a" * 64)
    async with ScreenHostApp[None](screen).run_test() as pilot:
        await pilot.pause()
        assert reads[0]["definition_id"] == "modelo.filing_record.view"
        assert reads[0]["payload"].filing_record_id == "a" * 64
        assert screen._revision_id == ("b" * 64 if available else None)
        assert isinstance(screen.app.screen, historical_export.WorkbenchExportScreen) is available

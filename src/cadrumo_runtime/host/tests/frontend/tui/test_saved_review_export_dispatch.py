"""Selected history controls dispatch typed requests through registered runtime operations."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from textual.screen import Screen

from cadrumo.application.modelo.filing_record_view_operation import (
    ModeloFilingRecordViewProjection,
    ModeloFilingRecordViewRequest,
)
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.entrypoints.tui import historical_export, reconciliation_export
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.modelo.workbench.ports import WorkbenchExportRequest
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.modelo import runtime_workbench_reads

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
    monkeypatch.setattr(module, "OperationController", Controller)
    monkeypatch.setattr(module, "OperationModal", lambda _controller: Screen())
    screen = screen_type(cast(FrontendClient, client), "a" * 64)
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

    async def read(read_client, filing_record_id):
        assert read_client is client
        reads.append(filing_record_id)
        return SimpleNamespace(
            profile_id=profile,
            filing_record_id="a" * 64,
            record=SimpleNamespace(filing_record_id="a" * 64, calculation_revision_id="b" * 64),
            historical_content=SimpleNamespace(
                calculation_revision_id="b" * 64, availability="available" if available else "missing"
            ),
            observation_layers=SimpleNamespace(effective_revision="c" * 64),
        )

    monkeypatch.setattr(historical_export, "read_filing_view", read)
    screen = historical_export.HistoricalFilingExportScreen(cast(FrontendClient, client), "a" * 64)
    async with ScreenHostApp[None](screen).run_test() as pilot:
        await pilot.pause()
        assert reads == ["a" * 64]
        assert screen._revision_id == ("b" * 64 if available else None)
        assert isinstance(screen.app.screen, historical_export.WorkbenchExportScreen) is available


class _FilingViewController:
    """Stands in for the runtime controller; the read under test owns the sequence it is driven in."""

    submitted: list[dict[str, object]]
    settled_reads: list[tuple[object, object, int]]
    released = object()

    @classmethod
    async def submit(cls, _client: object, **kwargs: object) -> "_FilingViewController":
        cls.submitted.append(kwargs)
        return cls()

    async def start(self) -> None:
        return None

    async def read_settled_result(self, projection: object, result_type: object, *, result_version: int) -> object:
        self.settled_reads.append((projection, result_type, result_version))
        return self.released


def _filing_view_state(
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
) -> SimpleNamespace:
    return SimpleNamespace(terminal_condition=condition, effect=effect, refusal_ref=None, failure_error_code=None)


def _bind_filing_view_read(monkeypatch, state: SimpleNamespace) -> list[dict[str, object]]:
    waited: list[dict[str, object]] = []

    async def terminal(controller: object, **kwargs: object) -> SimpleNamespace:
        assert isinstance(controller, _FilingViewController)
        waited.append(kwargs)
        return state

    _FilingViewController.submitted = []
    _FilingViewController.settled_reads = []
    monkeypatch.setattr(runtime_workbench_reads, "OperationController", _FilingViewController)
    monkeypatch.setattr(runtime_workbench_reads, "await_terminal_projection", terminal)
    return waited


@pytest.mark.asyncio
async def test_historical_tui_reads_the_filing_view_at_its_current_result_version(monkeypatch) -> None:
    profile = UUID("22222222-2222-4222-8222-222222222222")
    client = SimpleNamespace(profile_id=profile, session_id=UUID("33333333-3333-4333-8333-333333333333"))
    state = _filing_view_state()
    waited = _bind_filing_view_read(monkeypatch, state)

    result = await historical_export.read_filing_view(cast(FrontendClient, client), "a" * 64)

    assert result is _FilingViewController.released
    (call,) = _FilingViewController.submitted
    assert call["definition_id"] == "modelo.filing_record.view"
    assert call["subject_ref"] == profile_operation_subject(str(profile))
    assert call["expected_session_id"] == client.session_id
    assert isinstance(call["payload"], ModeloFilingRecordViewRequest)
    assert (call["payload"].profile_id, call["payload"].filing_record_id) == (profile, "a" * 64)
    assert waited[0]["definition_id"] == "modelo.filing_record.view"
    assert waited[0]["request_schema"] == OperationSchemaIdentityV1.from_model(
        schema_id="modelo.filing_record.view.request", schema_version=1, model_type=ModeloFilingRecordViewRequest
    )
    assert _FilingViewController.settled_reads == [(state, ModeloFilingRecordViewProjection, 2)]
    assert ModeloFilingRecordViewProjection.model_fields["result_version"].default == 2


@pytest.mark.asyncio
async def test_historical_tui_reads_no_result_from_a_filing_view_that_was_refused_or_left_an_effect(
    monkeypatch,
) -> None:
    client = SimpleNamespace(
        profile_id=UUID("22222222-2222-4222-8222-222222222222"),
        session_id=UUID("33333333-3333-4333-8333-333333333333"),
    )

    _bind_filing_view_read(monkeypatch, _filing_view_state(condition=OperationTerminalCondition.REFUSED))
    with pytest.raises(FrontendRefusedError):
        await historical_export.read_filing_view(cast(FrontendClient, client), "a" * 64)
    assert _FilingViewController.settled_reads == []

    _bind_filing_view_read(monkeypatch, _filing_view_state(effect=OperationEffect.UPDATED))
    with pytest.raises(RefusalError):
        await historical_export.read_filing_view(cast(FrontendClient, client), "a" * 64)
    assert _FilingViewController.settled_reads == []

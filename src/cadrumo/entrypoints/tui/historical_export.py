"""Export the retained calculation belonging to a selected historical filing."""

from __future__ import annotations

from pathlib import Path
from typing import override

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.export.calculation_review_xlsx_operation import (
    CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
    CalculationReviewXlsxRequest,
    CalculationReviewXlsxResult,
)
from ...application.modelo.filing_record_view_operation import (
    MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
    ModeloFilingRecordViewProjection,
    ModeloFilingRecordViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from .modelo.export_result import ModeloExportResultScreen
from .modelo.runtime_workbench_reads import read_runtime_workbench_operation
from .modelo.workbench.export import WorkbenchExportScreen
from .modelo.workbench.ports import WorkbenchExportOffer, WorkbenchExportRequest
from .operations.modal import OperationModal, OperationModalSettledOutcomeV1
from .operations.runtime_controller import RuntimeOperationController


class HistoricalFilingExportScreen(Screen[None]):
    """Resolve one exact filing, then ask for an immutable review destination."""

    def __init__(self, client: RuntimeFrontendClient, filing_record_id: str) -> None:
        """Retain the authenticated client and exact selected filing identity."""
        super().__init__()
        self._client = client
        self._filing_record_id = filing_record_id
        self._revision_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("cli.app.modelo.filing_record.export_help"), markup=False)
        yield Static("", id="historical-export-notice", markup=False)
        yield Button(tr("tui.modelo.export.result.close"), id="historical-export-close")

    def on_mount(self) -> None:
        """Resolve retained historical content before offering a destination."""
        self.run_worker(self._read_selection(), group="historical-export-read")

    def _notice(self, text: str) -> None:
        self.query_one("#historical-export-notice", Static).update(text)

    async def _read_selection(self) -> None:
        client = self._client
        session_id = client.session_id
        try:
            projection = await read_runtime_workbench_operation(
                client,
                definition_id=MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(client.profile_id)),
                payload=ModeloFilingRecordViewRequest(
                    profile_id=client.profile_id, filing_record_id=self._filing_record_id
                ),
                result_type=ModeloFilingRecordViewProjection,
                session_id=session_id,
            )
            if (
                projection.profile_id != client.profile_id
                or projection.filing_record_id != self._filing_record_id
                or projection.record.filing_record_id != self._filing_record_id
                or projection.historical_content.calculation_revision_id != projection.record.calculation_revision_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if projection.historical_content.availability != "available":
                self._notice(tr("cli.app.modelo.filing_record.export_missing"))
                return
            self._revision_id = projection.record.calculation_revision_id
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        self.app.push_screen(
            WorkbenchExportScreen(
                WorkbenchExportOffer(
                    artefacts=(ModeloExportArtefact.CALCULATION_REVIEW_XLSX,),
                    asks_elections=False,
                )
            ),
            self._asked,
        )

    def _asked(self, request: WorkbenchExportRequest | None) -> None:
        if request is not None:
            self.run_worker(self._publish(request), group="historical-export-publication")

    async def _publish(self, request: WorkbenchExportRequest) -> None:
        client = self._client
        revision_id = self._revision_id
        if revision_id is None:
            self._notice(tr("cli.app.modelo.filing_record.export_missing"))
            return
        try:
            controller = await RuntimeOperationController.submit(
                client,
                definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(client.profile_id)),
                payload=CalculationReviewXlsxRequest(
                    profile_id=client.profile_id,
                    calculation_revision_id=revision_id,
                    filing_record_id=self._filing_record_id,
                    output_path=str(Path(request.output_path).resolve()),
                    replace_existing=request.replace_existing,
                    report_language=OutputLanguage(output_language()),
                ),
                expected_session_id=client.session_id,
            )
            await controller.start()
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return

        def settled(outcome: object) -> None:
            if isinstance(outcome, OperationModalSettledOutcomeV1):
                self.run_worker(self._show_result(controller, outcome, revision_id), group="historical-export-result")

        self.app.push_screen(OperationModal(controller), settled)

    async def _show_result(
        self, controller: RuntimeOperationController, outcome: OperationModalSettledOutcomeV1, revision_id: str
    ) -> None:
        projection = outcome.view_model.projection
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            return
        try:
            result = await controller.read_settled_result(projection, CalculationReviewXlsxResult, result_version=1)
            if result.profile_id != self._client.profile_id or result.calculation_revision_id != revision_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        self.app.push_screen(ModeloExportResultScreen(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return to the history without changing its selected filing."""
        if event.button.id == "historical-export-close":
            self.app.pop_screen()

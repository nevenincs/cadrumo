"""Ask where to publish the selected declaration's saved reconciliation reviews."""

from __future__ import annotations

from pathlib import Path
from typing import override

from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.modelo.reconciliation_export_operation import (
    RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
    ReconciliationExportXlsxProjection,
    ReconciliationExportXlsxRequest,
)
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from ....core.payment_election import PaymentElection
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ..modelo.workbench.ports import WorkbenchExportRequest
from ..operations.modal import OperationModal, OperationModalSettledOutcomeV1
from ..operations.runtime_controller import RuntimeOperationController


class ReconciliationDestinationScreen(ModalScreen[WorkbenchExportRequest | None]):
    """Collect a local destination for the explicitly selected saved comparisons."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("cli.app.modelo.reconcile.export_work_unit_scope"), markup=False)
        yield Input(
            placeholder=tr("application.modelo.lifecycle.export_destination_placeholder"),
            id="reconciliation-export-path",
        )
        yield Checkbox(tr("tui.modelo.export.replace_existing.label"), id="reconciliation-export-replace")
        yield Static("", id="reconciliation-export-notice", markup=False)
        yield Button(tr("application.modelo.lifecycle.export"), id="reconciliation-export-submit")
        yield Button(tr("tui.modelo.workbench.editor.cancel"), id="reconciliation-export-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the chosen path, or leave without publishing anything."""
        if event.button.id == "reconciliation-export-cancel":
            self.dismiss(None)
            return
        if event.button.id != "reconciliation-export-submit":
            return
        path = self.query_one("#reconciliation-export-path", Input).value.strip()
        if not path:
            self.query_one("#reconciliation-export-notice", Static).update(
                tr("application.modelo.lifecycle.refusal.export_destination_required")
            )
            return
        self.dismiss(
            WorkbenchExportRequest(
                output_path=path,
                artefact=ModeloExportArtefact.CALCULATION_REVIEW_XLSX,
                refund_election=RefundElection.COMPENSAR,
                payment_election=PaymentElection.INGRESO,
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                replace_existing=self.query_one("#reconciliation-export-replace", Checkbox).value,
            )
        )


class ReconciliationExportScreen(Screen[None]):
    """Publish stored differences for an exact work unit through its profile worker."""

    def __init__(self, client: RuntimeFrontendClient, work_unit_id: str) -> None:
        """Retain the authenticated profile and explicit saved-review work selector."""
        super().__init__()
        self._client = client
        self._work_unit_id = work_unit_id

    def on_mount(self) -> None:
        """Ask for a destination after the operator chose the declaration."""
        self.app.push_screen(ReconciliationDestinationScreen(), self._asked)

    def _notice(self, text: str) -> None:
        self.query_one("#reconciliation-result-notice", Static).update(text)

    def _asked(self, request: WorkbenchExportRequest | None) -> None:
        if request is not None:
            self.run_worker(self._publish(request), group="reconciliation-export-publication")

    async def _publish(self, request: WorkbenchExportRequest) -> None:
        client = self._client
        try:
            controller = await RuntimeOperationController.submit(
                client,
                definition_id=RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(client.profile_id)),
                payload=ReconciliationExportXlsxRequest(
                    profile_id=client.profile_id,
                    work_unit_id=self._work_unit_id,
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
                self.run_worker(self._show_result(controller, outcome), group="reconciliation-export-result")

        self.app.push_screen(OperationModal(controller), settled)

    async def _show_result(
        self, controller: RuntimeOperationController, outcome: OperationModalSettledOutcomeV1
    ) -> None:
        projection = outcome.view_model.projection
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            return
        try:
            result = await controller.read_settled_result(
                projection, ReconciliationExportXlsxProjection, result_version=1
            )
            if (
                result.profile_id != self._client.profile_id
                or result.work_unit_id != self._work_unit_id
                or result.all_history
            ):
                self._notice(tr("operation.modal.terminal.failed"))
                return
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        self._notice(f"{result.title}\n{result.output_path}\n{tr('tui.modelo.export.result.warning.not_official')}")

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("cli.app.modelo.reconcile.export_work_unit_scope"), markup=False)
        yield Static("", id="reconciliation-result-notice", markup=False)
        yield Button(tr("tui.modelo.export.result.close"), id="reconciliation-result-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return to the selected declaration's history."""
        if event.button.id == "reconciliation-result-close":
            self.app.pop_screen()

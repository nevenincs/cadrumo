"""Read one declaration's workbench through the authenticated TUI runtime session.

Each read is a separately recorded worker operation: submitted, started,
observed to its terminal state and released as its registered typed result.
The session and profile captured when the workbench opened must still own the
connection, and every result must name that profile and declaration, before
anything reaches the screen. Losing this observer never cancels the worker's
read; it only discards the answer.
"""

from __future__ import annotations

import asyncio
import time
from threading import Lock

from cadrumo.application.modelo.casilla_help import ModeloCasillaHelpCardV1
from cadrumo.application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from cadrumo.application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
)
from cadrumo.application.modelo.workbench_operations import (
    MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloCasillaHelpProjectionV1,
    ModeloCasillaHelpRequest,
    ModeloWorkbenchFormRequest,
)
from cadrumo.application.modelo.workbench_projection import (
    ModeloWorkbenchFormProjectionV1,
    restore_modelo_workbench_form,
)
from cadrumo.application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection
from cadrumo_client.transport.operation_reads import read_operation

READ_TIMEOUT_SECONDS = 120.0


class RuntimeModeloWorkbenchSource:
    """Read one declaration's form and casilla help for the workbench, through one runtime session.

    Both reads are synchronous because the workbench calls them off its event
    loop; each runs its own short-lived loop on that worker thread.
    """

    def __init__(self, client: FrontendClient, declaration: DeclarationsWorkspaceDeclarationRefV1) -> None:
        """Pin the TUI session, its profile and the one declaration this workbench shows."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._work_unit_id = str(declaration.work_unit_id)
        self._modelo, self._filing_year = str(declaration.modelo), declaration.filing_year
        self._help_read_lock = Lock()

    def _require_session(self) -> None:
        if self._client.session_id != self._session_id or self._client.profile_id != self._profile_id:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def read_form(self, language: OutputLanguage) -> ModeloWorkbenchFormReadV1:
        """Read the form and admit its edit baseline in the worker."""
        self._require_session()
        projection = asyncio.run(
            read_operation(
                self._client,
                definition_id=MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
                subject_ref=self._work_unit_id,
                payload=ModeloWorkbenchFormRequest(
                    profile_id=self._profile_id, work_unit_id=self._work_unit_id, output_language=language
                ),
                result_type=ModeloWorkbenchFormProjectionV1,
                session_id=self._session_id,
            )
        )
        if projection.profile_id != self._profile_id or projection.work_unit_id != self._work_unit_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._require_session()
        return restore_modelo_workbench_form(projection)

    def help_card(
        self,
        casilla_id: CasillaId,
        *,
        registry_revision_id: str,
        calculation_revision_id: str | None,
        language: OutputLanguage,
    ) -> ModeloCasillaHelpCardV1:
        """Assemble one casilla's help in the worker, for the revision and calculation the form showed."""
        # Cancellation of the UI observer cannot stop its worker thread.
        # Serialize until that read returns, sharing one queue/read deadline.
        deadline = time.monotonic() + READ_TIMEOUT_SECONDS
        if not self._help_read_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RefusalError(RefusalCode.TIMEOUT)
        try:
            self._require_session()
            projection = asyncio.run(
                read_operation(
                    self._client,
                    definition_id=MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
                    subject_ref=self._work_unit_id,
                    payload=ModeloCasillaHelpRequest(
                        profile_id=self._profile_id,
                        work_unit_id=self._work_unit_id,
                        casilla_id=casilla_id,
                        registry_revision_id=registry_revision_id,
                        calculation_revision_id=calculation_revision_id,
                        output_language=language,
                    ),
                    result_type=ModeloCasillaHelpProjectionV1,
                    session_id=self._session_id,
                    deadline=deadline,
                )
            )
            if (
                projection.profile_id != self._profile_id
                or projection.work_unit_id != self._work_unit_id
                or projection.card.casilla_id != casilla_id
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            self._require_session()
            return projection.card
        finally:
            self._help_read_lock.release()

    def compare_taxation(self) -> ModeloTaxationComparisonProjection:
        """Read the declaration's joint and individual comparison; a refusal raises the error it recorded.

        The comparison is a recorded, nonmutating read of the profile's work
        unit. It shares the help reads' queue, because an observer that is
        cancelled cannot stop its worker thread.
        """
        deadline = time.monotonic() + READ_TIMEOUT_SECONDS
        if not self._help_read_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RefusalError(RefusalCode.TIMEOUT)
        try:
            self._require_session()
            projection = asyncio.run(self._read_comparison(deadline))
            if (
                projection.profile_id != self._profile_id
                or projection.work_unit_id != self._work_unit_id
                or projection.modelo != self._modelo
                or projection.filing_year != self._filing_year
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            self._require_session()
            return projection
        finally:
            self._help_read_lock.release()

    async def _read_comparison(self, deadline: float) -> ModeloTaxationComparisonProjection:
        definition_id = MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID
        subject_ref = profile_operation_subject(str(self._profile_id))
        payload = ModeloTaxationComparisonRequest(profile_id=self._profile_id, work_unit_id=self._work_unit_id)
        controller = await OperationController.submit(
            self._client,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            deadline=deadline,
            expected_session_id=self._session_id,
        )
        await controller.start()
        terminal = await await_terminal_projection(
            controller,
            definition_id=definition_id,
            subject_ref=subject_ref,
            request_schema=OperationSchemaIdentityV1.from_model(
                schema_id=f"{definition_id}.request", schema_version=1, model_type=ModeloTaxationComparisonRequest
            ),
            deadline=deadline,
        )
        if terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            detail = await controller.settled_error_detail(terminal)
            recorded = None if detail is None else detail.recorded_error()
            if recorded is not None:
                raise recorded
            raise FrontendRefusedError(
                terminal.refusal_ref or terminal.failure_error_code or "operation_not_successful"
            )
        if terminal.effect is not OperationEffect.NONE:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return await controller.read_settled_result(terminal, ModeloTaxationComparisonProjection, result_version=1)


__all__ = ["RuntimeModeloWorkbenchSource"]

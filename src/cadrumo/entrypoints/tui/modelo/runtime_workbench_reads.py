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
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.workbench_operations import (
    MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloCasillaHelpProjectionV1,
    ModeloCasillaHelpRequest,
    ModeloWorkbenchFormRequest,
)
from ....application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1, restore_modelo_workbench_form
from ....application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.casilla_id import CasillaId
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..operations.runtime_controller import RuntimeOperationController, await_terminal_projection

_READ_TIMEOUT_SECONDS = 120.0


async def read_runtime_workbench_operation[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    *,
    definition_id: str,
    subject_ref: str,
    payload: BaseModel,
    result_type: type[ResultT],
    session_id: UUID,
) -> ResultT:
    """Run one recorded read-only worker operation to its terminal state and return its typed result."""
    deadline = time.monotonic() + _READ_TIMEOUT_SECONDS
    controller = await RuntimeOperationController.submit(
        client,
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload=payload,
        deadline=deadline,
        expected_session_id=session_id,
    )
    await controller.start()
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=definition_id + ".request", schema_version=1, model_type=type(payload)
    )
    state = await await_terminal_projection(
        controller,
        definition_id=definition_id,
        subject_ref=subject_ref,
        request_schema=expected_request,
        deadline=deadline,
        poll_seconds=0.02,
    )
    if state.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise RuntimeFrontendRefusedError(
            state.refusal_ref
            or state.failure_error_code
            or (state.terminal_condition.value if state.terminal_condition is not None else "operation_unavailable")
        )
    if state.effect is not OperationEffect.NONE:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return await controller.read_settled_result(state, result_type, result_version=1)


class RuntimeModeloWorkbenchSource:
    """Read one declaration's form and casilla help for the workbench, through one runtime session.

    Both reads are synchronous because the workbench calls them off its event
    loop; each runs its own short-lived loop on that worker thread.
    """

    def __init__(self, client: RuntimeFrontendClient, declaration: DeclarationsWorkspaceDeclarationRefV1) -> None:
        """Pin the TUI session, its profile and the one declaration this workbench shows."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._work_unit_id = str(declaration.work_unit_id)

    def _require_session(self) -> None:
        if self._client.session_id != self._session_id or self._client.profile_id != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def read_form(self, language: OutputLanguage) -> ModeloWorkbenchFormReadV1:
        """Read the form and admit its edit baseline in the worker."""
        self._require_session()
        projection = asyncio.run(
            read_runtime_workbench_operation(
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
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
        self._require_session()
        projection = asyncio.run(
            read_runtime_workbench_operation(
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
            )
        )
        if (
            projection.profile_id != self._profile_id
            or projection.work_unit_id != self._work_unit_id
            or projection.card.casilla_id != casilla_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._require_session()
        return projection.card


__all__ = ["RuntimeModeloWorkbenchSource", "read_runtime_workbench_operation"]

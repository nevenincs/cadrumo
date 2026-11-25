"""List and answer one declaration's source disagreements through the authenticated TUI runtime session.

Each call is a separately recorded worker operation, run to its terminal state
and released as its registered typed result. The session and profile captured
when the workbench opened must still own the connection, and every result must
name that profile and the calculation revision asked about, before anything
reaches the screen. A transport failure while an answer is being sent leaves its
effect unknown; it is raised, never settled here as a refusal.
"""

from __future__ import annotations

import asyncio
import time

from pydantic import BaseModel

from cadrumo.application.modelo.credit_resolution_contracts import (
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
    CreditResolutionAcceptRequest,
    CreditResolutionListProjection,
    CreditResolutionListRequest,
    CreditResolutionMutationProjection,
    CreditResolutionRevokeRequest,
)
from cadrumo.application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection
from cadrumo_client.transport.operation_reads import read_operation

SETTLEMENT_SECONDS = 120.0


class RuntimeModeloDisagreements:
    """Bind the disagreements operations to one declaration and one TUI runtime session."""

    def __init__(self, client: FrontendClient, declaration: DeclarationsWorkspaceDeclarationRefV1) -> None:
        """Pin the TUI session, its profile and the one declaration this workbench shows."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id
        self._work_unit_id = str(declaration.work_unit_id)

    def _require_session(self) -> None:
        if self._client.session_id != self._session_id or self._client.profile_id != self._profile_id:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def list_answers(self, calculation_revision_id: str, language: OutputLanguage) -> CreditResolutionListProjection:
        """Read every answer the declaration holds, active and taken back."""
        self._require_session()
        projection = asyncio.run(
            read_operation(
                self._client,
                definition_id=MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
                subject_ref=self._work_unit_id,
                payload=CreditResolutionListRequest(
                    profile_id=self._profile_id,
                    calculation_revision_id=calculation_revision_id,
                    output_language=language,
                ),
                result_type=CreditResolutionListProjection,
                session_id=self._session_id,
                deadline=time.monotonic() + SETTLEMENT_SECONDS,
            )
        )
        if projection.profile_id != self._profile_id or projection.calculation_revision_id != calculation_revision_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._require_session()
        return projection

    def accept(
        self, calculation_revision_id: str, finding_id: str, reason: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        """Accept the amount the calculation used for one disagreement, giving the operator's reason."""
        return self._answer(
            MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
            CreditResolutionAcceptRequest(
                profile_id=self._profile_id,
                calculation_revision_id=calculation_revision_id,
                output_language=language,
                finding_id=finding_id,
                reason=reason,
            ),
            "accepted",
        )

    def revoke(
        self, calculation_revision_id: str, finding_id: str, expected_revision_id: str, language: OutputLanguage
    ) -> CreditResolutionMutationProjection:
        """Take back the active answer to one disagreement, guarded by the revision it is stored at."""
        return self._answer(
            MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
            CreditResolutionRevokeRequest(
                profile_id=self._profile_id,
                calculation_revision_id=calculation_revision_id,
                output_language=language,
                finding_id=finding_id,
                expected_revision_id=expected_revision_id,
            ),
            "revoked",
        )

    def _answer(
        self, definition_id: str, payload: BaseModel, stored_outcome: str
    ) -> CreditResolutionMutationProjection:
        self._require_session()
        projection = asyncio.run(self._settle(definition_id, payload, stored_outcome))
        if projection.profile_id != self._profile_id or projection.calculation_revision_id != getattr(
            payload, "calculation_revision_id", None
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._require_session()
        return projection

    async def _settle(
        self, definition_id: str, payload: BaseModel, stored_outcome: str
    ) -> CreditResolutionMutationProjection:
        deadline = time.monotonic() + SETTLEMENT_SECONDS
        controller = await OperationController.submit(
            self._client,
            definition_id=definition_id,
            subject_ref=self._work_unit_id,
            payload=payload,
            deadline=deadline,
            expected_session_id=self._session_id,
        )
        await controller.start()
        state = await await_terminal_projection(
            controller,
            definition_id=definition_id,
            subject_ref=self._work_unit_id,
            request_schema=OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".request", schema_version=1, model_type=type(payload)
            ),
            deadline=deadline,
        )
        stored = state.terminal_condition is OperationTerminalCondition.SUCCEEDED and (
            state.effect is OperationEffect.UPDATED
        )
        refused = (
            state.terminal_condition is OperationTerminalCondition.REFUSED
            and state.effect is OperationEffect.NONE
            and state.refusal_ref in state.definition_contract.refusal_detail_codes
        )
        if not (stored or refused):
            raise FrontendRefusedError(
                state.refusal_ref
                or state.failure_error_code
                or (state.terminal_condition.value if state.terminal_condition is not None else "operation_unavailable")
            )
        projection = await controller.read_settled_result(
            state, CreditResolutionMutationProjection, result_version=1, allow_refusal_detail=True
        )
        if projection.outcome != ("refused" if refused else stored_outcome):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return projection


__all__ = ["RuntimeModeloDisagreements"]

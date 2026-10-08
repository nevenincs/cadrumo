"""Bind Modelo lifecycle actions to one retained authenticated TUI runtime."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.export.calculation_review_xlsx_operation import (
    CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
    CalculationReviewXlsxRequest,
    CalculationReviewXlsxResult,
)
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.edit_admission import ModeloEditRenewalResultV1, ModeloEditRenewedV1
from ....application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ....application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1
from ....application.modelo.edit_models import ModeloEditBaselineV1, ModeloEditPreflightResultV1, ModeloEditSubmissionV1
from ....application.modelo.edit_operation_requests import ModeloEditPreflightRequestV2
from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ....application.modelo.export_projection import ModeloExportPublicResultV3
from ....application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ....application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ....application.modelo.workbench_operations import (
    MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
    ModeloEditApplyPrerequisiteProjectionV1,
    ModeloEditApplyPrerequisiteRequest,
    ModeloEditApplyPrerequisiteV1,
    ModeloEditPreflightProjectionV1,
    ModeloEditRenewalProjectionV1,
    ModeloEditRenewRequest,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.models import OperationRequest
from ....application.operations.registry import OperationFrontendProjection
from ....application.operations.schema_identity import OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.controller_port import OperationControllerPort
from ..operations.runtime_controller import RuntimeOperationController, await_terminal_projection
from .lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor
from .runtime_workbench_reads import read_runtime_workbench_operation

_ATTESTATION_ACTOR = "operator:tui-modelo"
_ATTESTATION_TIMEOUT_SECONDS = 60.0


def _require_attestation_update(state: OperationPublicProjectionV1, operation_id: str) -> None:
    terminal_effect = state.effect
    if (
        state.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or terminal_effect is not OperationEffect.UPDATED
    ):
        raise ModeloLifecycleActionUnavailableError(
            state.refusal_ref or state.failure_error_code or state.terminal_condition.value
            if state.terminal_condition is not None
            else "operation_terminal_unknown",
            context={
                "operation_id": operation_id,
                "terminal_condition": state.terminal_condition.value if state.terminal_condition else "unknown",
                "effect": (terminal_effect or OperationEffect.UNKNOWN).value,
            },
        )


def _attestation_admission(
    receipt: ModeloWorkM303AttestationPublicResultV2,
    client: RuntimeFrontendClient,
    declaration: DeclarationsWorkspaceDeclarationRefV1,
    work_unit_id: str,
    expected_session_id: UUID,
) -> M303Exonerado390ApplicabilityAttestationAdmission:
    if (
        receipt.profile_id != client.profile_id
        or receipt.work_unit_id != work_unit_id
        or receipt.filing_year != declaration.filing_year
        or receipt.period.to_period() != declaration.period
        or client.session_id != expected_session_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return receipt.to_admission()


async def _admit_attestation(
    client: RuntimeFrontendClient,
    declaration: DeclarationsWorkspaceDeclarationRefV1,
    observed_at: datetime,
    expected_session_id: UUID,
) -> M303Exonerado390ApplicabilityAttestationAdmission:
    work_unit_id = str(declaration.work_unit_id)
    if client.session_id != expected_session_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    deadline = time.monotonic() + _ATTESTATION_TIMEOUT_SECONDS
    payload = ModeloWorkM303AttestationRequest(
        profile_id=client.profile_id,
        work_unit_id=work_unit_id,
        observed_at=observed_at,
        actor=_ATTESTATION_ACTOR,
    )
    controller = await RuntimeOperationController.submit(
        client,
        definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=payload,
        deadline=deadline,
        expected_session_id=expected_session_id,
    )
    terminal_effect: OperationEffect | None = None
    try:
        await controller.start()
        state = await await_terminal_projection(
            controller,
            definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
            subject_ref=work_unit_id,
            request_schema=OperationSchemaIdentityV1.from_model(
                schema_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID + ".request",
                schema_version=2,
                model_type=ModeloWorkM303AttestationRequest,
            ),
            deadline=deadline,
        )
        terminal_effect = state.effect
        _require_attestation_update(state, str(controller.operation_id))
        receipt = await controller.read_settled_result(
            state,
            ModeloWorkM303AttestationPublicResultV2,
            result_version=2,
        )
        return _attestation_admission(receipt, client, declaration, work_unit_id, expected_session_id)
    except (RuntimeRefusalError, RuntimeFrontendRefusedError) as error:
        raise ModeloLifecycleActionUnavailableError(
            error.reason.value if isinstance(error, RuntimeRefusalError) else error.reason,
            context={
                "operation_id": str(controller.operation_id),
                "effect": (terminal_effect or OperationEffect.UNKNOWN).value,
            },
        ) from None


@dataclass(frozen=True, slots=True)
class _RuntimeModeloLifecycleBindings:
    client: RuntimeFrontendClient
    declaration: DeclarationsWorkspaceDeclarationRefV1
    work_unit_id: str
    profile_id: UUID
    session_id: UUID

    def require_session(self) -> None:
        if self.client.session_id != self.session_id or self.client.profile_id != self.profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def read[ResultT: BaseModel](self, definition_id: str, payload: BaseModel, result_type: type[ResultT]) -> ResultT:
        self.require_session()
        result = asyncio.run(
            read_runtime_workbench_operation(
                self.client,
                definition_id=definition_id,
                subject_ref=self.work_unit_id,
                payload=payload,
                result_type=result_type,
                session_id=self.session_id,
                financial_input=isinstance(payload, ModeloEditOperatorInputV2),
                request_model=ModeloEditPreflightRequestV2 if isinstance(payload, ModeloEditOperatorInputV2) else None,
                request_version=2 if isinstance(payload, ModeloEditOperatorInputV2) else 1,
            )
        )
        self.require_session()
        return result

    async def submit(self, request: OperationRequest[BaseModel]) -> OperationControllerPort:
        expected_subject = (
            profile_operation_subject(str(self.profile_id))
            if request.definition_id == CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID
            and isinstance(request.payload, CalculationReviewXlsxRequest)
            and request.payload.profile_id == self.profile_id
            else self.work_unit_id
        )
        if self.client.session_id != self.session_id or request.subject_ref != expected_subject:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return await RuntimeOperationController.submit(
            self.client,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
            financial_input=isinstance(request.payload, ModeloEditOperatorInputV2),
            expected_session_id=self.session_id,
        )

    async def read_export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV3:
        if self.client.session_id != self.session_id or projection.subject_ref != self.work_unit_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        controller = RuntimeOperationController(
            client=self.client,
            operation_id=projection.operation_id,
            session_id=self.session_id,
        )
        return await controller.read_settled_result(projection, ModeloExportPublicResultV3, result_version=3)

    async def read_review_result(self, projection: OperationPublicProjectionV1) -> CalculationReviewXlsxResult:
        if (
            self.client.session_id != self.session_id
            or projection.definition_id != CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID
            or projection.subject_ref != profile_operation_subject(str(self.profile_id))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        controller = RuntimeOperationController(
            client=self.client, operation_id=projection.operation_id, session_id=self.session_id
        )
        result = await controller.read_settled_result(projection, CalculationReviewXlsxResult, result_version=1)
        if result.profile_id != self.profile_id or result.work_unit_id != self.work_unit_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result

    def admit(self, observed_at: datetime) -> M303Exonerado390ApplicabilityAttestationAdmission:
        self.require_session()
        return asyncio.run(_admit_attestation(self.client, self.declaration, observed_at, self.session_id))

    def renew(self, baseline: ModeloEditBaselineV1) -> ModeloEditRenewalResultV1:
        projection = self.read(
            MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
            ModeloEditRenewRequest(
                profile_id=self.profile_id,
                baseline=ModeloEditApplyBaselineV1.from_baseline(baseline),
            ),
            ModeloEditRenewalProjectionV1,
        )
        if projection.profile_id != self.profile_id or projection.work_unit_id != self.work_unit_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        renewed = projection.renewed_baseline
        if renewed is not None:
            return ModeloEditRenewedV1(baseline=renewed.to_baseline())
        if projection.refusal is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return projection.refusal

    def preflight(self, submission: ModeloEditSubmissionV1) -> ModeloEditPreflightResultV1:
        projection = self.read(
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(submission=ModeloEditApplySubmissionV1.from_submission(submission)),
            ModeloEditPreflightProjectionV1,
        )
        if projection.profile_id != self.profile_id or projection.work_unit_id != self.work_unit_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return projection.outcome

    def prerequisite(
        self,
        operation_id: str,
        baseline: ModeloEditBaselineV1,
        registry_revision_id: str,
    ) -> ModeloEditApplyPrerequisiteV1 | None:
        projection = self.read(
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            ModeloEditApplyPrerequisiteRequest(
                profile_id=self.profile_id,
                work_unit_id=self.work_unit_id,
                apply_operation_id=operation_id,
                baseline_id=baseline.baseline_id,
                calculation_revision_id=baseline.current_calculation_revision_id,
                registry_revision_id=registry_revision_id,
            ),
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        if projection.profile_id != self.profile_id or projection.work_unit_id != self.work_unit_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return projection.prerequisite


def compose_runtime_modelo_lifecycle_door(
    client: RuntimeFrontendClient,
    declaration: DeclarationsWorkspaceDeclarationRefV1,
    *,
    calculation_revision_id: str | None,
    verification_report_id: str | None,
    asks_modelo_390: bool,
    refresh_after_success: Callable[[], object] | None = None,
) -> ModeloWorkspaceLifecycleDoor:
    """Return the lifecycle door of one declaration, bound to one TUI session and its worker.

    The calculation head, its granting verification report and whether the
    Modelo 390 question is asked are the ones the workbench's latest form read
    found, so every action acts on the revision the filer is looking at.
    """
    if client.frontend is not OperationFrontendProjection.TUI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    work_unit_id = str(declaration.work_unit_id)
    bindings = _RuntimeModeloLifecycleBindings(
        client=client,
        declaration=declaration,
        work_unit_id=work_unit_id,
        profile_id=client.profile_id,
        session_id=client.session_id,
    )

    return ModeloWorkspaceLifecycleDoor(
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        verification_report_id=verification_report_id,
        refresh_after_success=refresh_after_success,
        edit_renewal=bindings.renew,
        edit_preflight=bindings.preflight,
        apply_prerequisite=bindings.prerequisite,
        m303_exonerado_390_attestation_admission=(bindings.admit if str(declaration.modelo) == "303" else None),
        asks_modelo_390=asks_modelo_390,
        submit_operation=bindings.submit,
        read_export_result=bindings.read_export_result,
        profile_id=client.profile_id,
        read_review_result=bindings.read_review_result,
    )


__all__ = ["compose_runtime_modelo_lifecycle_door"]

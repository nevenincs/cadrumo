"""Bind Modelo lifecycle actions to one retained authenticated TUI runtime."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ....application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ....application.modelo.workspace_models import ModeloWorkspaceLifecycleProjectionV1
from ....application.operations.frontend_requests import OperationObservationRefusalV1, OperationObservationSuccessV1
from ....application.operations.models import OperationRequest
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ..operations.controller_port import OperationControllerPort
from ..operations.runtime_controller import RuntimeOperationController
from .lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor

_ATTESTATION_ACTOR = "operator:tui-modelo"
_ATTESTATION_TIMEOUT_SECONDS = 60.0


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


async def _admit_attestation(
    client: RuntimeFrontendClient,
    lifecycle: ModeloWorkspaceLifecycleProjectionV1,
    observed_at: datetime,
    expected_session_id: UUID,
) -> M303Exonerado390ApplicabilityAttestationAdmission:
    work_unit_id = lifecycle.target.work_unit_id
    if work_unit_id is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
        while True:
            _remaining(deadline)
            observed = await controller.observe(0, page_limit=1)
            if isinstance(observed, OperationObservationRefusalV1):
                raise RuntimeFrontendRefusedError(observed.code.value)
            if not isinstance(observed, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            state = observed.projection
            expected_request = OperationSchemaIdentityV1.from_model(
                schema_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID + ".request",
                schema_version=2,
                model_type=ModeloWorkM303AttestationRequest,
            )
            if (
                state.operation_id != controller.operation_id
                or state.definition_id != MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID
                or state.subject_ref != work_unit_id
                or state.definition_contract.request_schema != expected_request
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if state.lifecycle is OperationLifecycle.TERMINAL:
                terminal_effect = state.effect
                break
            await asyncio.sleep(min(0.05, _remaining(deadline)))
        if (
            state.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or terminal_effect is not OperationEffect.UPDATED
        ):
            raise ModeloLifecycleActionUnavailableError(
                state.refusal_ref or state.failure_error_code or state.terminal_condition.value
                if state.terminal_condition is not None
                else "operation_terminal_unknown",
                context={
                    "operation_id": str(controller.operation_id),
                    "terminal_condition": state.terminal_condition.value if state.terminal_condition else "unknown",
                    "effect": (terminal_effect or OperationEffect.UNKNOWN).value,
                },
            )
        receipt = await controller.read_settled_result(
            state,
            ModeloWorkM303AttestationPublicResultV2,
            result_version=2,
        )
        if (
            receipt.profile_id != client.profile_id
            or receipt.work_unit_id != work_unit_id
            or receipt.filing_year != lifecycle.target.filing_year
            or receipt.period.to_period() != lifecycle.target.period
            or client.session_id != expected_session_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return receipt.to_admission()
    except (RuntimeRefusalError, RuntimeFrontendRefusedError) as error:
        raise ModeloLifecycleActionUnavailableError(
            error.reason.value if isinstance(error, RuntimeRefusalError) else error.reason,
            context={
                "operation_id": str(controller.operation_id),
                "effect": (terminal_effect or OperationEffect.UNKNOWN).value,
            },
        ) from None


def compose_runtime_modelo_lifecycle_door(
    client: RuntimeFrontendClient,
    lifecycle: ModeloWorkspaceLifecycleProjectionV1,
    *,
    refresh_after_success: Callable[[], object] | None = None,
) -> ModeloWorkspaceLifecycleDoor:
    """Return the existing lifecycle door bound to one TUI session and worker."""
    target = lifecycle.target
    work_unit_id = target.work_unit_id
    if (
        client.frontend is not OperationFrontendProjection.TUI
        or target.bucket_id != str(client.profile_id)
        or work_unit_id is None
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    session_id = client.session_id

    async def submit(request: OperationRequest[BaseModel]) -> OperationControllerPort:
        if (
            client.session_id != session_id
            or request.subject_ref != work_unit_id
            or target.bucket_id != str(client.profile_id)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return await RuntimeOperationController.submit(
            client,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
            expected_session_id=session_id,
        )

    def admit(observed_at: datetime) -> M303Exonerado390ApplicabilityAttestationAdmission:
        if client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return asyncio.run(_admit_attestation(client, lifecycle, observed_at, session_id))

    return ModeloWorkspaceLifecycleDoor(
        work_unit_id=work_unit_id,
        calculation_revision_id=lifecycle.calculation_revision_id,
        verification_report_id=lifecycle.verification_report_id,
        refresh_after_success=refresh_after_success,
        edit_baseline=lifecycle.edit_baseline.to_baseline() if lifecycle.edit_baseline is not None else None,
        m303_exonerado_390_attestation_admission=admit if str(target.modelo) == "303" else None,
        asks_modelo_390=lifecycle.asks_modelo_390,
        submit_operation=submit,
    )


__all__ = ["compose_runtime_modelo_lifecycle_door"]

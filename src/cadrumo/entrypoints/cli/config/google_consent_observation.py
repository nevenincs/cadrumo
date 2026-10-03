"""Canonical google consent observation stages for the human terminal."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from ....application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmitted,
)
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
)
from ....core.hashing import canonical_json_bytes
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from ..registered_operation_errors import submitted_operation_error
from .google_consent_exchange import google_consent_exchange, google_consent_remaining


def start_google_consent(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    submitted: RuntimeOperationSubmitted,
    operation_id: str,
    deadline: float,
) -> None:
    """Start google consent."""
    if submitted.receipt.secret_requirement is not None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    started = google_consent_exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
        deadline,
    )
    if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def observe_google_consent(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    operation_id: str,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> OperationPublicProjectionV1:
    """Observe google consent."""
    observed = google_consent_exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationObserve(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
        ),
        deadline,
    )
    if not isinstance(observed, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(observed.observation, OperationObservationRefusalV1):
        raise RuntimeFrontendRefusedError(observed.observation.code.value)
    if not isinstance(observed.observation, OperationObservationSuccessV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    state = observed.observation.projection
    if (
        state.operation_id != operation_id
        or state.definition_id != GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        or state.subject_ref != subject_ref
        or state.definition_contract != contract
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return state


def require_google_consent_settlement(
    operation_id: str,
    state: OperationPublicProjectionV1,
    condition: OperationTerminalCondition | None,
    effect: OperationEffect | None,
    refusal_code: str | None,
    contract: OperationPublicDefinitionContractV1,
) -> OperationTerminalCondition:
    """Require google consent settlement."""
    if condition is None or (
        condition is not OperationTerminalCondition.SUCCEEDED
        and not (condition is OperationTerminalCondition.REFUSED and refusal_code in contract.refusal_detail_codes)
    ):
        raise submitted_operation_error(
            operation_id,
            state.refusal_ref or state.failure_error_code or "unknown",
            terminal_condition=condition,
            effect=effect,
            refusal_code=refusal_code,
        )
    return condition


def read_google_consent_result(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    operation_id: str,
    state: OperationPublicProjectionV1,
    contract: OperationPublicDefinitionContractV1,
    expected_result: OperationSchemaIdentityV1,
    deadline: float,
) -> GoogleConfigurationOutcome:
    """Read google consent result."""
    document = client.read_result_document(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=state.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=expected_result,
        ),
        timeout=google_consent_remaining(deadline),
    )
    if document.get("outcome") == "refused":
        refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(document))
        raise RuntimeFrontendRefusedError(refusal.code.value)
    # CAST-RATIONALE-GOOGLE-CONSENT-RESULT: runtime Pydantic specialization
    # binds the exact closed outcome despite the broader generic stub.
    success_type = cast(
        "type[OperationResultProjectionSuccessV1[GoogleConfigurationOutcome]]",
        OperationResultProjectionSuccessV1.__class_getitem__(GoogleConfigurationOutcome),
    )
    success = success_type.model_validate_json(canonical_json_bytes(document))
    if (
        success.result_schema != expected_result
        or success.definition_contract_digest != contract.definition_contract_digest
        or success.projection.profile_id != profile_id
        or client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return success.projection

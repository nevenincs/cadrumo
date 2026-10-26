"""Validate exact registered CLI contracts, private payload bounds and secret admission."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationReviewHandler
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import exchange_timeout
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationReply,
    OperationRequest,
    OperationSubmitted,
)
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from cadrumo_client.transport.frontend_client import FrontendClient


def require_registered_definition_contract(
    contract: OperationPublicDefinitionContractV1,
    definition_id: str,
    expected_request: OperationSchemaIdentityV1,
    expected_result: OperationSchemaIdentityV1,
    secret: bytearray | None,
) -> None:
    """Require exact payload, result and secret admission contracts."""
    if (
        contract.definition_id != definition_id
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or contract.ephemeral_secret_required is not (secret is not None)
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)


def require_registered_review_contract[ReviewT: BaseModel](
    contract: OperationPublicDefinitionContractV1, review: RegisteredOperationReviewHandler[ReviewT] | None
) -> None:
    """Require the declared review and response schemas to match the typed handler."""
    if review is not None and (
        contract.review_projection_schema != review.review_schema
        or contract.interaction_response_schema != review.response_schema
        or review.review_schema
        != OperationSchemaIdentityV1.from_model(
            schema_id=review.review_schema.schema_id,
            schema_version=review.review_schema.schema_version,
            model_type=review.review_type,
        )
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)


def encode_registered_payload(payload: BaseModel) -> str:
    """Bound encoded private payload bytes before runtime submission."""
    try:
        payload_json = payload.model_dump_json()
        payload_size = len(payload_json.encode("utf-8"))
    except (UnicodeError, ValueError):
        raise RefusalError(RefusalCode.INVALID_FRAME) from None
    if payload_size > SUBMISSION_PAYLOAD_MAX_BYTES:
        # Refuse before Pydantic can retain a long private row in its error.
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return payload_json


def submit_registered_secret(
    client: FrontendClient,
    submitted: OperationSubmitted,
    operation_id: OperationId,
    definition_id: str,
    subject_ref: str,
    secret: bytearray | None,
    call_deadline: Callable[[], float],
) -> None:
    """Submit a one-shot secret only after its exact operation and subject requirement is correlated."""
    requirement = submitted.receipt.secret_requirement
    if (requirement is None) is not (secret is None):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if requirement is not None and secret is not None:
        if (
            requirement.identity.operation_id != operation_id
            or requirement.identity.definition_id != definition_id
            or requirement.identity.subject_ref != subject_ref
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        acknowledged = client.submit_secret(requirement, secret, timeout=exchange_timeout(call_deadline()))
        if acknowledged.operation_id != operation_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)


def start_registered_operation(
    operation_id: OperationId,
    profile_id: UUID,
    session_id: UUID,
    exchange: Callable[[OperationRequest], OperationReply],
) -> None:
    """Start the admitted operation and correlate its acknowledgement."""
    started = exchange(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
    )
    if not isinstance(started, OperationAcknowledged) or started.operation_id != operation_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)

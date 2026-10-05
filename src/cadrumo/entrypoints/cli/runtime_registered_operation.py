"""Run bounded registered CLI operations and erase one-shot secrets on every exit."""

from __future__ import annotations

from typing import overload
from uuid import uuid4

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.schema_identity import OperationSchemaIdentityV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import bounded_deadline_after
from ...application.runtime.operation_access import (
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from .errors import (
    CliOperationStillRunningError,
    CliRefusedBoundaryError,
)
from .registered_operation_admission import (
    encode_registered_payload,
    require_registered_definition_contract,
    require_registered_review_contract,
    start_registered_operation,
    submit_registered_secret,
)
from .registered_operation_completion import read_registered_completion, require_registered_settlement
from .registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationProgress,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from .registered_operation_deadlines import RegisteredOperationDeadline, operation_settlement_deadline
from .registered_operation_errors import map_registered_transport_failure
from .registered_operation_exchange import RegisteredOperationExchange
from .registered_operation_observations import wait_registered_settlement


@overload
def run_registered_operation[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    payload: BaseModel,
    *,
    definition_id: str,
    subject_ref: str,
    result_type: type[ResultT],
    request_version: int,
    result_version: int,
    timeout: float,
    allow_refusal_detail: bool = False,
    secret: bytearray | None = None,
    review: None = None,
    settlement_timeout: float | None = None,
    pending_check_command: str | None = None,
) -> RegisteredOperationCompletion[ResultT]: ...


@overload
def run_registered_operation[ResultT: BaseModel, ReviewT: BaseModel](
    client: RuntimeFrontendClient,
    payload: BaseModel,
    *,
    definition_id: str,
    subject_ref: str,
    result_type: type[ResultT],
    request_version: int,
    result_version: int,
    timeout: float,
    review: RegisteredOperationReviewHandler[ReviewT],
    allow_refusal_detail: bool = False,
    secret: bytearray | None = None,
    settlement_timeout: float | None = None,
    pending_check_command: str | None = None,
) -> RegisteredOperationCompletion[ResultT] | RegisteredOperationReviewCompletion[ReviewT]: ...


def run_registered_operation[ResultT: BaseModel, ReviewT: BaseModel](
    client: RuntimeFrontendClient,
    payload: BaseModel,
    *,
    definition_id: str,
    subject_ref: str,
    result_type: type[ResultT],
    request_version: int,
    result_version: int,
    timeout: float,
    allow_refusal_detail: bool = False,
    secret: bytearray | None = None,
    review: RegisteredOperationReviewHandler[ReviewT] | None = None,
    settlement_timeout: float | None = None,
    pending_check_command: str | None = None,
) -> RegisteredOperationCompletion[ResultT] | RegisteredOperationReviewCompletion[ReviewT]:
    """Run one registered operation with exact contract and result correlation.

    ``timeout`` bounds every single exchange; ``settlement_timeout`` bounds how
    long the command waits for the admitted operation to settle. When that
    wait ends first, the operation is reported still running with its
    identity and unknown effect, never as a refusal of work that may commit.
    Any one-shot secret is wiped on every exit.
    """
    try:
        bounded_deadline_after(timeout, subject="modelo operation")
        deadline = operation_settlement_deadline(timeout, settlement_timeout)

        budget = RegisteredOperationDeadline(deadline, timeout, settlement_timeout)
        call_deadline = budget.call_deadline
        settled_read_deadline = budget.settled_read_deadline

        profile_id, session_id, frontend = client.profile_id, client.session_id, client.frontend
        contract = client.contract(definition_id, deadline=call_deadline())
        expected_request = OperationSchemaIdentityV1.from_model(
            schema_id=definition_id + ".request", schema_version=request_version, model_type=type(payload)
        )
        expected_result = OperationSchemaIdentityV1.from_model(
            schema_id=definition_id + ".result", schema_version=result_version, model_type=result_type
        )
        require_registered_definition_contract(
            contract, definition_id, expected_request, expected_result, frontend, secret
        )
        require_registered_review_contract(contract, review)

        progress = RegisteredOperationProgress()

        exchange = RegisteredOperationExchange(
            client, profile_id, session_id, frontend, deadline, call_deadline, progress
        )

        payload_json = encode_registered_payload(payload)
        submitted = exchange(
            RuntimeOperationSubmit(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload_json=payload_json,
            ),
        )
        if not isinstance(submitted, RuntimeOperationSubmitted):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        operation_id = submitted.receipt.operation_id
        try:
            submit_registered_secret(client, submitted, operation_id, definition_id, subject_ref, secret, call_deadline)
            start_registered_operation(operation_id, profile_id, session_id, exchange)
            state, detached_review = wait_registered_settlement(
                client,
                operation_id,
                profile_id,
                session_id,
                definition_id,
                subject_ref,
                contract,
                deadline,
                pending_check_command,
                progress,
                review,
                exchange,
            )
            if detached_review is not None:
                return detached_review
            require_registered_settlement(
                client, operation_id, state, progress, contract, allow_refusal_detail, settled_read_deadline
            )
            return read_registered_completion(
                client,
                operation_id,
                state,
                progress,
                contract,
                expected_result,
                result_type,
                profile_id,
                session_id,
                frontend,
                settled_read_deadline,
            )
        except (CliRefusedBoundaryError, CliOperationStillRunningError):
            raise
        except Exception as error:
            mapped = map_registered_transport_failure(client, operation_id, error, progress)
        # Do not chain a possibly private malformed projection into the public error.
        raise mapped from None
    finally:
        if secret is not None:
            secret[:] = bytes(len(secret))

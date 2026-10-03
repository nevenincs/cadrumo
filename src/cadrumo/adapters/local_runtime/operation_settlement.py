"""Submit, start and settle one registered operation over an exact frontend client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from pydantic import ValidationError

from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationLifecycle
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError

_POLL_INTERVAL_SECONDS = 0.02


@dataclass(frozen=True, slots=True)
class PinnedConnection:
    """The profile, session and frontend a client held when an operation was submitted."""

    profile_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection

    @classmethod
    def of(cls, client: RuntimeFrontendClient) -> Self:
        """Pin the identity the client holds now."""
        return cls(client.profile_id, client.session_id, client.frontend)

    def holds(self, client: RuntimeFrontendClient) -> bool:
        """Whether the client still holds exactly the pinned identity."""
        return (client.profile_id, client.session_id, client.frontend) == (
            self.profile_id,
            self.session_id,
            self.frontend,
        )

    def require_held(self, client: RuntimeFrontendClient) -> None:
        """Refuse once the client no longer holds the pinned identity.

        Every exchange already refuses a foreign session, but only with a
        profile mismatch; failing here names the lost connection instead.
        """
        if not self.holds(client):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def submit_operation(
    client: RuntimeFrontendClient,
    pinned: PinnedConnection,
    *,
    definition_id: str,
    subject_ref: str,
    payload_json: str,
    deadline: float,
    idempotency_key: str | None = None,
) -> RuntimeOperationSubmitted:
    """Submit one registered request under the pinned session; the receipt is not admission."""
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=pinned.profile_id,
            session_id=pinned.session_id,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
        ),
        deadline=deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return submitted


def start_and_await_terminal(
    client: RuntimeFrontendClient,
    pinned: PinnedConnection,
    operation_id: OperationId,
    *,
    contract: OperationPublicDefinitionContractV1,
    subject_ref: str,
    deadline: float,
) -> OperationPublicProjectionV1:
    """Admit a submitted operation and poll its canonical state until it is terminal.

    The pinned identity must hold before every observation, and each observed
    state must name this operation, definition, subject and exact contract.
    """
    started = client.operation(
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=pinned.profile_id,
            session_id=pinned.session_id,
            operation_id=operation_id,
        ),
        deadline=deadline,
    )
    if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    while True:
        remaining_budget(deadline)
        pinned.require_held(client)
        reply = client.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=pinned.profile_id,
                session_id=pinned.session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
            ),
            deadline=deadline,
        )
        if not isinstance(reply, RuntimeOperationObserved):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        observation = reply.observation
        if not isinstance(observation, OperationObservationSuccessV1):
            raise RuntimeFrontendRefusedError(observation.code.value)
        state = observation.projection
        if (
            state.operation_id != operation_id
            or state.definition_id != contract.definition_id
            or state.subject_ref != subject_ref
            or state.definition_contract != contract
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if state.lifecycle is OperationLifecycle.TERMINAL:
            return state
        time.sleep(min(_POLL_INTERVAL_SECONDS, remaining_budget(deadline)))


def read_settled_result_bytes(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    terminal: OperationPublicProjectionV1,
    contract: OperationPublicDefinitionContractV1,
    *,
    deadline: float,
) -> bytes:
    """Read one settled result document and return its canonical bytes unless it is a refusal.

    A refusal document surfaces as the runtime's typed refusal. A malformed one
    is an invalid frame without its content in the exception chain.
    """
    result_schema = contract.result_schema
    if result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    document = client.read_result_document(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=result_schema,
        ),
        timeout=remaining_budget(deadline),
    )
    encoded = canonical_json_bytes(document)
    if document.get("outcome") == "refused":
        try:
            refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
        except ValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        raise RuntimeFrontendRefusedError(refusal.code.value)
    return encoded

"""Read one human automation inventory through its registered runtime operation."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import cache
from uuid import UUID, uuid4

from pydantic import ValidationError

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.automation_enrollment import AutomationInventoryProjection
from ...application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import canonical_json_bytes
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError

_MAX_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class AutomationInventoryCompletion:
    """One complete current-consent projection and its canonical operation ID."""

    operation_id: OperationId
    projection: AutomationInventoryProjection


class AutomationInventoryReadError(CadrumoError):
    """Retain a submitted operation's identity without inventing its outcome."""

    def __init__(
        self,
        *,
        operation_id: OperationId,
        code: str,
        terminal_condition: OperationTerminalCondition | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        """Keep only a validated terminal witness or an explicit unknown effect."""
        self.operation_id = operation_id
        self.reason = code
        self._terminal_condition = terminal_condition
        self._effect = effect
        context = {
            "reason": code,
            "operation_id": str(operation_id),
            "effect": effect.value if effect is not None else "unknown",
        }
        if terminal_condition is not None:
            context["terminal_condition"] = terminal_condition.value
        super().__init__(code, context=context)

    @property
    def terminal_condition(self) -> OperationTerminalCondition | None:
        """Return a condition only when canonical observation supplied it."""
        return self._terminal_condition

    @property
    def effect(self) -> OperationEffect | None:
        """Keep an unobserved effect distinct from the public unknown marker."""
        return self._effect


@cache
def _contract() -> OperationPublicDefinitionContractV1:
    definition = next(
        item
        for item in build_automation_operation_definitions()
        if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    )
    registration = build_automation_operation_registrations((definition,))[0]
    if registration.contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return registration.contract


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _failure_code(error: Exception) -> str:
    if isinstance(error, RuntimeFrontendRefusedError):
        return error.reason
    if isinstance(error, RuntimeRefusalError):
        return error.reason.value
    return RuntimeRefusalCode.UNAVAILABLE.value


def _exact_profile(projection: AutomationInventoryProjection, profile_id: UUID) -> bool:
    return (
        all(item.profile_id == profile_id for item in projection.grants)
        and all(item.profile_id == profile_id for item in projection.keys)
        and all(item.receipt.profile_id == profile_id for item in projection.requests)
    )


def read_automation_inventory(client: RuntimeFrontendClient, *, timeout: float = 60) -> AutomationInventoryCompletion:
    """Return only a settled, exact-profile public inventory under human authority.

    A timeout or refusal after submission carries its operation ID. An observed
    terminal condition/effect is included only when canonical observation
    supplied it; no acknowledgement is treated as a completed read.
    """
    if client.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
        raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("automation inventory timeout must be finite and at most 120 seconds")
    deadline = time.monotonic() + timeout
    profile_id, session_id, frontend = client.profile_id, client.session_id, client.frontend
    contract = client.contract(AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID, deadline=deadline)
    if contract != _contract() or contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=contract.definition_id,
            subject_ref=subject_ref,
            payload_json=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()).model_dump_json(),
        ),
        deadline=deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        started = client.operation(
            RuntimeOperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                operation_id=operation_id,
            ),
            deadline=deadline,
        )
        if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        while True:
            _remaining(deadline)
            if client.session_id != session_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            reply = client.operation(
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=session_id,
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
                condition, effect = state.terminal_condition, state.effect
                break
            time.sleep(min(0.02, _remaining(deadline)))
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise AutomationInventoryReadError(
                operation_id=operation_id,
                code=state.refusal_ref
                or state.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        if effect is not OperationEffect.NONE:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        document = client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=state.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            timeout=_remaining(deadline),
        )
        if document.get("outcome") == "refused":
            try:
                refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(document))
            except ValidationError:
                refusal = None
            if refusal is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        try:
            result = OperationResultProjectionSuccessV1[AutomationInventoryProjection].model_validate_json(
                canonical_json_bytes(document)
            )
        except ValidationError:
            result = None
        if result is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if (
            result.result_schema != contract.result_schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or not _exact_profile(result.projection, profile_id)
            or client.profile_id != profile_id
            or client.frontend is not frontend
            or client.session_id != session_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return AutomationInventoryCompletion(operation_id=operation_id, projection=result.projection)
    except AutomationInventoryReadError:
        raise
    except Exception as error:
        code = RuntimeRefusalCode.INVALID_FRAME.value if isinstance(error, ValidationError) else _failure_code(error)
    # Leave the exception handler before constructing the public error. A
    # malformed private result must not remain in its exception chain.
    raise AutomationInventoryReadError(
        operation_id=operation_id,
        code=code,
        terminal_condition=condition,
        effect=effect,
    )


__all__ = ["AutomationInventoryCompletion", "AutomationInventoryReadError", "read_automation_inventory"]

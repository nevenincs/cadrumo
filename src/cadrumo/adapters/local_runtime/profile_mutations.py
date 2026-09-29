"""Bounded native runtime runner for registered profile-fact mutations."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import cache
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationPublicDefinitionRegistrationV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    ProfileCompleteSetupOperationProjection,
    ProfileCompleteSetupOperationRequest,
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
    ProfilePatchOperationProjection,
    ProfilePatchOperationRequest,
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfileRepeatableRowChangeOperationProjection,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    build_user_profile_operation_registrations,
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

type ProfileMutationRequest = (
    ProfileFieldMutationOperationRequest
    | ProfilePatchOperationRequest
    | ProfilePlantillaMediaOperationRequest
    | ProfileDescendantsOperationRequest
    | ProfileRepeatableRowMutationOperationRequest
    | ProfileRepeatableRowUpdateOperationRequest
    | ProfileRepeatableRowRemoveOperationRequest
    | ProfileCompleteSetupOperationRequest
)

type ProfileMutationProjection = (
    ProfileMutationOperationProjection
    | ProfilePatchOperationProjection
    | ProfilePlantillaMediaOperationProjection
    | ProfileDescendantsOperationProjection
    | ProfileRepeatableRowMutationOperationProjection
    | ProfileRepeatableRowChangeOperationProjection
    | ProfileCompleteSetupOperationProjection
)

_SUPPORTED_REQUEST_TYPES: tuple[type[BaseModel], ...] = (
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePlantillaMediaOperationRequest,
    ProfileDescendantsOperationRequest,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileCompleteSetupOperationRequest,
)
_MAX_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class ProfileMutationCompletion:
    """Canonical settled identity retained alongside its permitted result projection."""

    operation_id: OperationId
    projection: ProfileMutationOperationProjection
    effect: OperationEffect


class ProfileMutationRunError(CadrumoError):
    """Retain the submitted ID and only observed settlement facts on failure."""

    def __init__(
        self,
        *,
        operation_id: OperationId,
        code: str,
        terminal_condition: OperationTerminalCondition | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        """Keep unknown effect explicit when the runtime could not be observed."""
        self.operation_id = operation_id
        self.reason = code
        self._terminal_condition = terminal_condition
        self._effect = effect
        context = {
            "reason": code,
            "operation_id": str(operation_id),
            "effect": effect.value if effect else "unknown",
        }
        if terminal_condition is not None:
            context["terminal_condition"] = terminal_condition.value
        super().__init__(code, context=context)

    @property
    def terminal_condition(self) -> OperationTerminalCondition | None:
        """Return only the terminal condition actually observed by the runner."""
        return self._terminal_condition

    @property
    def effect(self) -> OperationEffect | None:
        """Keep unobserved effects distinct from the serialized unknown marker."""
        return self._effect


@cache
def _registration(request_type: type[BaseModel]) -> OperationPublicDefinitionRegistrationV1:
    """Resolve the exact definition and schemas from the canonical owner."""
    if request_type not in _SUPPORTED_REQUEST_TYPES:
        raise TypeError("unsupported profile mutation request type")
    definition = next(
        (definition for definition in USER_PROFILE_OPERATION_DEFINITIONS if definition.request_type is request_type),
        None,
    )
    if definition is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    registration = build_user_profile_operation_registrations((definition,))[0]
    result_schema = registration.contract.result_schema
    if result_schema is None or not any(
        binding.identity == result_schema and issubclass(binding.model_type, ProfileMutationOperationProjection)
        for binding in registration.schema_bindings
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return registration


def _deadline(timeout: float) -> float:
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("profile mutation timeout must be finite and at most 120 seconds")
    return time.monotonic() + timeout


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


def run_profile_mutation(
    client: RuntimeFrontendClient,
    request: ProfileMutationRequest,
    *,
    timeout: float = 60,
    idempotency_key: str | None = None,
) -> ProfileMutationCompletion:
    """Submit, settle and project one exact-profile mutation over native IPC.

    An acknowledgement is never reported as a committed effect. Once submitted,
    every non-result path raises :class:`ProfileMutationRunError` with the
    operation ID so the caller can inspect current state through canonical
    observation. ``terminal_condition`` and ``effect`` are populated only when
    a valid terminal observation was actually received.
    """
    if type(request) not in _SUPPORTED_REQUEST_TYPES:
        raise TypeError("unsupported profile mutation request type")
    if request.profile_id != client.profile_id:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    deadline = _deadline(timeout)
    registration = _registration(type(request))
    contract = client.contract(registration.contract.definition_id, deadline=deadline)
    if contract != registration.contract or contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    session_id = client.session_id
    profile_id = client.profile_id
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=contract.definition_id,
            subject_ref=subject_ref,
            payload_json=request.model_dump_json(),
            idempotency_key=idempotency_key,
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
            observed = client.operation(
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=session_id,
                    observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
                ),
                deadline=deadline,
            )
            if not isinstance(observed, RuntimeOperationObserved):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            observation = observed.observation
            if not isinstance(observation, OperationObservationSuccessV1):
                raise RuntimeFrontendRefusedError(observation.code.value)
            projection = observation.projection
            if (
                projection.operation_id != operation_id
                or projection.definition_id != contract.definition_id
                or projection.subject_ref != subject_ref
                or projection.definition_contract != contract
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if projection.lifecycle is OperationLifecycle.TERMINAL:
                condition, effect = projection.terminal_condition, projection.effect
                break
            time.sleep(min(0.02, _remaining(deadline)))
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise ProfileMutationRunError(
                operation_id=operation_id,
                code=projection.refusal_ref
                or projection.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        result = client.operation(
            RuntimeOperationResult(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                result=OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
            ),
            deadline=deadline,
        )
        if (
            not isinstance(result, RuntimeOperationProjected)
            or result.operation_id != operation_id
            or result.projection_kind != "result"
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if result.document.get("outcome") == "refused":
            refused = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(result.document))
            raise RuntimeFrontendRefusedError(refused.code.value)
        success = OperationResultProjectionSuccessV1[ProfileMutationProjection].model_validate_json(
            canonical_json_bytes(result.document)
        )
        expected_type = next(
            binding.model_type for binding in registration.schema_bindings if binding.identity == contract.result_schema
        )
        if (
            success.result_schema != contract.result_schema
            or success.definition_contract_digest != contract.definition_contract_digest
            or type(success.projection) is not expected_type
            or success.projection.profile_id != profile_id
            or success.projection.record_revision < request.expected_revision
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ProfileMutationCompletion(operation_id=operation_id, projection=success.projection, effect=effect)
    except ProfileMutationRunError:
        raise
    except Exception as error:
        if isinstance(error, ValidationError):
            error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        raise ProfileMutationRunError(
            operation_id=operation_id,
            code=_failure_code(error),
            terminal_condition=condition,
            effect=effect,
        ) from error


__all__ = ["ProfileMutationCompletion", "ProfileMutationRequest", "ProfileMutationRunError", "run_profile_mutation"]

"""One bounded, correlated transport for registered CLI operations."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationPublicDefinitionContractV1, OperationSchemaIdentityV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .errors import CliRefusedBoundaryError

_MAX_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class RegisteredOperationCompletion[ResultT: BaseModel]:
    """One registered result and the effect that settled its exact operation."""

    operation_id: OperationId
    projection: ResultT
    effect: OperationEffect
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED
    refusal_code: str | None = None


def _deadline(timeout: float) -> float:
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("modelo operation timeout must be finite and at most 120 seconds")
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


def submitted_operation_error(
    operation_id: OperationId,
    code: str,
    *,
    terminal_condition: OperationTerminalCondition | None,
    effect: OperationEffect | None,
    refusal_code: str | None = None,
) -> CliRefusedBoundaryError:
    """Retain an exact operation ID and its last observed effect on refusal."""
    context = {
        "operation_id": str(operation_id),
        "reason": code,
        "effect": effect.value if effect is not None else "unknown",
    }
    if terminal_condition is not None:
        context["terminal_condition"] = terminal_condition.value
    if refusal_code is not None:
        context["refusal_code"] = refusal_code
    return CliRefusedBoundaryError(code, context=context)


def _result[ResultT: BaseModel](
    document: Mapping[str, object],
    *,
    result_type: type[ResultT],
    contract: OperationPublicDefinitionContractV1,
) -> ResultT:
    encoded = canonical_json_bytes(document)
    if document.get("outcome") == "refused":
        refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
    # CAST-RATIONALE-CLI-REGISTERED-RESULT-GENERIC: Pydantic's runtime specialization binds the
    # success projection to this exact result_type; its __class_getitem__ typing stub is broad.
    success_type = cast(
        "type[OperationResultProjectionSuccessV1[ResultT]]",
        OperationResultProjectionSuccessV1.__class_getitem__(result_type),
    )
    success = success_type.model_validate_json(encoded)
    if (
        success.result_schema != contract.result_schema
        or success.definition_contract_digest != contract.definition_contract_digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return success.projection


def _run_registered_operation[ResultT: BaseModel](
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
) -> RegisteredOperationCompletion[ResultT]:
    """Run one registered operation with exact contract and result correlation."""
    deadline = _deadline(timeout)
    profile_id, session_id, frontend = client.profile_id, client.session_id, client.frontend
    contract = client.contract(definition_id, deadline=deadline)
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=definition_id + ".request", schema_version=request_version, model_type=type(payload)
    )
    expected_result = OperationSchemaIdentityV1.from_model(
        schema_id=definition_id + ".result", schema_version=result_version, model_type=result_type
    )
    if (
        contract.definition_id != definition_id
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or frontend not in contract.permitted_frontends
        or contract.ephemeral_secret_required is not (secret is not None)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    try:
        payload_json = payload.model_dump_json()
        payload_size = len(payload_json.encode("utf-8"))
    except (UnicodeError, ValueError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    if payload_size > SUBMISSION_PAYLOAD_MAX_BYTES:
        # Refuse before Pydantic can retain a long private row in its error.
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=payload_json,
        ),
        deadline=deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    refusal_code: str | None = None
    try:
        requirement = submitted.receipt.secret_requirement
        if (requirement is None) is not (secret is None):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if requirement is not None and secret is not None:
            if (
                requirement.identity.operation_id != operation_id
                or requirement.identity.definition_id != definition_id
                or requirement.identity.subject_ref != subject_ref
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            acknowledged = client.submit_secret(requirement, secret, timeout=min(20, _remaining(deadline)))
            if acknowledged.operation_id != operation_id:
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
            if isinstance(observed.observation, OperationObservationRefusalV1):
                raise RuntimeFrontendRefusedError(observed.observation.code.value)
            if not isinstance(observed.observation, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            state = observed.observation.projection
            if (
                state.operation_id != operation_id
                or state.definition_id != definition_id
                or state.subject_ref != subject_ref
                or state.definition_contract != contract
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if state.lifecycle is OperationLifecycle.TERMINAL:
                condition, effect = state.terminal_condition, state.effect
                refusal_code = state.refusal_ref
                break
            time.sleep(min(0.02, _remaining(deadline)))
        declared_refusal_detail = (
            allow_refusal_detail
            and condition is OperationTerminalCondition.REFUSED
            and refusal_code in contract.refusal_detail_codes
        )
        if condition is not OperationTerminalCondition.SUCCEEDED and not declared_refusal_detail:
            raise submitted_operation_error(
                operation_id,
                state.refusal_ref
                or state.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        document = client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=state.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=expected_result,
            ),
            timeout=_remaining(deadline),
        )
        projection = _result(document, result_type=result_type, contract=contract)
        if client.profile_id != profile_id or client.session_id != session_id or client.frontend is not frontend:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if condition is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return RegisteredOperationCompletion[ResultT](
            operation_id=operation_id,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )
    except CliRefusedBoundaryError:
        raise
    except Exception as error:
        code = RuntimeRefusalCode.INVALID_FRAME.value if isinstance(error, ValidationError) else _failure_code(error)
    # Do not chain a possibly private malformed projection into the public error.
    raise submitted_operation_error(
        operation_id, code, terminal_condition=condition, effect=effect, refusal_code=refusal_code
    )


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
) -> RegisteredOperationCompletion[ResultT]:
    """Run an exact registered operation and wipe any one-shot secret on every exit."""
    try:
        return _run_registered_operation(
            client,
            payload,
            definition_id=definition_id,
            subject_ref=subject_ref,
            result_type=result_type,
            request_version=request_version,
            result_version=result_version,
            timeout=timeout,
            allow_refusal_detail=allow_refusal_detail,
            secret=secret,
        )
    finally:
        if secret is not None:
            secret[:] = bytes(len(secret))


__all__ = ["RegisteredOperationCompletion", "run_registered_operation", "submitted_operation_error"]

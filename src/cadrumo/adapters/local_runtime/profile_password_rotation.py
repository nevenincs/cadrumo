"""Confirm password rotation through a freshly authenticated result reader."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import ValidationError

from ...application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    ProfilePassphraseRotationOperationRequest,
)
from ...application.auth.passphrase_operation_access import (
    PROFILE_ROTATION_RESULT_SCHEMA_ID,
    ProfilePassphraseRotationResultProjection,
)
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationPublicDefinitionContractV1
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
from ...application.user_profile.automation_custody_port import AutomationCustodyCode
from ...application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ...core.hashing import canonical_json_bytes
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from .profile_mutations import ProfileMutationRunError


@dataclass(frozen=True, slots=True)
class ProfileRotationCompletion:
    """The exact committed result read under replacement-password authority."""

    operation_id: OperationId
    outcome: ProfilePassphraseRotationOutcome


def _wipe_buffers(buffers: tuple[object, ...]) -> None:
    for buffer in buffers:
        if isinstance(buffer, bytearray):
            buffer[:] = bytes(len(buffer))


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _secret_document(current: bytearray, replacement: bytearray, confirmation: bytearray) -> bytearray:
    document: bytearray | None = None
    with suppress(UnicodeError):
        document = bytearray(
            canonical_json_bytes(
                {
                    "current_passphrase": current.decode("utf-8"),
                    "new_passphrase": replacement.decode("utf-8"),
                    "new_passphrase_confirmation": confirmation.decode("utf-8"),
                }
            )
        )
    # Do not retain a decoder exception containing rejected credential bytes.
    if document is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return document


def _observe(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    contract: OperationPublicDefinitionContractV1,
    *,
    deadline: float,
) -> OperationObservationSuccessV1:
    _remaining(deadline)
    reply = client.operation(
        RuntimeOperationObserve(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
        ),
        deadline=deadline,
    )
    if not isinstance(reply, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    observation = reply.observation
    if not isinstance(observation, OperationObservationSuccessV1):
        raise RuntimeFrontendRefusedError(observation.code.value)
    projection = observation.projection
    if (
        projection.operation_id != operation_id
        or projection.definition_id != contract.definition_id
        or projection.subject_ref != profile_operation_subject(str(client.profile_id))
        or projection.definition_contract != contract
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return observation


def _settled(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    contract: OperationPublicDefinitionContractV1,
    *,
    deadline: float,
) -> OperationObservationSuccessV1:
    while True:
        observed = _observe(client, operation_id, contract, deadline=deadline)
        projection = observed.projection
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
                raise ProfileMutationRunError(
                    operation_id=operation_id,
                    code=projection.refusal_ref or projection.failure_error_code or "rotation_unsettled",
                    terminal_condition=projection.terminal_condition,
                    effect=projection.effect,
                )
            if projection.effect is not OperationEffect.UPDATED:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return observed
        time.sleep(min(0.02, _remaining(deadline)))


def _fresh_result(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    contract: OperationPublicDefinitionContractV1,
    *,
    deadline: float,
) -> ProfilePassphraseRotationOutcome:
    observed = _settled(client, operation_id, contract, deadline=deadline)
    if contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    reply = client.operation(
        RuntimeOperationResult(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=observed.projection.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
        ),
        deadline=deadline,
    )
    if (
        not isinstance(reply, RuntimeOperationProjected)
        or reply.operation_id != operation_id
        or reply.projection_kind != "result"
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise RuntimeFrontendRefusedError(refusal.code.value)
    result = OperationResultProjectionSuccessV1[ProfilePassphraseRotationResultProjection].model_validate_json(
        canonical_json_bytes(reply.document)
    )
    outcome = result.projection.outcome
    if (
        result.result_schema != contract.result_schema
        or result.definition_contract_digest != contract.definition_contract_digest
        or outcome.profile_id != str(client.profile_id)
        or not outcome.dek_epoch_preserved
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return outcome


def _read_with_replacement(
    original: RuntimeFrontendClient,
    operation_id: OperationId,
    contract: OperationPublicDefinitionContractV1,
    *,
    replacement: bytearray,
    fresh_client: Callable[[], RuntimeFrontendClient],
    original_session: UUID,
    deadline: float,
) -> ProfilePassphraseRotationOutcome:
    while True:
        _remaining(deadline)
        reader = fresh_client()
        if reader is original:
            raise RuntimeFrontendRefusedError(AccessDenialCode.CONNECTION_MISMATCH.value)
        with reader:
            if reader.profile_id != original.profile_id or reader.frontend is not original.frontend:
                raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
            try:
                reader.login_password(bytearray(replacement), timeout=min(20.0, _remaining(deadline)))
            except RuntimeFrontendRefusedError as error:
                # Only an old host still retiring may defer fresh admission.
                # A rejected password is never retried or treated as success.
                if error.reason not in {AutomationCustodyCode.CONFLICT.value, AutomationCustodyCode.UNAVAILABLE.value}:
                    raise
            else:
                if reader.session_id == original_session:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return _fresh_result(reader, operation_id, contract, deadline=deadline)
        time.sleep(min(0.05, _remaining(deadline)))


def run_profile_password_rotation(
    client: RuntimeFrontendClient,
    *,
    current_passphrase: bytearray,
    new_passphrase: bytearray,
    new_passphrase_confirmation: bytearray,
    fresh_client: Callable[[], RuntimeFrontendClient],
    timeout: float = 60,
) -> ProfileRotationCompletion:
    """Consume proofs, then confirm the exact result using fresh human admission.

    The original client is borrowed; each replacement client is owned here.
    No mutation is retried. Once submission succeeds, uncertainty retains its
    operation ID for canonical recovery instead of claiming rollback or success.
    """
    buffers: tuple[object, ...] = (current_passphrase, new_passphrase, new_passphrase_confirmation)
    operation_id: OperationId | None = None
    try:
        if not all(isinstance(value, bytearray) for value in buffers):
            raise TypeError("password rotation requires mutable credential buffers")
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("password rotation timeout must be finite and at most 120 seconds")
        deadline = time.monotonic() + timeout
        contract = client.contract(PROFILE_ROTATION_OPERATION_DEFINITION_ID, deadline=deadline)
        if (
            contract.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
            or contract.result_schema is None
            or contract.result_schema.schema_id != PROFILE_ROTATION_RESULT_SCHEMA_ID
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        original_session = client.session_id
        payload = ProfilePassphraseRotationOperationRequest(profile_id=client.profile_id)
        submitted = client.operation(
            RuntimeOperationSubmit(
                request_id=uuid4(),
                profile_id=client.profile_id,
                session_id=original_session,
                definition_id=contract.definition_id,
                subject_ref=profile_operation_subject(str(client.profile_id)),
                payload_json=payload.model_dump_json(),
                idempotency_key=None,
            ),
            deadline=deadline,
        )
        if not isinstance(submitted, RuntimeOperationSubmitted):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        operation_id = submitted.receipt.operation_id
        requirement = submitted.receipt.secret_requirement
        if (
            requirement is None
            or requirement.identity.operation_id != operation_id
            or requirement.identity.definition_id != contract.definition_id
            or requirement.identity.subject_ref != profile_operation_subject(str(client.profile_id))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        secret = _secret_document(current_passphrase, new_passphrase, new_passphrase_confirmation)
        try:
            delivered = client.submit_secret(requirement, secret, timeout=_remaining(deadline))
        finally:
            secret[:] = bytes(len(secret))
        if delivered.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            started = client.operation(
                RuntimeOperationControl(
                    action="operation_start",
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=original_session,
                    operation_id=operation_id,
                ),
                deadline=deadline,
            )
            if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            _settled(client, operation_id, contract, deadline=deadline)
        except RuntimeFrontendRefusedError:
            # Deliberate retirement removes old read authority. Fresh password
            # admission and the exact canonical result must still prove success.
            pass
        except RuntimeRefusalError as error:
            if error.reason not in {RuntimeRefusalCode.CONNECTION_CLOSED, RuntimeRefusalCode.UNAVAILABLE}:
                raise
        outcome = _read_with_replacement(
            client,
            operation_id,
            contract,
            replacement=new_passphrase,
            fresh_client=fresh_client,
            original_session=original_session,
            deadline=deadline,
        )
        return ProfileRotationCompletion(operation_id, outcome)
    except ProfileMutationRunError:
        raise
    except Exception as error:
        if operation_id is None:
            raise
        code = (
            error.reason
            if isinstance(error, RuntimeFrontendRefusedError)
            else error.reason.value
            if isinstance(error, RuntimeRefusalError)
            else RuntimeRefusalCode.INVALID_FRAME.value
            if isinstance(error, ValidationError)
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        failure = ProfileMutationRunError(operation_id=operation_id, code=code)
    finally:
        _wipe_buffers(buffers)
    raise failure

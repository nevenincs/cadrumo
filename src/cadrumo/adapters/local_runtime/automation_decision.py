"""Confirm a reviewed automation decision through the canonical runtime owner."""

from __future__ import annotations

import math
import time
from contextlib import suppress
from dataclasses import dataclass
from functools import cache
from typing import Literal
from uuid import uuid4

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
from ...application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    AutomationReviewProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from ...application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
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

type AutomationDecision = Literal["approve", "decline"]


@dataclass(frozen=True, slots=True)
class AutomationDecisionCompletion:
    """A canonical completed decision, never proof of key possession."""

    operation_id: OperationId
    receipt: AutomationReceiptProjection
    effect: OperationEffect


class AutomationDecisionRunError(CadrumoError):
    """Keep recovery identity and observed effects when completion is unavailable."""

    def __init__(
        self,
        *,
        operation_id: OperationId,
        code: str,
        terminal_condition: OperationTerminalCondition | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        """Never let optional typed attributes overwrite an honest unknown effect."""
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
        """Return only a condition supplied by canonical observation."""
        return self._terminal_condition

    @property
    def effect(self) -> OperationEffect | None:
        """Return only an effect supplied by canonical observation."""
        return self._effect


@cache
def _contract(decision: AutomationDecision) -> OperationPublicDefinitionContractV1:
    identity = (
        AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
        if decision == "approve"
        else AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
    )
    definition = next(item for item in build_automation_operation_definitions() if item.definition_id == identity)
    return build_automation_operation_registrations((definition,))[0].contract


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _checked_review(review: AutomationReviewProjection) -> AutomationReviewProjection:
    validated: AutomationReviewProjection | None = None
    with suppress(ValidationError, ValueError, TypeError):
        validated = AutomationReviewProjection.model_validate_json(review.model_dump_json(warnings=False))
    if validated is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return validated


def _matches_receipt(
    review: AutomationReviewProjection, completed: AutomationReceiptProjection, decision: AutomationDecision
) -> bool:
    original = review.receipt
    if decision == "approve" and (completed.key_id is not None) != (
        review.proposal.kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE}
    ):
        return False
    return (
        completed.profile_id == original.profile_id
        and completed.request_id == original.request_id
        and completed.review_digest == original.review_digest
        and completed.grant_id == original.grant_id
        and completed.stage is (EnrollmentStage.COMPLETE if decision == "approve" else EnrollmentStage.DECLINED)
        and (original.key_id is None or completed.key_id == original.key_id)
        and (original.credential_reference is None or completed.credential_reference == original.credential_reference)
        and ((completed.key_id is None) == (completed.credential_reference is None))
    )


def run_automation_decision(
    client: RuntimeFrontendClient,
    review: AutomationReviewProjection,
    *,
    decision: AutomationDecision,
    password: bytearray | None = None,
    timeout: float = 120,
) -> AutomationDecisionCompletion:
    """Submit once for the exact reviewed digest, then require its settled result.

    Approval consumes a fresh password through the declared ephemeral channel.
    Decline takes no password. The borrowed client is never closed here, and
    expiry or disconnection never causes an automatic second submission.
    """
    operation_id: OperationId | None = None
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    try:
        if decision not in {"approve", "decline"}:
            raise ValueError("unsupported automation decision")
        if (decision == "approve" and not isinstance(password, bytearray)) or (
            decision == "decline" and password is not None
        ):
            raise ValueError("password proof does not match the requested decision")
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("automation decision timeout must be finite and at most 120 seconds")
        if client.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
            raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
        review = _checked_review(review)
        profile_id, session_id, frontend = client.profile_id, client.session_id, client.frontend
        if review.receipt.profile_id != profile_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        deadline = time.monotonic() + timeout
        expected = _contract(decision)
        contract = client.contract(expected.definition_id, deadline=deadline)
        if contract != expected or contract.result_schema is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        subject = profile_operation_subject(str(profile_id))
        submitted = client.operation(
            RuntimeOperationSubmit(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                definition_id=contract.definition_id,
                subject_ref=subject,
                payload_json=AutomationOperationRequest(
                    profile_id=profile_id,
                    request_id=review.receipt.request_id,
                    review_digest=review.receipt.review_digest,
                ).model_dump_json(),
            ),
            deadline=deadline,
        )
        if not isinstance(submitted, RuntimeOperationSubmitted):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        operation_id = submitted.receipt.operation_id
        requirement = submitted.receipt.secret_requirement
        if decision == "approve":
            if (
                requirement is None
                or password is None
                or requirement.secret_kind != "automation.password"  # noqa: S105 - declared channel kind
                or requirement.identity.operation_id != operation_id
                or requirement.identity.definition_id != contract.definition_id
                or requirement.identity.subject_ref != subject
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            accepted = client.submit_secret(requirement, password, timeout=_remaining(deadline))
            if accepted.operation_id != operation_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        elif requirement is not None:
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
            if (client.profile_id, client.session_id, client.frontend) != (profile_id, session_id, frontend):
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
                or state.subject_ref != subject
                or state.definition_contract != contract
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if state.lifecycle is OperationLifecycle.TERMINAL:
                condition, effect = state.terminal_condition, state.effect
                break
            time.sleep(min(0.02, _remaining(deadline)))
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise AutomationDecisionRunError(
                operation_id=operation_id,
                code=state.refusal_ref or state.failure_error_code or "decision_unsettled",
                terminal_condition=condition,
                effect=effect,
            )
        if effect not in {OperationEffect.NONE, OperationEffect.UPDATED}:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
            refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(document))
            raise RuntimeFrontendRefusedError(refusal.code.value)
        result = OperationResultProjectionSuccessV1[AutomationReceiptProjection].model_validate_json(
            canonical_json_bytes(document)
        )
        if (
            result.result_schema != contract.result_schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or not _matches_receipt(review, result.projection, decision)
            or (client.profile_id, client.session_id, client.frontend) != (profile_id, session_id, frontend)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return AutomationDecisionCompletion(operation_id, result.projection, effect)
    except AutomationDecisionRunError:
        raise
    except Exception as error:
        if operation_id is None:
            raise
        reason = (
            error.reason
            if isinstance(error, RuntimeFrontendRefusedError)
            else error.reason.value
            if isinstance(error, RuntimeRefusalError)
            else RuntimeRefusalCode.INVALID_FRAME.value
            if isinstance(error, ValidationError)
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        failure = AutomationDecisionRunError(
            operation_id=operation_id, code=reason, terminal_condition=condition, effect=effect
        )
    finally:
        if isinstance(password, bytearray):
            password[:] = bytes(len(password))
    raise failure


__all__ = [
    "AutomationDecision",
    "AutomationDecisionCompletion",
    "AutomationDecisionRunError",
    "run_automation_decision",
]

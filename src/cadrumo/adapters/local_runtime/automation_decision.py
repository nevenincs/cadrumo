"""Confirm a reviewed automation decision through the canonical runtime owner."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from functools import cache
from typing import Literal

from pydantic import ValidationError

from ...application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import bounded_deadline_after, remaining_budget
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
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError, frontend_failure_code
from .operation_settlement import (
    PinnedConnection,
    read_settled_result_bytes,
    start_and_await_terminal,
    submit_operation,
)

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
        deadline = bounded_deadline_after(timeout, subject="automation decision")
        if client.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
            raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
        review = _checked_review(review)
        pinned = PinnedConnection.of(client)
        profile_id = pinned.profile_id
        if review.receipt.profile_id != profile_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        expected = _contract(decision)
        contract = client.contract(expected.definition_id, deadline=deadline)
        if contract != expected or contract.result_schema is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        subject = profile_operation_subject(str(profile_id))
        submitted = submit_operation(
            client,
            pinned,
            definition_id=contract.definition_id,
            subject_ref=subject,
            payload_json=AutomationOperationRequest(
                profile_id=profile_id,
                request_id=review.receipt.request_id,
                review_digest=review.receipt.review_digest,
            ).model_dump_json(),
            deadline=deadline,
        )
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
            accepted = client.submit_secret(requirement, password, timeout=remaining_budget(deadline))
            if accepted.operation_id != operation_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        elif requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        state = start_and_await_terminal(
            client, pinned, operation_id, contract=contract, subject_ref=subject, deadline=deadline
        )
        condition, effect = state.terminal_condition, state.effect
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise AutomationDecisionRunError(
                operation_id=operation_id,
                code=state.refusal_ref or state.failure_error_code or "decision_unsettled",
                terminal_condition=condition,
                effect=effect,
            )
        if effect not in {OperationEffect.NONE, OperationEffect.UPDATED}:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        result = OperationResultProjectionSuccessV1[AutomationReceiptProjection].model_validate_json(
            read_settled_result_bytes(client, operation_id, state, contract, deadline=deadline)
        )
        if (
            result.result_schema != contract.result_schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or not _matches_receipt(review, result.projection, decision)
            or not pinned.holds(client)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return AutomationDecisionCompletion(operation_id, result.projection, effect)
    except AutomationDecisionRunError:
        raise
    except Exception as error:
        if operation_id is None:
            raise
        reason = frontend_failure_code(error)
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

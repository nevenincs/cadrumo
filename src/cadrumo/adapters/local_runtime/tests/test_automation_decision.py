"""The reviewed decision runner retains exact intent and truthful uncertainty."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal, override
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue, TypeAdapter

from cadrumo.adapters.local_runtime.automation_decision import (
    AutomationDecisionRunError,
    run_automation_decision,
)
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationProposalProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _review(profile_id: UUID, *, kind: EnrollmentKind = EnrollmentKind.ENROLL) -> AutomationReviewProjection:
    instant = now()
    grant_id = uuid4()
    return AutomationReviewProjection(
        receipt=AutomationReceiptProjection(
            request_id=uuid4(),
            profile_id=profile_id,
            stage=EnrollmentStage.REQUESTED,
            review_digest="a" * 64,
            grant_id=grant_id,
            key_id=None,
            credential_reference=None,
        ),
        client_id=uuid4(),
        destination_id=uuid4(),
        proposal=AutomationProposalProjection(
            kind=kind,
            scope=AutomationScopeProjection(
                operations=(),
                actions=(),
                disclosures=(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            expires_at=instant + timedelta(days=30),
            key_expires_at=instant + timedelta(days=15),
            unattended=False,
            allow_os_lock=False,
            target_grant_id=grant_id if kind is EnrollmentKind.RENEW else None,
            target_key_id=None,
        ),
        expires_at=instant + timedelta(minutes=5),
    )


def _contract(decision: Literal["approve", "decline"]) -> OperationPublicDefinitionContractV1:
    identity = (
        AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
        if decision == "approve"
        else AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
    )
    definition = next(item for item in build_automation_operation_definitions() if item.definition_id == identity)
    return build_automation_operation_registrations((definition,))[0].contract


def _refused_observation(
    *, contract: OperationPublicDefinitionContractV1, operation_id: str, subject_ref: str, refusal_ref: str
) -> OperationObservationSuccessV1:
    instant = now()
    contract_set = OperationPublicContractSetV1.build((contract,))
    projection = OperationPublicProjectionV1(
        operation_id=operation_id,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        revision=3,
        anchor_cursor=3,
        definition_contract=contract,
        contract_set_digest=contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=instant,
        updated_at=instant,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=refusal_ref,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    event_page = OperationPublicEventPageV1(
        operation_id=operation_id,
        anchor_cursor=3,
        requested_cursor=3,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=3,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=event_page)


class _DecisionClient(RuntimeFrontendClient):
    """A typed boundary script, with no service or native-transport claim."""

    def __init__(self, review: AutomationReviewProjection, *, decision: Literal["approve", "decline"]) -> None:
        self._profile_id = review.receipt.profile_id
        self._frontend = OperationFrontendProjection.CLI
        self._session_id = uuid4()
        self.review = review
        self.decision = decision
        self.operation_id = "b" * 64
        self.requests: list[RuntimeOperationRequest] = []
        self.secret_calls = 0
        self.close_calls = 0
        self.bad_requirement = False
        self.secret_failure = False
        self.terminal_refusal: str | None = None
        self.result_failure: Literal["none", "digest", "malformed", "rebind", "missing_key", "unexpected_key"] = "none"

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert deadline > 0 and definition_id == _contract(self.decision).definition_id
        return _contract(self.decision)

    @override
    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0
        self.requests.append(request)
        if isinstance(request, RuntimeOperationSubmit):
            identity = OperationIdentity(
                operation_id="c" * 64 if self.bad_requirement else self.operation_id,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            )
            requirement = (
                OperationSecretRequirement(
                    identity=identity,
                    interaction_id="d" * 64,
                    revision=0,
                    secret_kind="automation.password",  # noqa: S106 - declared channel kind, not a credential
                    expires_at=now() + timedelta(minutes=5),
                )
                if self.decision == "approve"
                else None
            )
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                receipt=OperationSubmissionReceiptV1(operation_id=self.operation_id, secret_requirement=requirement),
            )
        if isinstance(request, RuntimeOperationControl):
            return RuntimeOperationAcknowledged(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                operation_id=self.operation_id,
            )
        if isinstance(request, RuntimeOperationObserve):
            contract = _contract(self.decision)
            if self.terminal_refusal is not None:
                observation = _refused_observation(
                    contract=contract,
                    operation_id=self.operation_id,
                    subject_ref=profile_operation_subject(str(self.profile_id)),
                    refusal_ref=self.terminal_refusal,
                )
                return RuntimeOperationObserved(
                    request_id=request.request_id,
                    runtime_boot_id=UUID(int=1),
                    connection_id=UUID(int=2),
                    observation=observation,
                )
            state = OperationPublicProjectionV1.model_construct(
                operation_id=self.operation_id,
                definition_id=contract.definition_id,
                subject_ref=profile_operation_subject(str(self.profile_id)),
                definition_contract=contract,
                lifecycle=OperationLifecycle.TERMINAL,
                terminal_condition=OperationTerminalCondition.SUCCEEDED,
                effect=OperationEffect.UPDATED,
                revision=3,
            )
            observed = OperationObservationSuccessV1.model_construct(projection=state)
            return RuntimeOperationObserved.model_construct(observation=observed)
        raise AssertionError("unexpected operation request")

    @override
    def submit_secret(
        self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float = 20
    ) -> RuntimeOperationAcknowledged:
        assert timeout > 0 and requirement.secret_kind == "automation.password"  # noqa: S105 - channel kind
        self.secret_calls += 1
        if self.secret_failure:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        secret[:] = bytes(len(secret))
        return RuntimeOperationAcknowledged(
            request_id=uuid4(),
            runtime_boot_id=UUID(int=1),
            connection_id=UUID(int=2),
            operation_id=self.operation_id,
        )

    @override
    def read_result_document(
        self,
        result: OperationResultProjectionRequestV1,
        *,
        timeout: float = 60,
        deadline: float | None = None,
    ) -> dict[str, JsonValue]:
        assert deadline is None or deadline > 0
        assert timeout > 0 and result.operation_id == self.operation_id
        if self.result_failure == "malformed":
            return {"outcome": "success", "projection": {"private": "SENTINEL_PRIVATE_RESULT"}}
        original = self.review.receipt
        has_key = self.decision == "approve" and self.review.proposal.kind in {
            EnrollmentKind.ENROLL,
            EnrollmentKind.ROTATE,
        }
        if self.result_failure == "missing_key":
            has_key = False
        elif self.result_failure == "unexpected_key":
            has_key = True
        receipt = AutomationReceiptProjection(
            request_id=original.request_id,
            profile_id=original.profile_id,
            stage=EnrollmentStage.COMPLETE if self.decision == "approve" else EnrollmentStage.DECLINED,
            review_digest="e" * 64 if self.result_failure == "digest" else original.review_digest,
            grant_id=original.grant_id,
            key_id=uuid4() if has_key else None,
            credential_reference=uuid4() if has_key else None,
        )
        if self.result_failure == "rebind":
            self._session_id = uuid4()
        contract = _contract(self.decision)
        assert contract.result_schema is not None
        envelope = OperationResultProjectionSuccessV1[AutomationReceiptProjection](
            result_schema=contract.result_schema,
            definition_contract_digest=contract.definition_contract_digest,
            projection=receipt,
        )
        return TypeAdapter(dict[str, JsonValue]).validate_python(envelope.model_dump(mode="json"))

    @override
    def close(self) -> None:
        self.close_calls += 1


def test_decline_uses_exact_review_once_and_never_asks_for_secret() -> None:
    review = _review(uuid4())
    client = _DecisionClient(review, decision="decline")
    completed = run_automation_decision(client, review, decision="decline")
    assert completed.operation_id == client.operation_id
    assert completed.receipt.stage is EnrollmentStage.DECLINED
    assert completed.effect is OperationEffect.UPDATED
    submits = [item for item in client.requests if isinstance(item, RuntimeOperationSubmit)]
    starts = [item for item in client.requests if isinstance(item, RuntimeOperationControl)]
    assert len(submits) == len(starts) == 1
    payload = AutomationOperationRequest.model_validate_json(submits[0].payload_json)
    assert (payload.profile_id, payload.request_id, payload.review_digest) == (
        review.receipt.profile_id,
        review.receipt.request_id,
        review.receipt.review_digest,
    )
    assert client.secret_calls == client.close_calls == 0


def test_terminal_refusal_keeps_the_public_refusal_reference_and_observed_context() -> None:
    review = _review(uuid4())
    client = _DecisionClient(review, decision="decline")
    client.terminal_refusal = "refusal:decision.denied"

    with pytest.raises(AutomationDecisionRunError) as failed:
        run_automation_decision(client, review, decision="decline")

    assert failed.value.reason == client.terminal_refusal
    assert failed.value.context == {
        "reason": client.terminal_refusal,
        "operation_id": client.operation_id,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationSubmit)]) == 1
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationControl)]) == 1
    assert client.secret_calls == client.close_calls == 0


def test_approval_wipes_preflight_and_wrong_requirement_proofs() -> None:
    review = _review(uuid4())
    wrong = _DecisionClient(review, decision="approve")
    wrong._profile_id = uuid4()
    before = bytearray(b"proof-before-submission")
    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        run_automation_decision(wrong, review, decision="approve", password=before)
    assert refused.value.reason == AccessDenialCode.PROFILE_MISMATCH.value
    assert before == bytes(len(before)) and wrong.requests == []

    client = _DecisionClient(review, decision="approve")
    client.bad_requirement = True
    after = bytearray(b"proof-after-submission")
    with pytest.raises(AutomationDecisionRunError) as failed:
        run_automation_decision(client, review, decision="approve", password=after)
    assert after == bytes(len(after))
    assert failed.value.operation_id == client.operation_id
    assert failed.value.effect is None and failed.value.context is not None
    assert failed.value.context["effect"] == "unknown"
    assert client.secret_calls == client.close_calls == 0
    assert len(client.requests) == 1


@pytest.mark.parametrize("kind", [EnrollmentKind.ENROLL, EnrollmentKind.RENEW])
def test_approval_accepts_only_the_reviewed_kind_of_completed_receipt(kind: EnrollmentKind) -> None:
    review = _review(uuid4(), kind=kind)
    client = _DecisionClient(review, decision="approve")
    password = bytearray(b"DECISION_PROOF")
    completed = run_automation_decision(client, review, decision="approve", password=password)
    assert password == bytes(len(password))
    assert completed.operation_id == client.operation_id
    assert completed.receipt.stage is EnrollmentStage.COMPLETE
    assert (completed.receipt.key_id is not None) is (kind is EnrollmentKind.ENROLL)
    assert (completed.receipt.credential_reference is not None) is (kind is EnrollmentKind.ENROLL)
    assert completed.effect is OperationEffect.UPDATED
    assert client.secret_calls == 1 and client.close_calls == 0
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationSubmit)]) == 1
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationControl)]) == 1


@pytest.mark.parametrize(
    ("kind", "failure"),
    [
        (EnrollmentKind.ENROLL, "missing_key"),
        (EnrollmentKind.RENEW, "unexpected_key"),
    ],
)
def test_approval_rejects_completed_receipt_for_wrong_reviewed_kind(
    kind: EnrollmentKind, failure: Literal["missing_key", "unexpected_key"]
) -> None:
    review = _review(uuid4(), kind=kind)
    client = _DecisionClient(review, decision="approve")
    client.result_failure = failure
    password = bytearray(b"DECISION_PROOF")
    with pytest.raises(AutomationDecisionRunError) as failed:
        run_automation_decision(client, review, decision="approve", password=password)
    assert password == bytes(len(password))
    assert failed.value.operation_id == client.operation_id
    assert failed.value.reason == RuntimeRefusalCode.INVALID_FRAME.value
    assert failed.value.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert failed.value.effect is OperationEffect.UPDATED
    assert failed.value.__cause__ is None
    assert client.close_calls == 0


def test_secret_delivery_loss_retains_one_submission_without_sensitive_cause() -> None:
    review = _review(uuid4())
    client = _DecisionClient(review, decision="approve")
    client.secret_failure = True
    password = bytearray(b"UNIQUE_DECISION_PROOF")
    with pytest.raises(AutomationDecisionRunError) as failed:
        run_automation_decision(client, review, decision="approve", password=password)
    assert password == bytes(len(password))
    assert failed.value.operation_id == client.operation_id
    assert failed.value.reason == RuntimeRefusalCode.CONNECTION_CLOSED.value
    assert failed.value.terminal_condition is None and failed.value.effect is None
    assert failed.value.__cause__ is None
    assert "UNIQUE_DECISION_PROOF" not in str(failed.value)
    assert client.secret_calls == 1 and client.close_calls == 0
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationSubmit)]) == 1
    assert not any(isinstance(item, RuntimeOperationControl) for item in client.requests)


@pytest.mark.parametrize("failure", ["digest", "malformed", "rebind"])
def test_result_mismatch_never_loses_the_observed_effect(failure: Literal["digest", "malformed", "rebind"]) -> None:
    review = _review(uuid4())
    client = _DecisionClient(review, decision="decline")
    client.result_failure = failure
    with pytest.raises(AutomationDecisionRunError) as failed:
        run_automation_decision(client, review, decision="decline")
    assert failed.value.operation_id == client.operation_id
    assert failed.value.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert failed.value.effect is OperationEffect.UPDATED
    assert failed.value.reason == RuntimeRefusalCode.INVALID_FRAME.value
    assert failed.value.__cause__ is None
    assert "SENTINEL_PRIVATE_RESULT" not in str(failed.value)
    assert client.close_calls == 0
    assert len([item for item in client.requests if isinstance(item, RuntimeOperationSubmit)]) == 1

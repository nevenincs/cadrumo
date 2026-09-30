"""The CLI censal bridge carries exact scope through reviewed settlement."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicTerminalEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.interactions import OperationResponseIntent
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationManaged,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalFieldIntent,
    CensalOperationOutcome,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewFieldProjectionV1,
    CensalReviewProjectionV1,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.cli.config.runtime_censal_review import review_censal_with_runtime
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

_PROFILE_ID = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "c" * 64
_INTERACTION_ID = "d" * 64
_NOW = datetime(2026, 9, 29, tzinfo=UTC)
_RESULT_DIGEST = "e" * 64
_BOOT_ID = UUID("cc000000-0000-4000-8000-0000000000cc")
_CONNECTION_ID = UUID("dd000000-0000-4000-8000-0000000000dd")

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _contract() -> OperationPublicDefinitionContractV1:
    unused_port = cast(Any, None)
    definition = build_censal_operation_definition(
        certificate_secret_backend_factory=unused_port,
        browser_session_factory=unused_port,
        operator_scope_ports=unused_port,
        censal_fetch_port=unused_port,
    )
    return build_censal_operation_registration(definition).contract


def _request(profile_id: UUID = _PROFILE_ID) -> CensalOperationRequest:
    return CensalOperationRequest(
        baseline=CensalProfileBaseline(profile_id=str(profile_id), record_revision=1, content_digest="a" * 64),
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )


class _RuntimeClient:
    """Protocol-shaped client that checks each wire exchange's connection scope."""

    profile_id = _PROFILE_ID
    session_id = _SESSION_ID
    frontend = OperationFrontendProjection.CLI

    def __init__(
        self,
        *,
        refuse_before_review: bool = False,
        terminal_effect_override: OperationEffect | None = None,
        result_outcome_override: CensalOperationOutcome | None = None,
    ) -> None:
        self.public_contract = _contract()
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.review_projection = CensalReviewProjectionV1(
            projection_version=1,
            fields=tuple(
                CensalReviewFieldProjectionV1(
                    path=item.path,
                    intent=item.intent,
                    observed_value=f"reviewed:{item.path}",
                )
                for item in _request().field_intents
            ),
        )
        self.refuse_before_review = refuse_before_review
        self.terminal_effect_override = terminal_effect_override
        self.result_outcome_override = result_outcome_override
        self.requests: list[RuntimeOperationRequest] = []
        self.contract_reads: list[str] = []
        self.response_action: str | None = None
        self.result_ref: str | None = None
        self.terminal_effect: OperationEffect | None = None

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert deadline > 0
        self.contract_reads.append(definition_id)
        return self.public_contract

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0
        assert request.profile_id == self.profile_id
        assert request.session_id == self.session_id
        self.requests.append(request)

        if isinstance(request, RuntimeOperationSubmit):
            assert request.definition_id == CENSAL_OPERATION_DEFINITION_ID
            assert request.subject_ref == str(self.profile_id)
            assert CensalOperationRequest.model_validate_json(request.payload_json).baseline.profile_id == str(
                self.profile_id
            )
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=_BOOT_ID,
                connection_id=_CONNECTION_ID,
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=None),
            )

        if isinstance(request, RuntimeOperationControl):
            assert request.action == "operation_start"
            assert request.operation_id == _OPERATION_ID
            return RuntimeOperationAcknowledged(
                request_id=request.request_id,
                runtime_boot_id=_BOOT_ID,
                connection_id=_CONNECTION_ID,
                operation_id=_OPERATION_ID,
            )

        if isinstance(request, RuntimeOperationObserve):
            assert request.observation.operation_id == _OPERATION_ID
            observation = self._observation(terminal=self.response_action is not None or self.refuse_before_review)
            return RuntimeOperationObserved(
                request_id=request.request_id,
                runtime_boot_id=_BOOT_ID,
                connection_id=_CONNECTION_ID,
                observation=observation,
            )

        if isinstance(request, RuntimeOperationReview):
            reference = request.review.reference
            assert reference.operation_id == _OPERATION_ID
            assert reference.review_projection_schema == CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
            success = OperationReviewProjectionSuccessV1[CensalReviewProjectionV1](
                projection_schema=CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=self.review_projection,
            )
            return RuntimeOperationProjected(
                request_id=request.request_id,
                runtime_boot_id=_BOOT_ID,
                connection_id=_CONNECTION_ID,
                operation_id=_OPERATION_ID,
                projection_kind="review",
                document=json.loads(success.model_dump_json()),
            )

        if isinstance(request, RuntimeOperationManage):
            management = request.management
            if isinstance(management, (OperationResponseApplyRequestV1, OperationResponseRejectRequestV1)):
                assert management.operation_id == _OPERATION_ID
                self.response_action = management.response_action
                success = OperationResponseMutationSuccessV1(
                    operation_id=_OPERATION_ID,
                    interaction_id=_INTERACTION_ID,
                    revision=4,
                    response_action=management.response_action,
                )
            else:
                assert isinstance(management, OperationResponseControlRequestV1)
                assert management.operation_id == _OPERATION_ID
                assert management.actor_ref == f"session:{self.session_id}"
                success = OperationResponseControlSuccessV1(
                    operation_id=_OPERATION_ID,
                    interaction_id=_INTERACTION_ID,
                    revision=4,
                    available=True,
                    permitted_intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
                )
            return RuntimeOperationManaged(
                request_id=request.request_id,
                runtime_boot_id=_BOOT_ID,
                connection_id=_CONNECTION_ID,
                operation_id=_OPERATION_ID,
                document=json.loads(success.model_dump_json()),
            )

        raise AssertionError(f"unexpected runtime request: {type(request).__name__}")

    def _observation(self, *, terminal: bool) -> OperationObservationSuccessV1:
        contract = self.public_contract
        pending = OperationReviewAvailableInteractionV1(
            operation_id=_OPERATION_ID,
            interaction_id=_INTERACTION_ID,
            revision=4,
            presentation_code="censo.interaction-wait",
            response_schema=CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity,
            expires_at=None,
            review_reference=OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION_ID,
                interaction_id=_INTERACTION_ID,
                revision=4,
                review_projection_schema=CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=None,
            ),
        )
        if terminal and self.refuse_before_review:
            lifecycle = OperationLifecycle.TERMINAL
            condition = OperationTerminalCondition.REFUSED
            effect = OperationEffect.NONE
            result_ref = None
            refusal_ref = "censal.review.unavailable"
            phase_code = "censo.settlement"
        elif terminal:
            lifecycle = OperationLifecycle.TERMINAL
            condition = OperationTerminalCondition.SUCCEEDED
            expected_effect = OperationEffect.UPDATED if self.response_action == "apply" else OperationEffect.NONE
            effect = self.terminal_effect_override or expected_effect
            expected_outcome = (
                CensalOperationOutcome.APPLIED if self.response_action == "apply" else CensalOperationOutcome.REJECTED
            )
            outcome = self.result_outcome_override or expected_outcome
            result_ref = f"censo-review:{_RESULT_DIGEST}:{outcome}"
            refusal_ref = None
            self.result_ref = result_ref
            phase_code = "censo.settlement"
        else:
            lifecycle = OperationLifecycle.WAITING_FOR_INTERACTION
            condition = None
            effect = OperationEffect.NONE
            result_ref = None
            refusal_ref = None
            phase_code = "censo.interaction-wait"

        cursor = 2 if terminal else 1
        if terminal:
            self.terminal_effect = effect
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION_ID,
            definition_id=CENSAL_OPERATION_DEFINITION_ID,
            subject_ref=str(self.profile_id),
            revision=5 if terminal else 4,
            anchor_cursor=cursor,
            definition_contract=contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=lifecycle,
            terminal_condition=condition,
            effect=effect,
            phase_code=phase_code,
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=not terminal,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1() if terminal else pending,
            result_ref=result_ref,
            refusal_ref=refusal_ref,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        first_event = OperationPublicPhaseEventV1(
            revision=4,
            sequence=1,
            timestamp=_NOW,
            code="censo.interaction-wait",
            phase_code="censo.interaction-wait",
        )
        events: tuple[OperationPublicPhaseEventV1 | OperationPublicTerminalEventV1, ...]
        if terminal:
            events = (
                first_event,
                OperationPublicTerminalEventV1(
                    revision=5,
                    sequence=2,
                    timestamp=_NOW,
                    code="operation.terminal",
                    condition=condition,
                    effect=effect,
                    result_ref=result_ref,
                    refusal_ref=refusal_ref,
                    failure_error_code=None,
                    diagnostic_ref=None,
                ),
            )
        else:
            events = (first_event,)
        page = OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=cursor,
            requested_cursor=0,
            status=OperationReplayStatus.PAGE,
            events=events,
            next_cursor=cursor,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=page)


@pytest.mark.parametrize(
    ("apply", "expected_effect", "expected_outcome"),
    [
        (True, OperationEffect.UPDATED, CensalOperationOutcome.APPLIED),
        (False, OperationEffect.NONE, CensalOperationOutcome.REJECTED),
    ],
)
def test_review_bridge_uses_exact_session_projection_and_terminal_decision(
    apply: bool,
    expected_effect: OperationEffect,
    expected_outcome: CensalOperationOutcome,
) -> None:
    client = _RuntimeClient()
    request = _request()
    seen_projection: list[CensalReviewProjectionV1] = []

    result = review_censal_with_runtime(
        cast(RuntimeFrontendClient, client),
        request,
        decide=lambda projection: seen_projection.append(projection) or apply,
    )

    assert client.contract_reads == [CENSAL_OPERATION_DEFINITION_ID]
    assert OperationFrontendProjection.CLI in client.public_contract.permitted_frontends
    assert all(
        exchange.profile_id == client.profile_id and exchange.session_id == client.session_id
        for exchange in client.requests
    )
    submitted = next(exchange for exchange in client.requests if isinstance(exchange, RuntimeOperationSubmit))
    assert submitted.subject_ref == str(client.profile_id)
    assert CensalOperationRequest.model_validate_json(submitted.payload_json) == request
    assert seen_projection == [client.review_projection]
    assert result.projection == client.review_projection
    assert result.applied is apply
    assert client.response_action == ("apply" if apply else "reject")
    assert client.terminal_effect is expected_effect
    assert client.result_ref == f"censo-review:{_RESULT_DIGEST}:{expected_outcome.value}"
    terminal_observation = next(
        exchange for exchange in reversed(client.requests) if isinstance(exchange, RuntimeOperationObserve)
    )
    assert terminal_observation.profile_id == client.profile_id
    assert terminal_observation.session_id == client.session_id


def test_review_refusal_retains_submitted_operation_identity_and_effect() -> None:
    client = _RuntimeClient(refuse_before_review=True)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        review_censal_with_runtime(cast(RuntimeFrontendClient, client), _request(), decide=lambda _projection: True)

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert refused.value.context["terminal_condition"] == OperationTerminalCondition.REFUSED.value


@pytest.mark.parametrize(
    ("apply", "effect_override", "outcome_override", "observed_effect"),
    [
        (True, OperationEffect.NONE, None, OperationEffect.NONE),
        (False, None, CensalOperationOutcome.APPLIED, OperationEffect.NONE),
    ],
)
def test_review_refuses_a_terminal_effect_or_result_outcome_mismatch_with_identity(
    apply: bool,
    effect_override: OperationEffect | None,
    outcome_override: CensalOperationOutcome | None,
    observed_effect: OperationEffect,
) -> None:
    client = _RuntimeClient(
        terminal_effect_override=effect_override,
        result_outcome_override=outcome_override,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        review_censal_with_runtime(cast(RuntimeFrontendClient, client), _request(), decide=lambda _review: apply)

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == observed_effect.value
    assert refused.value.context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value

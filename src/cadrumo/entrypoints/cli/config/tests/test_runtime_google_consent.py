"""Google consent wire correlation and real terminal refusal, with no browser/provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

import pytest

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.outbound.google.errors import GoogleAuthNonInteractiveError
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from .....application.operations.interactions import OperationResponseIntent
from .....application.operations.models import OperationIdentity
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from .....application.runtime.operation_access import (
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
from .....application.user_profile.google_configuration_operation import (
    build_google_configuration_definitions,
    build_google_configuration_registration,
)
from .....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
    GoogleLoginProjection,
    GoogleLoginRequest,
)
from .....application.user_profile.google_configuration_operation_ports import GoogleConfigurationOperationPorts
from .....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....cli.errors import CliRefusedBoundaryError
from .. import google_consent_review
from .. import runtime_google_consent as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = UUID("68686868-6868-4686-8686-686868686868")
_SESSION = UUID("69696969-6969-4696-8696-696969696969")
_BOOT = UUID("70707070-7070-4707-8707-707070707070")
_CONNECTION = UUID("71717171-7171-4717-8717-717171717171")
_NOW = datetime.now(UTC)
_OPERATION = "a" * 64
_INTERACTION = "b" * 64


class _ReplyFields(TypedDict):
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class _Client:
    """Closed runtime reply fixture; it exercises frontend transport, not native custody."""

    profile_id = _PROFILE
    session_id = _SESSION
    frontend = OperationFrontendProjection.CLI

    def __init__(self, *, substitute_review: bool = False, change_session: bool = False) -> None:
        def unused(**_kwargs: object) -> GoogleConfigurationOperationPorts:
            pytest.fail("contract fixture acquired provider capabilities")

        definition = next(
            item
            for item in build_google_configuration_definitions(unused)
            if item.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        )
        self.public_contract = build_google_configuration_registration(definition).contract
        self.requests: list[RuntimeOperationRequest] = []
        self.applied = False
        self.rejected = False
        self.substitute_review = substitute_review
        self.change_session = change_session

    def contract(self, definition_id: str, *, deadline: float):
        assert definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID and deadline > 0
        return self.public_contract

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0 and request.profile_id == _PROFILE and request.session_id == _SESSION
        self.requests.append(request)
        common: _ReplyFields = {
            "request_id": request.request_id,
            "runtime_boot_id": _BOOT,
            "connection_id": _CONNECTION,
        }
        if isinstance(request, RuntimeOperationSubmit):
            assert request.subject_ref == profile_operation_subject(str(_PROFILE))
            assert GoogleLoginRequest.model_validate_json(request.payload_json) == GoogleLoginRequest(
                profile_id=_PROFILE
            )
            return RuntimeOperationSubmitted(
                **common, receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None)
            )
        if isinstance(request, RuntimeOperationControl):
            return RuntimeOperationAcknowledged(**common, operation_id=_OPERATION)
        if isinstance(request, RuntimeOperationObserve):
            return RuntimeOperationObserved(**common, observation=self._observation())
        if isinstance(request, RuntimeOperationReview):
            assert request.review.reference.operation_id == _OPERATION and request.review.reference.revision == 4
            proposal = GoogleConsentProposal(
                identity=OperationIdentity(
                    operation_id=_OPERATION,
                    definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                revision=4,
                request=GoogleLoginRequest(profile_id=_PROFILE),
            )
            projection = GoogleConsentReviewProjection(
                identity=proposal.identity,
                revision=4,
                profile_id=_PROFILE,
                reviewed_proposal_digest="c" * 64 if self.substitute_review else proposal.digest,
            )
            assert self.public_contract.review_projection_schema is not None
            review_envelope = OperationReviewProjectionSuccessV1[GoogleConsentReviewProjection](
                projection_schema=self.public_contract.review_projection_schema,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=projection,
            )
            if self.change_session:
                self.session_id = UUID("72727272-7272-4727-8727-727272727272")
            return RuntimeOperationProjected(
                **common,
                operation_id=_OPERATION,
                projection_kind="review",
                document=review_envelope.model_dump(mode="json"),
            )
        if isinstance(request, RuntimeOperationManage):
            management = request.management
            assert isinstance(
                management,
                (OperationResponseControlRequestV1, OperationResponseApplyRequestV1, OperationResponseRejectRequestV1),
            )
            assert (
                management.operation_id == _OPERATION
                and management.interaction_id == _INTERACTION
                and management.revision == 4
            )
            assert management.actor_ref == f"session:{_SESSION}"
            if not isinstance(management, (OperationResponseApplyRequestV1, OperationResponseRejectRequestV1)):
                control_envelope = OperationResponseControlSuccessV1(
                    operation_id=_OPERATION,
                    interaction_id=_INTERACTION,
                    revision=4,
                    available=True,
                    permitted_intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
                )
                document = control_envelope.model_dump(mode="json")
            else:
                self.applied = isinstance(management, OperationResponseApplyRequestV1)
                self.rejected = isinstance(management, OperationResponseRejectRequestV1)
                assert self.applied or self.rejected
                mutation_envelope = OperationResponseMutationSuccessV1(
                    operation_id=_OPERATION,
                    interaction_id=_INTERACTION,
                    revision=4,
                    response_action="apply" if self.applied else "reject",
                )
                document = mutation_envelope.model_dump(mode="json")
            return RuntimeOperationManaged(**common, operation_id=_OPERATION, document=document)
        pytest.fail("unexpected Google consent wire request")

    def _observation(self) -> OperationObservationSuccessV1:
        contract = self.public_contract
        assert contract.review_projection_schema is not None and contract.interaction_response_schema is not None
        pending = OperationReviewAvailableInteractionV1(
            operation_id=_OPERATION,
            interaction_id=_INTERACTION,
            revision=4,
            presentation_code=GOOGLE_CONSENT_PRESENTATION_CODE,
            response_schema=contract.interaction_response_schema,
            expires_at=None,
            review_reference=OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION,
                interaction_id=_INTERACTION,
                revision=4,
                review_projection_schema=contract.review_projection_schema,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=None,
            ),
        )
        terminal = self.applied
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION,
            definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            revision=5 if terminal else 4,
            anchor_cursor=1,
            definition_contract=contract,
            contract_set_digest=OperationPublicContractSetV1.build((contract,)).contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.WAITING_FOR_INTERACTION,
            terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
            effect=OperationEffect.UPDATED if terminal else OperationEffect.NONE,
            phase_code=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1() if terminal else pending,
            result_ref="d" * 64 if terminal else None,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        event = OperationPublicPhaseEventV1(
            revision=4,
            sequence=1,
            timestamp=_NOW,
            code=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            phase_code=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
        )
        return OperationObservationSuccessV1(
            projection=projection,
            event_page=OperationPublicEventPageV1(
                operation_id=_OPERATION,
                anchor_cursor=1,
                requested_cursor=0,
                status=OperationReplayStatus.PAGE,
                events=(event,),
                next_cursor=1,
                restart_cursor=None,
            ),
        )

    def read_result_document(self, request: OperationResultProjectionRequestV1, *, timeout: float):
        assert self.applied and timeout > 0 and request.operation_id == _OPERATION and request.terminal_revision == 5
        assert self.public_contract.result_schema is not None
        assert request.result_schema == self.public_contract.result_schema
        envelope = OperationResultProjectionSuccessV1[GoogleConfigurationOutcome](
            result_schema=request.result_schema,
            definition_contract_digest=self.public_contract.definition_contract_digest,
            projection=GoogleConfigurationOutcome(
                profile_id=_PROFILE,
                outcome="succeeded",
                result=GoogleLoginProjection(
                    profile_id=_PROFILE,
                    account_email="synthetic@example.invalid",
                    root_folder_id="synthetic-root-folder",
                ),
            ),
        )
        return envelope.model_dump(mode="json")


def _as_runtime(client: _Client) -> RuntimeFrontendClient:
    # CAST-RATIONALE-GOOGLE-CONSENT-CLIENT-FIXTURE: this explicit typed wire double
    # implements the exact invoked client methods; it claims no native facility.
    return cast(RuntimeFrontendClient, cast(object, client))


def test_browser_bridge_checks_terminal_after_review_and_before_exact_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()

    def terminal() -> None:
        assert any(isinstance(item, RuntimeOperationReview) for item in client.requests)
        assert not any(isinstance(item, RuntimeOperationManage) for item in client.requests)

    monkeypatch.setattr(google_consent_review, "require_interactive_terminal", terminal)
    result = bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))
    assert result.operation_id == _OPERATION and result.effect is OperationEffect.UPDATED
    assert isinstance(result.projection.result, GoogleLoginProjection)
    assert result.projection.result.account_email == "synthetic@example.invalid"
    assert client.applied and not client.rejected


def test_noninteractive_terminal_preserves_canonical_verdict_and_rejects_exact_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    class NonInteractive:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", NonInteractive())
    client = _Client()
    with pytest.raises(GoogleAuthNonInteractiveError) as caught:
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))
    assert caught.value.terminal_precondition_verdict is not None
    assert (
        caught.value.terminal_precondition_verdict.failed_condition_id == "google.auth.interactive_terminal.available"
    )
    assert client.rejected and not client.applied
    assert caught.value.context is not None and caught.value.context["operation_id"] == _OPERATION


@pytest.mark.parametrize("kwargs", [{"substitute_review": True}, {"change_session": True}])
def test_substituted_review_or_changed_session_never_gets_human_apply(kwargs: dict[str, bool]) -> None:
    client = _Client(**kwargs)
    with pytest.raises(CliRefusedBoundaryError):
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))
    assert not client.applied and not client.rejected

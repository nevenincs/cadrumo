"""Google consent wire correlation and real terminal refusal, with no browser/provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypedDict, cast, override
from uuid import UUID

import pytest

from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
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
from cadrumo.application.operations.interactions import OperationResponseIntent
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.user_profile.google_configuration_operation import (
    build_google_configuration_definitions,
    build_google_configuration_registration,
)
from cadrumo.application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
    GoogleLoginProjection,
    GoogleLoginRequest,
)
from cadrumo.application.user_profile.google_configuration_operation_ports import GoogleConfigurationOperationPorts
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo_client.commands import google_consent_review
from cadrumo_client.commands import runtime_google_consent as bridge
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.google_configuration_receipt_correlation import correlate_google_completion
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationManage,
    OperationManaged,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationReply,
    OperationRequest,
    OperationReview,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.transport.frontend_client import FrontendClient

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
        self.requests: list[OperationRequest] = []
        self.applied = False
        self.rejected = False
        self.substitute_review = substitute_review
        self.change_session = change_session

    def contract(self, definition_id: str, *, deadline: float):
        assert definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID and deadline > 0
        return self.public_contract

    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        # Every reply is settled when it is sent, so the fixture never cues a re-observation.
        return lambda: None

    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        assert deadline > 0 and request.profile_id == _PROFILE and request.session_id == _SESSION
        self.requests.append(request)
        common: _ReplyFields = {
            "request_id": request.request_id,
            "runtime_boot_id": _BOOT,
            "connection_id": _CONNECTION,
        }
        if isinstance(request, OperationSubmit):
            assert request.subject_ref == profile_operation_subject(str(_PROFILE))
            assert GoogleLoginRequest.model_validate_json(request.payload_json) == GoogleLoginRequest(
                profile_id=_PROFILE
            )
            return OperationSubmitted(
                **common, receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None)
            )
        if isinstance(request, OperationControl):
            return OperationAcknowledged(**common, operation_id=_OPERATION)
        if isinstance(request, OperationObserve):
            return OperationObserved(**common, observation=self._observation())
        if isinstance(request, OperationReview):
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
            return OperationProjected(
                **common,
                operation_id=_OPERATION,
                projection_kind="review",
                document=review_envelope.model_dump(mode="json"),
            )
        if isinstance(request, OperationManage):
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
            return OperationManaged(**common, operation_id=_OPERATION, document=document)
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


def _as_runtime(client: _Client) -> FrontendClient:
    # CAST-RATIONALE-GOOGLE-CONSENT-CLIENT-FIXTURE: this explicit typed wire double
    # implements the exact invoked client methods; it claims no native facility.
    return cast(FrontendClient, cast(object, client))


def test_browser_bridge_checks_terminal_after_review_and_before_exact_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()

    def terminal() -> None:
        assert any(isinstance(item, OperationReview) for item in client.requests)
        assert not any(isinstance(item, OperationManage) for item in client.requests)

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
    with pytest.raises(CadrumoError) as caught:
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))
    # The refusal is the registered non-interactive one, by its public code.
    assert get_registered_error_code(caught.value).code == "REFUSED_GOOGLE_NON_INTERACTIVE"
    verdict = nested_terminal_precondition_verdict(caught.value)
    assert verdict is not None
    assert verdict.failed_condition_id == "google.auth.interactive_terminal.available"
    assert client.rejected and not client.applied
    assert caught.value.context is not None and caught.value.context["operation_id"] == _OPERATION


@pytest.mark.parametrize("kwargs", [{"substitute_review": True}, {"change_session": True}])
def test_substituted_review_or_changed_session_never_gets_human_apply(kwargs: dict[str, bool]) -> None:
    client = _Client(**kwargs)
    with pytest.raises(CliRefusedBoundaryError):
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))
    assert not client.applied and not client.rejected


_PERSON_FRONTENDS = (
    OperationFrontendProjection.CLI,
    OperationFrontendProjection.TUI,
    OperationFrontendProjection.DESKTOP,
)
# ``external-client`` is every delegated client, the MCP harness among them;
# ``installed-service`` is the agent service and automation.
_NON_PERSON_FRONTENDS = (
    OperationFrontendProjection.EXTERNAL_CLIENT,
    OperationFrontendProjection.INSTALLED_SERVICE,
)


class _FrontendClient(_Client):
    """The same closed wire fixture, bound to a chosen frontend that may change at one step."""

    def __init__(
        self,
        frontend: OperationFrontendProjection,
        *,
        after_submit: OperationFrontendProjection | None = None,
        at_result: OperationFrontendProjection | None = None,
    ) -> None:
        super().__init__()
        self.frontend = frontend
        self.after_submit = after_submit
        self.at_result = at_result

    @override
    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        reply = super().operation(request, deadline=deadline)
        if isinstance(request, OperationSubmit) and self.after_submit is not None:
            self.frontend = self.after_submit
        return reply

    @override
    def read_result_document(self, request: OperationResultProjectionRequestV1, *, timeout: float):
        document = super().read_result_document(request, timeout=timeout)
        if self.at_result is not None:
            self.frontend = self.at_result
        return document


def test_the_frontend_sets_partition_every_frontend() -> None:
    assert set(_PERSON_FRONTENDS) | set(_NON_PERSON_FRONTENDS) == set(OperationFrontendProjection)
    assert not set(_PERSON_FRONTENDS) & set(_NON_PERSON_FRONTENDS)


@pytest.mark.parametrize("frontend", _PERSON_FRONTENDS)
def test_every_person_frontend_signs_in_through_the_one_consent_exchange(
    frontend: OperationFrontendProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(google_consent_review, "require_interactive_terminal", lambda: None)
    client = _FrontendClient(frontend)
    request = GoogleLoginRequest(profile_id=_PROFILE)

    completed = bridge.login_google_with_runtime(_as_runtime(client), request)
    correlate_google_completion(
        _as_runtime(client),
        request,
        completed,
        definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
        expected_projection_type=GoogleLoginProjection,
    )

    assert client.applied and not client.rejected
    assert isinstance(completed.projection.result, GoogleLoginProjection)


@pytest.mark.parametrize("frontend", _NON_PERSON_FRONTENDS)
def test_a_non_person_frontend_is_refused_before_anything_is_submitted(frontend: OperationFrontendProjection) -> None:
    client = _FrontendClient(frontend)

    with pytest.raises(RefusalError) as refused:
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))

    assert type(refused.value) is RefusalError and refused.value.reason is RefusalCode.INVALID_FRAME
    assert client.requests == [] and not client.applied


@pytest.mark.parametrize("frontend", _NON_PERSON_FRONTENDS)
def test_a_connection_that_stops_being_a_persons_during_an_exchange_is_closed(
    frontend: OperationFrontendProjection,
) -> None:
    """The exchange checks the connection again once the reply arrives, before the reply is used."""
    client = _FrontendClient(OperationFrontendProjection.DESKTOP, after_submit=frontend)

    with pytest.raises(RefusalError) as refused:
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))

    assert type(refused.value) is RefusalError and refused.value.reason is RefusalCode.CONNECTION_CLOSED
    assert [type(item) for item in client.requests] == [OperationSubmit]
    assert not client.applied


@pytest.mark.parametrize("frontend", _NON_PERSON_FRONTENDS)
def test_a_result_read_by_a_non_person_connection_is_an_invalid_frame(
    frontend: OperationFrontendProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(google_consent_review, "require_interactive_terminal", lambda: None)
    client = _FrontendClient(OperationFrontendProjection.TUI, at_result=frontend)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.login_google_with_runtime(_as_runtime(client), GoogleLoginRequest(profile_id=_PROFILE))

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RefusalCode.INVALID_FRAME.value
    assert refused.value.context["operation_id"] == _OPERATION


@pytest.mark.parametrize("frontend", _NON_PERSON_FRONTENDS)
def test_a_completion_correlated_on_a_non_person_connection_is_an_invalid_frame(
    frontend: OperationFrontendProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(google_consent_review, "require_interactive_terminal", lambda: None)
    client = _FrontendClient(OperationFrontendProjection.DESKTOP)
    request = GoogleLoginRequest(profile_id=_PROFILE)
    completed = bridge.login_google_with_runtime(_as_runtime(client), request)
    client.frontend = frontend

    with pytest.raises(CliRefusedBoundaryError) as refused:
        correlate_google_completion(
            _as_runtime(client),
            request,
            completed,
            definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            expected_projection_type=GoogleLoginProjection,
        )

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RefusalCode.INVALID_FRAME.value
    assert refused.value.context["operation_id"] == _OPERATION

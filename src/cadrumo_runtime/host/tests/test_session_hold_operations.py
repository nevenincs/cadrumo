"""The held person bridge's generic relay: submit, observe, result, review answered by digest, and cancel.

The fake runtime serves real registered contracts so every document the relay
passes on validates as the runtime would publish it; the relay itself is given
only a definition id, a subject and a request object.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.application.user_profile.google_configuration_operation import (
    build_google_configuration_definitions,
    build_google_configuration_registration,
)
from cadrumo.application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConsentReviewProjection,
    GoogleStatusProjection,
)
from cadrumo.application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationOperationPortsFactory,
)
from cadrumo.application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
)
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import (
    OperationCancellation,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts import deadline_budget
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationFinancialInput,
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
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import (
    CustodyRecoveringEffectUnknownError,
    CustodyRecoveringError,
    FrontendRefusedError,
)
from cadrumo_runtime.host.session_hold_operations import (
    RELAY_ACTION_KEYS,
    OperationRelay,
    RelayRefusedError,
    relay_reply,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 10, 18, 9, tzinfo=UTC)
_PROFILE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_SESSION = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_BOOT = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_CONNECTION = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
_DOCUMENT = TypeAdapter(dict[str, JsonValue])
_SUBJECT = f"profile:{_PROFILE}"
_PROFILE_PAYLOAD: dict[str, object] = {"profile_id": str(_PROFILE)}


def _unbuilt_registry(*_arguments: object) -> object:
    raise AssertionError("the hold never runs an operation itself")


_GOOGLE_DEFINITIONS = build_google_configuration_definitions(
    cast(GoogleConfigurationOperationPortsFactory, _unbuilt_registry)
)
_REGISTRY = OperationRegistry(
    definitions=tuple(sorted(_GOOGLE_DEFINITIONS, key=lambda definition: definition.definition_id)),
    public_registrations=tuple(
        sorted(
            (build_google_configuration_registration(definition) for definition in _GOOGLE_DEFINITIONS),
            key=lambda registration: registration.contract.definition_id,
        )
    ),
)


def _contract(definition_id: str) -> OperationPublicDefinitionContractV1:
    return _REGISTRY.lookup_public_contract(definition_id)


def _json(model: BaseModel) -> dict[str, JsonValue]:
    return _DOCUMENT.validate_python(model.model_dump(mode="json"))


def _review(operation_id: str, revision: int, proposal: str) -> GoogleConsentReviewProjection:
    return GoogleConsentReviewProjection(
        identity=OperationIdentity(
            operation_id=operation_id, definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID, subject_ref=_SUBJECT
        ),
        revision=revision,
        profile_id=_PROFILE,
        reviewed_proposal_digest=proposal * 64,
    )


class _Operation:
    def __init__(self, operation_id: str, definition_id: str, subject_ref: str) -> None:
        self.operation_id = operation_id
        self.definition_id = definition_id
        self.subject_ref = subject_ref
        self.contract = _contract(definition_id)
        self.revision = 1
        self.lifecycle = OperationLifecycle.RUNNING
        self.condition: OperationTerminalCondition | None = None
        self.events: list[OperationPublicPhaseEventV1] = []
        self.review: GoogleConsentReviewProjection | None = None
        self.interaction_id = "1" * 64
        self.result: BaseModel | None = None
        self.refusal_ref: str | None = None
        self.cancellable = self.contract.cancellation is not OperationCancellation.UNSUPPORTED

    def await_review(self, review: GoogleConsentReviewProjection) -> None:
        self.review = review
        self.lifecycle = OperationLifecycle.WAITING_FOR_INTERACTION
        self.revision = review.revision

    def settle(self, result: BaseModel | None) -> None:
        self.lifecycle = OperationLifecycle.TERMINAL
        self.condition = OperationTerminalCondition.SUCCEEDED
        self.result = result
        self.review = None
        self.revision += 1

    def refuse(self, code: str, detail: BaseModel) -> None:
        self.settle(detail)
        self.condition = OperationTerminalCondition.REFUSED
        self.refusal_ref = code

    def _pending(self) -> OperationNoPendingInteractionV1 | OperationReviewAvailableInteractionV1:
        if self.review is None:
            return OperationNoPendingInteractionV1()
        schema = self.contract.review_projection_schema
        response = self.contract.interaction_response_schema
        assert schema is not None and response is not None
        expires = _NOW + timedelta(minutes=30)
        return OperationReviewAvailableInteractionV1(
            operation_id=self.operation_id,
            interaction_id=self.interaction_id,
            revision=self.revision,
            presentation_code=GOOGLE_CONSENT_PRESENTATION_CODE,
            response_schema=response,
            expires_at=expires,
            review_reference=OperationReviewProjectionReferenceV1(
                operation_id=self.operation_id,
                interaction_id=self.interaction_id,
                revision=self.revision,
                review_projection_schema=schema,
                definition_contract_digest=self.contract.definition_contract_digest,
                expires_at=expires,
            ),
        )

    def projection(self) -> OperationPublicProjectionV1:
        terminal = self.lifecycle is OperationLifecycle.TERMINAL
        return OperationPublicProjectionV1(
            operation_id=self.operation_id,
            definition_id=self.definition_id,
            subject_ref=self.subject_ref,
            revision=self.revision,
            anchor_cursor=len(self.events),
            definition_contract=self.contract,
            contract_set_digest=_REGISTRY.public_contract_set.contract_set_digest,
            lifecycle=self.lifecycle,
            terminal_condition=self.condition,
            effect=OperationEffect.NONE,
            phase_code=None,
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.contract.close_policy,
            cancellation=self.contract.cancellation,
            cancellable_now=self.cancellable and not terminal,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=self._pending(),
            result_ref="f" * 64 if self.condition is OperationTerminalCondition.SUCCEEDED and self.result else None,
            refusal_ref=self.refusal_ref,
            failure_error_code=None,
            diagnostic_ref=None,
        )


class _Runtime:
    """The hold's verified connection, answering each exchange from its operations."""

    frontend = OperationFrontendProjection.DESKTOP
    profile_id = _PROFILE
    session_id = _SESSION

    def __init__(self) -> None:
        self.operations: dict[str, _Operation] = {}
        self.submitted: list[OperationSubmit] = []
        self.financial: list[OperationFinancialInput] = []
        #: The definitions whose contract takes a transient financial operand; the runtime refuses every other one.
        self.financial_definitions: set[str] = set()
        self.managed: list[object] = []
        self.busy_holder: str | None = None
        #: The runtime's refusal of the next submission, as its client raises it.
        self.submit_refusal: FrontendRefusedError | None = None
        self.stale_cancellation = False

    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        assert (request.profile_id, request.session_id) == (_PROFILE, _SESSION)
        rid = request.request_id
        if isinstance(request, OperationSubmit):
            if self.busy_holder is not None:
                raise FrontendRefusedError(AccessDenialCode.SUBJECT_BUSY.value, holder_operation_id=self.busy_holder)
            if self.submit_refusal is not None:
                raise self.submit_refusal
            self.submitted.append(request)
            operation = _Operation(f"{len(self.submitted):064x}", request.definition_id, request.subject_ref)
            self.operations[operation.operation_id] = operation
            receipt = OperationSubmissionReceiptV1(operation_id=operation.operation_id, secret_requirement=None)
            return OperationSubmitted(request_id=rid, runtime_boot_id=_BOOT, connection_id=_CONNECTION, receipt=receipt)
        if isinstance(request, OperationFinancialInput):
            if request.definition_id not in self.financial_definitions:
                raise FrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)
            self.financial.append(request)
            operation = _Operation(f"f{len(self.financial):063x}", request.definition_id, request.subject_ref)
            self.operations[operation.operation_id] = operation
            receipt = OperationSubmissionReceiptV1(operation_id=operation.operation_id, secret_requirement=None)
            return OperationSubmitted(request_id=rid, runtime_boot_id=_BOOT, connection_id=_CONNECTION, receipt=receipt)
        if isinstance(request, OperationControl):
            return OperationAcknowledged(
                request_id=rid, runtime_boot_id=_BOOT, connection_id=_CONNECTION, operation_id=request.operation_id
            )
        if isinstance(request, OperationObserve):
            operation = self.operations.get(request.observation.operation_id)
            if operation is None:
                raise FrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)
            after = request.observation.after_cursor
            events = tuple(operation.events[after:])
            page = OperationPublicEventPageV1(
                operation_id=operation.operation_id,
                anchor_cursor=len(operation.events),
                requested_cursor=after,
                status=OperationReplayStatus.PAGE if events else OperationReplayStatus.CAUGHT_UP,
                events=events,
                next_cursor=len(operation.events),
                restart_cursor=None,
            )
            observation = OperationObservationSuccessV1(projection=operation.projection(), event_page=page)
            return OperationObserved(
                request_id=rid, runtime_boot_id=_BOOT, connection_id=_CONNECTION, observation=observation
            )
        if isinstance(request, OperationReview):
            operation = self.operations[request.review.reference.operation_id]
            assert operation.review is not None
            schema = operation.contract.review_projection_schema
            assert schema is not None
            document = OperationReviewProjectionSuccessV1[GoogleConsentReviewProjection](
                projection_schema=schema,
                definition_contract_digest=operation.contract.definition_contract_digest,
                projection=operation.review,
            ).model_dump(mode="json")
            return OperationProjected(
                request_id=rid,
                runtime_boot_id=_BOOT,
                connection_id=_CONNECTION,
                operation_id=operation.operation_id,
                projection_kind="review",
                document=document,
            )
        if isinstance(request, OperationManage):
            return self._manage(request)
        raise AssertionError(f"unexpected exchange {request!r}")

    def _manage(self, request: OperationManage) -> OperationReply:
        management = request.management
        self.managed.append(management)
        operation = self.operations[management.operation_id]
        if isinstance(management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1):
            document = _json(
                OperationResponseMutationSuccessV1(
                    operation_id=operation.operation_id,
                    interaction_id=management.interaction_id,
                    revision=management.revision,
                    response_action=management.response_action,
                )
            )
            operation.review = None
            operation.lifecycle = OperationLifecycle.RUNNING
        elif isinstance(management, OperationResponseControlRequestV1):
            document = _json(
                OperationResponseControlSuccessV1(
                    operation_id=operation.operation_id,
                    interaction_id=management.interaction_id,
                    revision=management.revision,
                    available=True,
                    permitted_intents=frozenset({"apply", "reject"}),
                )
            )
        elif isinstance(management, OperationCancellationRequestV1):
            if self.stale_cancellation:
                document = _json(
                    OperationCancellationRefusalV1(
                        code=OperationCancellationRefusalCode.STALE_OPERATION_REVISION,
                        requested_version=None,
                        diagnostic_ref=None,
                    )
                )
            else:
                document = _json(
                    OperationCancellationSuccessV1(
                        operation_id=operation.operation_id,
                        revision=operation.revision,
                        cancellation_acknowledged=False,
                    )
                )
        else:
            raise AssertionError(f"unexpected management {management!r}")
        return OperationManaged(
            request_id=request.request_id,
            runtime_boot_id=_BOOT,
            connection_id=_CONNECTION,
            operation_id=operation.operation_id,
            document=document,
        )

    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, timeout: float = 60, deadline: float | None = None
    ) -> dict[str, JsonValue]:
        operation = self.operations[result.operation_id]
        assert operation.result is not None and result.terminal_revision == operation.revision
        return {
            "outcome": "success",
            "result_projection_version": 1,
            "result_schema": result.result_schema.model_dump(mode="json"),
            "definition_contract_digest": operation.contract.definition_contract_digest,
            "projection": operation.result.model_dump(mode="json"),
        }


def _relay(runtime: _Runtime) -> OperationRelay:
    return OperationRelay(cast(FrontendClient, runtime))


def _submit(relay: OperationRelay, definition_id: str, payload: dict[str, object]) -> str:
    reply = relay.handle(
        "operation_submit",
        {"definition_id": definition_id, "subject_ref": _SUBJECT, "payload": payload},
    )
    assert reply["kind"] == "operation_submitted"
    return cast(str, reply["operation_id"])


def _reviewing(runtime: _Runtime, relay: OperationRelay) -> tuple[_Operation, dict[str, object]]:
    operation_id = _submit(relay, GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    operation = runtime.operations[operation_id]
    operation.await_review(_review(operation_id, 2, "e"))
    return operation, relay.handle("operation_review", {"operation_id": operation_id})


def _answer(review: dict[str, object], decision: str = "apply") -> dict[str, object]:
    return {
        "operation_id": review["operation_id"],
        "interaction_id": review["interaction_id"],
        "revision": review["revision"],
        "review_digest": review["review_digest"],
        "decision": decision,
    }


def test_a_submitted_operation_is_relayed_unchanged_and_watched_until_it_settles() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)
    assert not relay.watching()
    operation_id = _submit(relay, GOOGLE_STATUS_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    (submitted,) = runtime.submitted
    assert (submitted.definition_id, submitted.subject_ref) == (GOOGLE_STATUS_OPERATION_DEFINITION_ID, _SUBJECT)
    assert submitted.payload_json == f'{{"profile_id":"{_PROFILE}"}}'
    assert relay.watching()
    with pytest.raises(RelayRefusedError) as unsettled:
        relay.handle("operation_result", {"operation_id": operation_id})
    assert unsettled.value.code == "no_result"
    result = GoogleStatusProjection(profile_id=_PROFILE, session_present=False)
    runtime.operations[operation_id].settle(result)
    observed = relay.handle("operation_observe", {"operation_id": operation_id, "after_cursor": 0})
    assert observed["kind"] == "operation_observed"
    observation = OperationObservationSuccessV1.model_validate_json(json.dumps(observed["observation"]))
    assert observation.projection.lifecycle is OperationLifecycle.TERMINAL
    assert not relay.watching()
    read = relay.handle("operation_result", {"operation_id": operation_id})
    assert read["definition_id"] == GOOGLE_STATUS_OPERATION_DEFINITION_ID
    assert cast(dict[str, object], read["document"])["projection"] == result.model_dump(mode="json")


def _financial(definition_id: str, body: object) -> dict[str, object]:
    return {"definition_id": definition_id, "subject_ref": _SUBJECT, "input": body}


def test_financial_input_travels_once_as_the_runtimes_financial_input_and_the_relay_lets_go_of_it() -> None:
    runtime = _Runtime()
    runtime.financial_definitions.add(GOOGLE_STATUS_OPERATION_DEFINITION_ID)
    relay = _relay(runtime)
    request = _financial(GOOGLE_STATUS_OPERATION_DEFINITION_ID, {"input_version": 2, "amount": "1.234,56"})

    reply = relay.handle("operation_financial_submit", request)

    assert reply["kind"] == "operation_submitted"
    (sent,) = runtime.financial
    assert (sent.definition_id, sent.subject_ref) == (GOOGLE_STATUS_OPERATION_DEFINITION_ID, _SUBJECT)
    assert sent.payload_json == '{"input_version":2,"amount":"1.234,56"}'
    # Never as an ordinary submission, and the bridge's own copy is gone once it is handed over.
    assert runtime.submitted == []
    assert "input" not in request
    assert relay.watching()


def test_financial_input_for_a_definition_that_takes_none_is_refused_closed_and_starts_nothing() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)

    with pytest.raises(RelayRefusedError) as refused:
        relay.handle("operation_financial_submit", _financial(GOOGLE_STATUS_OPERATION_DEFINITION_ID, {"a": 1}))

    assert refused.value.code == AccessDenialCode.OPERATION_DENIED.value
    assert (runtime.financial, runtime.operations) == ([], {})
    assert not relay.watching()


def test_financial_input_that_is_not_an_object_or_too_large_never_reaches_the_runtime() -> None:
    runtime = _Runtime()
    runtime.financial_definitions.add(GOOGLE_STATUS_OPERATION_DEFINITION_ID)
    relay = _relay(runtime)

    with pytest.raises(TypeError):
        relay.handle("operation_financial_submit", _financial(GOOGLE_STATUS_OPERATION_DEFINITION_ID, []))
    with pytest.raises(ValueError, match="too large"):
        relay.handle(
            "operation_financial_submit",
            _financial(GOOGLE_STATUS_OPERATION_DEFINITION_ID, {"text": "x" * SUBMISSION_PAYLOAD_MAX_BYTES}),
        )
    assert runtime.financial == []


def test_a_busy_subject_names_the_operation_that_holds_it() -> None:
    runtime = _Runtime()
    runtime.busy_holder = "7" * 64
    with pytest.raises(RelayRefusedError) as refused:
        _submit(_relay(runtime), GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    assert (refused.value.code, refused.value.holder_operation_id) == (AccessDenialCode.SUBJECT_BUSY.value, "7" * 64)
    assert runtime.submitted == []


@pytest.mark.parametrize(
    ("refusal", "code"),
    [
        # Refused before the worker took it: nothing was done, and the session comes back by itself.
        (CustodyRecoveringError(remaining_seconds=90), AccessDenialCode.CUSTODY_RECOVERING.value),
        # The worker was lost while it served the submission: it may have been made, so the relay's unknown.
        (CustodyRecoveringEffectUnknownError(remaining_seconds=90, operation_id=None), "unavailable"),
    ],
)
def test_a_submission_refused_while_custody_recovers_is_relayed_as_its_effect_allows(
    refusal: FrontendRefusedError, code: str
) -> None:
    runtime = _Runtime()
    runtime.submit_refusal = refusal
    with pytest.raises(RelayRefusedError) as refused:
        _submit(_relay(runtime), GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    assert (refused.value.code, refused.value.holder_operation_id) == (code, None)


def test_an_answer_applies_exactly_the_review_it_read_and_a_changed_review_is_refused_unanswered() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)
    operation, review = _reviewing(runtime, relay)
    assert review["review_digest"] == content_hash_hex(cast(dict[str, JsonValue], review["document"]))
    operation.review = _review(operation.operation_id, operation.revision, "d")
    with pytest.raises(RelayRefusedError) as changed:
        relay.handle("operation_respond", _answer(review))
    assert changed.value.code == "review_changed"
    assert runtime.managed == []
    current = relay.handle("operation_review", {"operation_id": operation.operation_id})
    answered = relay.handle("operation_respond", _answer(current))
    assert answered == {"kind": "operation_responded", "operation_id": operation.operation_id, "decision": "apply"}
    control, applied = runtime.managed
    assert isinstance(control, OperationResponseControlRequestV1)
    assert isinstance(applied, OperationResponseApplyRequestV1)
    assert (applied.interaction_id, applied.revision, applied.actor_ref) == ("1" * 64, 2, f"session:{_SESSION}")


def test_a_rejection_answers_without_applying_and_another_interaction_is_not_pending() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)
    operation, review = _reviewing(runtime, relay)
    with pytest.raises(RelayRefusedError) as other:
        relay.handle("operation_respond", {**_answer(review), "interaction_id": "2" * 64})
    assert other.value.code == "not_pending"
    with pytest.raises(ValueError):
        relay.handle("operation_respond", _answer(review, "maybe"))
    relay.handle("operation_respond", _answer(review, "reject"))
    assert [type(item) for item in runtime.managed] == [
        OperationResponseControlRequestV1,
        OperationResponseRejectRequestV1,
    ]
    with pytest.raises(RelayRefusedError) as gone:
        relay.handle("operation_review", {"operation_id": operation.operation_id})
    assert gone.value.code == "not_pending"


def test_cancel_is_sent_at_the_observed_revision_and_a_stale_one_is_a_closed_refusal() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)
    operation_id = _submit(relay, GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    runtime.stale_cancellation = True
    with pytest.raises(RelayRefusedError) as stale:
        relay.handle("operation_cancel", {"operation_id": operation_id, "expected_revision": 1})
    assert stale.value.code == OperationCancellationRefusalCode.STALE_OPERATION_REVISION.value
    runtime.stale_cancellation = False
    requested = relay.handle("operation_cancel", {"operation_id": operation_id, "expected_revision": 1})
    assert requested == {"kind": "operation_cancel_requested", "operation_id": operation_id}
    cancelled = runtime.managed[-1]
    assert isinstance(cancelled, OperationCancellationRequestV1) and cancelled.expected_revision == 1


@pytest.mark.parametrize(
    ("action", "request_fields"),
    [
        ("operation_submit", {"definition_id": "", "subject_ref": "s", "payload": {}}),
        ("operation_submit", {"definition_id": "d", "subject_ref": "s", "payload": []}),
        ("operation_observe", {"operation_id": "a" * 64, "after_cursor": -1}),
        ("operation_cancel", {"operation_id": "a" * 64, "expected_revision": True}),
    ],
)
def test_a_malformed_request_is_invalid_and_reaches_no_runtime(action: str, request_fields: dict[str, object]) -> None:
    runtime = _Runtime()
    with pytest.raises((TypeError, ValueError)):
        _relay(runtime).handle(action, request_fields)
    assert runtime.submitted == [] and runtime.managed == []


def test_a_reply_carries_the_held_identity_with_its_fields_or_a_closed_refusal() -> None:
    request_id = uuid4()
    identity = {
        "request_id": str(request_id),
        "profile_id": str(_PROFILE),
        "session_id": str(_SESSION),
        "runtime_boot_id": str(_BOOT),
        "connection_id": str(_CONNECTION),
    }

    def reply(
        *, fields: dict[str, object] | None = None, refusal: RelayRefusedError | None = None
    ) -> dict[str, object]:
        return relay_reply(
            request_id=request_id,
            profile_id=_PROFILE,
            session_id=_SESSION,
            runtime_boot_id=_BOOT,
            connection_id=_CONNECTION,
            fields=fields,
            refusal=refusal,
        )

    fields: dict[str, object] = {"kind": "operation_submitted", "operation_id": "a" * 64}
    assert reply(fields=fields) == {**identity, **fields}
    refused = reply(refusal=RelayRefusedError("subject_busy", holder_operation_id="b" * 64))
    assert refused == {"kind": "operation_refused", **identity, "code": "subject_busy", "holder_operation_id": "b" * 64}
    with pytest.raises(ValueError):
        reply()
    assert RELAY_ACTION_KEYS["operation_respond"] == {
        "operation_id",
        "interaction_id",
        "revision",
        "review_digest",
        "decision",
    }


def _declined_google_sign_in() -> GoogleConfigurationOutcome:
    refusal = GoogleConfigurationRefusalProjection(
        profile_id=_PROFILE,
        provider_code="REFUSED_GOOGLE_SIGN_IN_REQUIRED",
        message_key="adapters.google.oauth_flow.errors.consent_declined",
        facts=GoogleConfigurationPresentationFacts(profile=_PROFILE),
        failure_category=DependencyFailureCategory.CANCELLED,
    )
    return GoogleConfigurationOutcome(profile_id=_PROFILE, outcome="refused", refusal=refusal)


def test_a_refusal_its_definition_details_is_read_like_a_result_and_any_other_refusal_has_none() -> None:
    runtime = _Runtime()
    relay = _relay(runtime)
    operation_id = _submit(relay, GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    detail = _declined_google_sign_in()
    runtime.operations[operation_id].refuse(GOOGLE_CONFIGURATION_REFUSAL_CODE, detail)

    read = relay.handle("operation_result", {"operation_id": operation_id})

    assert read["definition_id"] == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
    assert cast(dict[str, object], read["document"])["projection"] == detail.model_dump(mode="json")
    other = _submit(relay, GOOGLE_STATUS_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    runtime.operations[other].refuse(AccessDenialCode.OPERATION_DENIED.value, detail)
    with pytest.raises(RelayRefusedError) as undocumented:
        relay.handle("operation_result", {"operation_id": other})
    assert undocumented.value.code == "no_result"


def test_relay_uses_one_runtime_budget_across_slow_submit_and_start(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _Runtime()
    original = runtime.operation
    now = [1000.0]
    deadlines: list[float] = []
    monkeypatch.setattr(deadline_budget.time, "monotonic", lambda: now[0])

    def slow(request: OperationRequest, *, deadline: float) -> OperationReply:
        deadlines.append(deadline)
        now[0] += 9.0
        deadline_budget.remaining_budget(deadline)
        return original(request, deadline=deadline)

    monkeypatch.setattr(runtime, "operation", slow)
    operation = _submit(_relay(runtime), GOOGLE_STATUS_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)
    assert operation in runtime.operations
    assert deadlines == [1120.0, 1120.0]


def test_relay_does_not_restart_budget_after_slow_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _Runtime()
    original = runtime.operation
    now = [1000.0]
    monkeypatch.setattr(deadline_budget.time, "monotonic", lambda: now[0])

    def exhausted(request: OperationRequest, *, deadline: float) -> OperationReply:
        assert isinstance(request, OperationSubmit), "must not dispatch start after the action expires"
        result = original(request, deadline=deadline)
        now[0] += 121.0
        return result

    monkeypatch.setattr(runtime, "operation", exhausted)
    with pytest.raises(RelayRefusedError, match="unavailable"):
        _submit(_relay(runtime), GOOGLE_STATUS_OPERATION_DEFINITION_ID, _PROFILE_PAYLOAD)


def test_relay_logs_transport_cause_without_request_data(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    runtime = _Runtime()

    def refused(request: OperationRequest, *, deadline: float) -> OperationReply:
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED, check="private-profile-value")

    monkeypatch.setattr(runtime, "operation", refused)
    with caplog.at_level(logging.WARNING), pytest.raises(RelayRefusedError, match="unavailable"):
        _submit(_relay(runtime), GOOGLE_STATUS_OPERATION_DEFINITION_ID, {"private": "private-profile-value"})
    record = next(record for record in delivered_records(caplog) if record.message == "session_hold_operation_refused")
    assert record.__dict__["reason"] == "runtime_deadline_exceeded"
    assert record.__dict__["action"] == "operation_submit"
    assert "private-profile-value" not in str(record.__dict__)

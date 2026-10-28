"""Registered REVIEW uses one correlated transport and never replays a response."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, datetime
from threading import Thread, get_ident
from typing import Any, Literal, TypedDict, cast, override
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_SETUP_DEFINITION_ID,
    PROVISION_RESPONSE_SCHEMA,
    PROVISION_REVIEW_SCHEMA,
    ProvisionMutationRequest,
    ProvisionOutcome,
    ProvisionPlan,
    ProvisionPlanEntry,
    ProvisionPlanSpace,
    ProvisionResult,
    ProvisionReviewProjection,
    build_components_definitions,
    build_components_registration,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationDetachRequestV1,
    OperationDetachSuccessV1,
    OperationObservationRequestV1,
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
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalFieldIntent,
    CensalOperationOutcome,
    CensalOperationRequest,
    CensalOperationResult,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewProjectionV1,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.cli.errors import emit_error_and_exit
from cadrumo_client.commands import profile_binding, registered_operation_deadlines, registered_operation_errors
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import bind_profile_client, bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from cadrumo_client.commands.registered_operation_deadlines import RegisteredOperationSettlement
from cadrumo_client.contracts.contracts import (
    ChannelWake,
    ClientHello,
    Peer,
    RefusalCode,
    RefusalError,
    ServerHello,
)
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
    OperationReviewClaim,
    OperationReviewClaimed,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION = "c" * 64
_INTERACTION = "d" * 64
_NOW = datetime(2026, 9, 29, tzinfo=UTC)


class _ReplyIds(TypedDict):
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


def _contract() -> OperationPublicDefinitionContractV1:
    unused_port = cast(Any, None)
    definition = build_censal_operation_definition(
        certificate_secret_backend_factory=unused_port,
        browser_session_factory=unused_port,
        operator_scope_ports=unused_port,
        censal_fetch_port=unused_port,
        provider_preflight=lambda _profile_id, _operation: None,
    )
    return build_censal_operation_registration(definition).contract


def _payload() -> CensalOperationRequest:
    return CensalOperationRequest(
        baseline=CensalProfileBaseline(profile_id=str(_PROFILE), record_revision=1, content_digest="a" * 64),
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )


class ReviewWire:
    """Explicit operation transport port; no executor or native admission substitute."""

    profile_id = _PROFILE
    session_id = _SESSION
    frontend = OperationFrontendProjection.CLI

    def __init__(self, *, fault: str | None = None, already_terminal: bool = False) -> None:
        self.public_contract = _contract()
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.review = CensalReviewProjectionV1(projection_version=1, reviewed_proposal_digest="f" * 64, fields=())
        self.requests: list[OperationRequest] = []
        self.deadlines: list[float] = []
        self.action: Literal["apply", "reject"] | None = "apply" if already_terminal else None
        self.fault = fault
        self.result_reads = 0
        self.repeated_wait = False
        self.observers: list[Callable[[], None]] = []

    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        self.observers.append(receive)
        return lambda: self.observers.remove(receive)

    def _cue(self) -> None:
        # The runtime cues observers whenever the operation commits a change.
        for receive in tuple(self.observers):
            receive()

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == CENSAL_OPERATION_DEFINITION_ID
        self.deadlines.append(deadline)
        return self.public_contract

    def read_result_document(
        self, request: OperationResultProjectionRequestV1, *, timeout: float, deadline: float
    ) -> dict[str, Any]:
        self.deadlines.append(deadline)
        assert timeout > 0
        assert request.operation_id == _OPERATION and request.terminal_revision == 5
        assert request.result_schema == self.public_contract.result_schema
        assert request.definition_contract_digest == self.public_contract.definition_contract_digest
        self.result_reads += 1
        schema = self.public_contract.result_schema
        assert schema is not None
        return json.loads(
            OperationResultProjectionSuccessV1[CensalOperationResult](
                result_schema=schema,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=CensalOperationResult(
                    outcome=CensalOperationOutcome.APPLIED
                    if self.action == "apply"
                    else CensalOperationOutcome.REJECTED,
                    reviewed_proposal_digest="f" * 64,
                ),
            ).model_dump_json()
        )

    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        assert request.profile_id == _PROFILE and request.session_id == _SESSION
        self.requests.append(request)
        self.deadlines.append(deadline)
        reply_id = request.request_id
        if isinstance(request, OperationSubmit):
            return OperationSubmitted(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None),
            )
        if isinstance(request, OperationControl):
            assert request.action == "operation_start"
            return OperationAcknowledged(
                request_id=reply_id, runtime_boot_id=_PROFILE, connection_id=_SESSION, operation_id=_OPERATION
            )
        if isinstance(request, OperationObserve):
            terminal = self.action is not None
            if terminal and self.fault == "repeat-wait" and not self.repeated_wait:
                self.repeated_wait = True
                terminal = False
                # The held-back settlement commits after this observation.
                self._cue()
            return OperationObserved(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                observation=self._observation(terminal=terminal),
            )
        if isinstance(request, OperationReview):
            assert request.review.reference.revision == 4
            success = OperationReviewProjectionSuccessV1[CensalReviewProjectionV1](
                projection_schema=(
                    self.public_contract.request_schema
                    if self.fault == "review-schema"
                    else CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
                ),
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=self.review,
            )
            if self.fault == "reply-id":
                reply_id = uuid4()
            if self.fault == "session":
                self.session_id = uuid4()
            return OperationProjected(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                operation_id=_OPERATION,
                projection_kind="review",
                document=json.loads(success.model_dump_json()),
            )
        assert isinstance(request, OperationManage)
        management = request.management
        if isinstance(management, OperationDetachRequestV1):
            assert management.expected_revision == 4
            document = OperationDetachSuccessV1(operation_id=_OPERATION, revision=4)
        elif isinstance(management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1):
            assert management.actor_ref == f"session:{_SESSION}"
            assert management.interaction_id == _INTERACTION and management.revision == 4
            self.action = management.response_action
            self._cue()
            if self.fault == "lost-ack":
                raise RefusalError(RefusalCode.TIMEOUT)
            if self.fault == "mutation-id":
                reply_id = uuid4()
            document = OperationResponseMutationSuccessV1(
                operation_id=_OPERATION, interaction_id=_INTERACTION, revision=4, response_action=self.action
            )
        else:
            assert isinstance(management, OperationResponseControlRequestV1)
            assert management.actor_ref == f"session:{_SESSION}"
            document = OperationResponseControlSuccessV1(
                operation_id=_OPERATION,
                interaction_id=_INTERACTION,
                revision=3 if self.fault == "control-revision" else 4,
                available=self.fault != "no-authority",
                permitted_intents=frozenset() if self.fault == "no-authority" else frozenset({"apply", "reject"}),
            )
        return OperationManaged(
            request_id=reply_id,
            runtime_boot_id=_PROFILE,
            connection_id=_SESSION,
            operation_id=_OPERATION,
            document=json.loads(document.model_dump_json()),
        )

    def _observation(self, *, terminal: bool) -> OperationObservationSuccessV1:
        pending = OperationReviewAvailableInteractionV1(
            operation_id=_OPERATION,
            interaction_id=_INTERACTION,
            revision=4,
            presentation_code="censo.interaction-wait",
            response_schema=CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity,
            expires_at=None,
            review_reference=OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION,
                interaction_id=_INTERACTION,
                revision=4,
                review_projection_schema=CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                expires_at=None,
            ),
        )
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION,
            definition_id=CENSAL_OPERATION_DEFINITION_ID,
            subject_ref=str(_PROFILE),
            revision=5 if terminal else 4,
            anchor_cursor=1,
            definition_contract=self.public_contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.WAITING_FOR_INTERACTION,
            terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
            effect=OperationEffect.UPDATED if terminal and self.action == "apply" else OperationEffect.NONE,
            phase_code="censo.settlement" if terminal else "censo.interaction-wait",
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.public_contract.close_policy,
            cancellation=self.public_contract.cancellation,
            cancellable_now=not terminal,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1() if terminal else pending,
            result_ref="e" * 64 if terminal else None,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        page = OperationPublicEventPageV1(
            operation_id=_OPERATION,
            anchor_cursor=1,
            requested_cursor=0,
            status=OperationReplayStatus.PAGE,
            events=(
                OperationPublicPhaseEventV1(
                    revision=4,
                    sequence=1,
                    timestamp=_NOW,
                    code="censo.interaction-wait",
                    phase_code="censo.interaction-wait",
                ),
            ),
            next_cursor=1,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=page)


def _run(
    wire: ReviewWire, handler: RegisteredOperationReviewHandler[CensalReviewProjectionV1] | None
) -> (
    RegisteredOperationCompletion[CensalOperationResult] | RegisteredOperationReviewCompletion[CensalReviewProjectionV1]
):
    return run_registered_operation(
        cast(FrontendClient, wire),
        _payload(),
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=str(_PROFILE),
        result_type=CensalOperationResult,
        request_version=1,
        result_version=1,
        timeout=5,
        review=handler,
    )


def _handler(decision: Literal["apply", "reject"] | None) -> RegisteredOperationReviewHandler[CensalReviewProjectionV1]:
    return RegisteredOperationReviewHandler(
        review_type=CensalReviewProjectionV1,
        review_schema=CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity,
        response_schema=CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity,
        decide=lambda _: decision,
    )


@pytest.mark.parametrize("decision", ["apply", "reject", None])
def test_registered_review_responds_or_detaches_without_fabricating_terminal_success(
    decision: Literal["apply", "reject"] | None,
) -> None:
    wire = ReviewWire(fault="repeat-wait")
    completion = _run(wire, _handler(decision))
    assert completion.operation_id == _OPERATION
    assert len(set(wire.deadlines)) == 1
    manages = [item.management for item in wire.requests if isinstance(item, OperationManage)]
    if decision is None:
        assert isinstance(completion, RegisteredOperationReviewCompletion)
        assert completion.review == wire.review and completion.effect is OperationEffect.NONE
        assert len(manages) == 1 and isinstance(manages[0], OperationDetachRequestV1)
        assert wire.result_reads == 0
    else:
        assert isinstance(completion, RegisteredOperationCompletion)
        assert completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert completion.effect is (OperationEffect.UPDATED if decision == "apply" else OperationEffect.NONE)
        assert wire.result_reads == 1
        assert len(manages) == 2 and type(manages[0]) is OperationResponseControlRequestV1
        assert isinstance(manages[1], OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1)
        assert manages[1].response_action == decision


@pytest.mark.parametrize("refuse", [False, True])
def test_review_reference_validation_precedes_decision_and_response_control(refuse: bool) -> None:
    wire = ReviewWire()
    calls: list[str] = []

    def validate(review: CensalReviewProjectionV1, reference: OperationReviewProjectionReferenceV1) -> None:
        assert review == wire.review
        assert reference.operation_id == _OPERATION and reference.revision == 4
        calls.append("validate")
        if refuse:
            raise RefusalError(RefusalCode.INVALID_FRAME)

    def decide(_: CensalReviewProjectionV1) -> Literal["apply"]:
        calls.append("decide")
        return "apply"

    handler = replace(_handler("apply"), decide=decide, validate_reference=validate)
    if refuse:
        with pytest.raises(CliRefusedBoundaryError):
            _run(wire, handler)
        assert calls == ["validate"]
        assert wire.action is None and wire.result_reads == 0
        assert not any(isinstance(item, OperationManage) for item in wire.requests)
    else:
        completion = _run(wire, handler)
        assert isinstance(completion, RegisteredOperationCompletion)
        assert calls == ["validate", "decide"]
        assert wire.action == "apply" and wire.result_reads == 1


def test_optional_review_hooks_present_then_decide_then_claim_before_response_control() -> None:
    wire = ReviewWire()
    calls: list[str] = []

    def present(document: Any) -> None:
        assert document["outcome"] == "success"
        calls.append("present")

    def decide(_: CensalReviewProjectionV1) -> Literal["apply"]:
        calls.append("decide")
        return "apply"

    def claim(pending: Any, document: Any, profile: UUID, session: UUID, exchange: Any) -> Any:
        assert document["outcome"] == "success"
        assert profile == _PROFILE and session == _SESSION
        assert not any(isinstance(item, OperationManage) for item in wire.requests)
        calls.append("claim")
        return pending

    handler = replace(_handler("apply"), present_document=present, decide=decide, claim=claim)
    completion = _run(wire, handler)
    assert isinstance(completion, RegisteredOperationCompletion)
    assert calls == ["present", "decide", "claim"]


class ProvisionReviewWire(ReviewWire):
    """Typed setup transport exercising the actual CLI runner and claim callback."""

    def __init__(self) -> None:
        super().__init__()
        definition = next(
            item
            for item in build_components_definitions(cast(Any, None))
            if item.definition_id == COMPONENTS_SETUP_DEFINITION_ID
        )
        self.public_contract = build_components_registration(definition).contract
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.provision_review = ProvisionReviewProjection(
            reviewed_proposal_digest="f" * 64,
            plan_digest="e" * 64,
            plan=ProvisionPlan(
                contract_version=3,
                entries=(
                    ProvisionPlanEntry(
                        item_id="browser",
                        download_bytes=100,
                        source_hosts=("example.com",),
                        destination="playwright-browsers",
                        installs_outside_program=False,
                        target_version=None,
                        parts=(),
                    ),
                ),
                known_download_bytes=100,
                has_unknown_size=False,
                installs_outside_program=False,
                space=ProvisionPlanSpace(free_bytes=1000, required_bytes=100, sufficient=True),
            ),
        )
        self.displayed_document: dict[str, Any] | None = None
        self.claimed = False

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == COMPONENTS_SETUP_DEFINITION_ID
        return self.public_contract

    @override
    def read_result_document(
        self, request: OperationResultProjectionRequestV1, *, timeout: float, deadline: float
    ) -> dict[str, Any]:
        assert request.terminal_revision == 6
        schema = self.public_contract.result_schema
        assert schema is not None
        outcome = ProvisionOutcome.COMPLETED if self.action == "apply" else ProvisionOutcome.REJECTED
        return json.loads(
            OperationResultProjectionSuccessV1[ProvisionResult](
                result_schema=schema,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=ProvisionResult(outcome=outcome, plan_digest=self.provision_review.plan_digest),
            ).model_dump_json()
        )

    def _provision_observation(self) -> OperationObservationSuccessV1:
        terminal = self.action is not None
        reference = OperationReviewProjectionReferenceV1(
            operation_id=_OPERATION,
            interaction_id=_INTERACTION,
            revision=4,
            review_projection_schema=PROVISION_REVIEW_SCHEMA.identity,
            definition_contract_digest=self.public_contract.definition_contract_digest,
            expires_at=None,
        )
        pending = OperationReviewAvailableInteractionV1(
            operation_id=_OPERATION,
            interaction_id=_INTERACTION,
            revision=4,
            presentation_code="config.provision.review",
            response_schema=PROVISION_RESPONSE_SCHEMA.identity,
            expires_at=None,
            review_reference=reference,
        )
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION,
            definition_id=COMPONENTS_SETUP_DEFINITION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            revision=6 if terminal else 4,
            anchor_cursor=0,
            definition_contract=self.public_contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.WAITING_FOR_INTERACTION,
            terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
            effect=OperationEffect.UPDATED if terminal and self.action == "apply" else OperationEffect.NONE,
            phase_code="config.provision.setup",
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.public_contract.close_policy,
            cancellation=self.public_contract.cancellation,
            cancellable_now=not terminal,
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
        page = OperationPublicEventPageV1(
            operation_id=_OPERATION,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=page)

    @override
    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        from cadrumo.core.hashing import content_hash_hex

        self.requests.append(request)
        common: _ReplyIds = {"request_id": request.request_id, "runtime_boot_id": _PROFILE, "connection_id": _SESSION}
        if isinstance(request, OperationSubmit):
            assert request.definition_id == COMPONENTS_SETUP_DEFINITION_ID
            assert ProvisionMutationRequest.model_validate_json(request.payload_json) == ProvisionMutationRequest()
            return OperationSubmitted(
                **common, receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None)
            )
        if isinstance(request, OperationControl):
            return OperationAcknowledged(**common, operation_id=_OPERATION)
        if isinstance(request, OperationObserve):
            return OperationObserved(**common, observation=self._provision_observation())
        if isinstance(request, OperationReview):
            document = OperationReviewProjectionSuccessV1[ProvisionReviewProjection](
                projection_schema=PROVISION_REVIEW_SCHEMA.identity,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=self.provision_review,
            )
            self.displayed_document = json.loads(document.model_dump_json())
            return OperationProjected(
                **common, operation_id=_OPERATION, projection_kind="review", document=self.displayed_document
            )
        if isinstance(request, OperationReviewClaim):
            assert self.displayed_document is not None
            assert request.reviewed_document_digest == content_hash_hex(self.displayed_document)
            self.claimed = True
            return OperationReviewClaimed(
                **common,
                reference=request.reference.model_copy(update={"revision": 5}),
                reviewed_document_digest=request.reviewed_document_digest,
                allowed_intents=frozenset({"apply", "reject"}),
            )
        assert isinstance(request, OperationManage) and self.claimed
        management = request.management
        if isinstance(management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1):
            assert management.revision == 5 and management.interaction_id == _INTERACTION
            self.action = management.response_action
            document = OperationResponseMutationSuccessV1(
                operation_id=_OPERATION, interaction_id=_INTERACTION, revision=5, response_action=self.action
            )
            self._cue()
        else:
            assert isinstance(management, OperationResponseControlRequestV1)
            assert management.revision == 5 and management.interaction_id == _INTERACTION
            document = OperationResponseControlSuccessV1(
                operation_id=_OPERATION,
                interaction_id=_INTERACTION,
                revision=5,
                available=True,
                permitted_intents=frozenset({"apply", "reject"}),
            )
        return OperationManaged(**common, operation_id=_OPERATION, document=json.loads(document.model_dump_json()))


@pytest.mark.parametrize("yes", [True, False])
def test_provision_cli_uses_actual_registered_runner_and_claims_before_response(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    yes: bool,
) -> None:
    from ..config import provision_cli

    wire = ProvisionReviewWire()
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: wire)
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    ctx = typer.Context(typer.main.get_command(app), obj={"format": "json"})
    if yes:
        provision_cli.provision_setup(ctx, yes=True)
    else:
        with pytest.raises(typer.Exit):
            provision_cli.provision_setup(ctx, yes=False)
    output = capsys.readouterr()
    assert wire.displayed_document is not None and json.loads(output.err.splitlines()[0]) == wire.displayed_document
    assert wire.action == ("apply" if yes else "reject")
    assert [type(item) for item in wire.requests] == [
        OperationSubmit,
        OperationControl,
        OperationObserve,
        OperationReview,
        OperationReviewClaim,
        OperationManage,
        OperationManage,
        OperationObserve,
    ]


@pytest.mark.parametrize("yes", [True, False])
def test_existing_setup_review_claims_the_observed_document_before_answering(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], yes: bool
) -> None:
    from ..config import provision_cli

    wire = ProvisionReviewWire()
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: wire)
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    ctx = typer.Context(typer.main.get_command(app), obj={"format": "json"})
    provision_cli.provision_review(ctx, _OPERATION, yes=yes, reject=not yes)
    output = capsys.readouterr()
    assert wire.displayed_document is not None and json.loads(output.err.splitlines()[0]) == wire.displayed_document
    assert json.loads(output.out)["result"] == {"operation_id": _OPERATION, "decision": "apply" if yes else "reject"}
    assert [type(item) for item in wire.requests] == [
        OperationObserve,
        OperationReview,
        OperationReviewClaim,
        OperationManage,
        OperationManage,
    ]


@pytest.mark.parametrize("existing", [False, True])
def test_provision_review_text_shows_plan_without_raw_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], existing: bool
) -> None:
    from ..config import provision_cli

    wire = ProvisionReviewWire()
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: wire)
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    ctx = typer.Context(typer.main.get_command(app), obj={"format": "text"})
    if existing:
        provision_cli.provision_review(ctx, _OPERATION, yes=True)
    else:
        provision_cli.provision_setup(ctx, yes=True)
    stderr = capsys.readouterr().err
    assert "example.com" in stderr
    assert "definition_contract_digest" not in stderr
    assert "review_projection_version" not in stderr
    assert wire.claimed and wire.action == "apply"


@pytest.mark.parametrize("fault", ["review-schema", "reply-id", "session", "control-revision", "no-authority"])
def test_registered_review_rejects_stale_or_unadmitted_control_before_mutation(fault: str) -> None:
    wire = ReviewWire(fault=fault)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _run(wire, _handler("apply"))
    assert caught.value.context is not None
    assert caught.value.context["operation_id"] == _OPERATION
    assert wire.action is None and wire.result_reads == 0
    assert not any(
        isinstance(item, OperationManage)
        and isinstance(item.management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1)
        for item in wire.requests
    )


@pytest.mark.parametrize("fault", ["lost-ack", "mutation-id"])
def test_ambiguous_registered_response_keeps_unknown_effect_and_never_replays(fault: str) -> None:
    wire = ReviewWire(fault=fault)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _run(wire, _handler("apply"))
    assert caught.value.context is not None
    assert caught.value.context["effect"] == OperationEffect.UNKNOWN.value
    assert wire.action == "apply" and wire.result_reads == 0
    assert (
        sum(
            isinstance(item, OperationManage) and isinstance(item.management, OperationResponseApplyRequestV1)
            for item in wire.requests
        )
        == 1
    )


def test_unhandled_waiting_review_refuses_and_unchanged_terminal_caller_still_reads_result() -> None:
    waiting = ReviewWire()
    with pytest.raises(CliRefusedBoundaryError):
        _run(waiting, None)
    assert not any(isinstance(item, OperationReview | OperationManage) for item in waiting.requests)
    terminal = ReviewWire(already_terminal=True)
    completion = _run(terminal, None)
    assert isinstance(completion, RegisteredOperationCompletion) and terminal.result_reads == 1


def test_review_callback_cancellation_is_exact_and_expired_deadline_prevents_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = asyncio.CancelledError()
    wire = ReviewWire()

    def cancel(_: CensalReviewProjectionV1) -> Literal["apply", "reject"] | None:
        raise cancellation

    handler = _handler("apply")
    cancelled = RegisteredOperationReviewHandler(
        review_type=handler.review_type,
        review_schema=handler.review_schema,
        response_schema=handler.response_schema,
        decide=cancel,
    )
    with pytest.raises(asyncio.CancelledError) as caught:
        _run(wire, cancelled)
    assert caught.value is cancellation
    assert not any(isinstance(item, OperationManage) for item in wire.requests)

    clock = [100.0]
    monkeypatch.setattr(registered_operation_deadlines.time, "monotonic", lambda: clock[0])

    def expire(_: CensalReviewProjectionV1) -> Literal["apply", "reject"] | None:
        clock[0] += 6
        return "apply"

    expired = RegisteredOperationReviewHandler(
        review_type=handler.review_type,
        review_schema=handler.review_schema,
        response_schema=handler.response_schema,
        decide=expire,
    )
    timed = ReviewWire()
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _run(timed, expired)
    assert refused.value.context is not None
    assert refused.value.context["reason"] == RefusalCode.TIMEOUT.value
    assert not any(isinstance(item, OperationManage) for item in timed.requests)


_RELEASE_CONTEXT: ContextVar[str | None] = ContextVar("cli_release_test_context", default=None)


class ReleaseFaultChannel:
    """Explicit byte port exercising real framing and native-release ownership."""

    def __init__(self, *, close_failures: int) -> None:
        self.peer = Peer(os_owner_id="synthetic-owner", process_id=1)
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.close_failures = close_failures
        self.failure = RefusalError(RefusalCode.TIMEOUT)
        self.close_contexts: list[str | None] = []
        self.close_threads: list[int] = []

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > time.monotonic()
        if len(self.inbound) < count:
            raise self.failure
        payload = bytes(self.inbound[:count])
        del self.inbound[:count]
        return payload

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        while not self.read_ready():
            if any(wake.is_set() for wake in wakes):
                return False
            time.sleep(0.01)
        return True

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))

    def close(self) -> None:
        self.close_calls += 1
        self.close_contexts.append(_RELEASE_CONTEXT.get())
        self.close_threads.append(get_ident())
        if self.close_calls <= self.close_failures:
            raise OSError("synthetic native release failure")


class FramingFaultClient(FrontendClient):
    """Script submission only; observation uses the real verified byte connection."""

    def __init__(self, channel: ReleaseFaultChannel) -> None:
        deadline = time.monotonic() + 5
        hello = ServerHello(product_version="cleanup-test", storage_identity="a" * 64, boot_id=_PROFILE)
        write_document(channel, hello, deadline=deadline)
        channel.inbound.extend(b"".join(channel.writes))
        channel.writes.clear()
        self.native_connection = VerifiedConnection(
            channel,
            expected=ClientHello(product_version=hello.product_version, storage_identity=hello.storage_identity),
            deadline=deadline,
        )
        super().__init__(self.native_connection, profile_id=_PROFILE, frontend=OperationFrontendProjection.CLI)
        self.script = ReviewWire()

    @property
    @override
    def session_id(self) -> UUID:
        return _SESSION

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        return self.script.contract(definition_id, deadline=deadline)

    @override
    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        if isinstance(request, OperationObserve):
            reply = self.native_connection.operation(request, deadline=deadline)
            assert isinstance(reply, OperationObserved)
            return reply
        return self.script.operation(request, deadline=deadline)


def _retained_cleanup(error: BaseException) -> AsyncResourceCleanupError:
    cleanup = error.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    return cleanup


def test_mapped_registered_exchange_and_invocation_keep_one_actual_native_retry_owner() -> None:
    """A failed framed read and scope release retain ID/effect and one retry path."""
    channel = ReleaseFaultChannel(close_failures=3)
    client = FramingFaultClient(channel)
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    # A command is not needed: this is the exact parsed-context resource owner.
    with pytest.raises(CliRefusedBoundaryError) as caught, context:
        bind_profile_client(context, client, profile_id=_PROFILE)
        assert bound_profile_client(context) is client
        _run(cast(ReviewWire, client), None)
    mapped = caught.value
    assert mapped.context is not None
    assert mapped.context["operation_id"] == _OPERATION
    assert mapped.context["effect"] == OperationEffect.UNKNOWN.value
    assert mapped.context["reason"] == RefusalCode.TIMEOUT.value
    assert mapped.__cause__ is None
    assert channel.close_calls == 2
    retained = _retained_cleanup(mapped)
    original = _retained_cleanup(channel.failure)
    assert len(retained.resources) == 1 and retained.resources == original.resources
    assert mapped.__dict__["_transport_cleanup"] is channel.failure.__dict__["_transport_cleanup"]
    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        asyncio.run(retained.retry_cleanup())
    assert channel.close_calls == 3
    asyncio.run(retry_failed.value.retry_cleanup())
    assert channel.close_calls == 4
    asyncio.run(retained.retry_cleanup())
    client.close()
    assert channel.close_calls == 4


@pytest.mark.parametrize("cancel", [False, True])
def test_bound_cli_release_preserves_exact_body_and_cancel_with_failed_native_owner(cancel: bool) -> None:
    channel = ReleaseFaultChannel(close_failures=1)
    client = FramingFaultClient(channel)
    primary = asyncio.CancelledError() if cancel else RefusalError(RefusalCode.INVALID_FRAME)
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    with pytest.raises(type(primary)) as caught, context:
        bind_profile_client(context, client, profile_id=_PROFILE)
        raise primary
    assert caught.value is primary and channel.close_calls == 1
    field = "cleanup_error" if cancel else "async_cleanup_error"
    cleanup = primary.__dict__.get(field)
    assert isinstance(cleanup, AsyncResourceCleanupError) and len(cleanup.resources) == 1
    asyncio.run(cleanup.retry_cleanup())
    assert channel.close_calls == 2


@pytest.mark.parametrize("close_failures", [0, 1])
def test_rendered_cli_exit_exposes_unsettled_typed_cause_but_keeps_successful_exit(
    close_failures: int, capsys: pytest.CaptureFixture[str]
) -> None:
    channel = ReleaseFaultChannel(close_failures=close_failures)
    client = FramingFaultClient(channel)
    primary = registered_operation_errors.submitted_operation_error(
        _OPERATION, RefusalCode.INVALID_FRAME.value, terminal_condition=None, effect=OperationEffect.UNKNOWN
    )
    rendered: typer.Exit | None = None
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    with pytest.raises(CliRefusedBoundaryError if close_failures else typer.Exit) as caught, context:
        bind_profile_client(context, client, profile_id=_PROFILE)
        try:
            emit_error_and_exit(primary)
        except typer.Exit as exit_request:
            rendered = exit_request
            raise
    assert caught.value is (primary if close_failures else rendered)
    assert channel.close_calls == 1
    assert "synthetic native release failure" not in capsys.readouterr().err
    if close_failures:
        assert primary.context is not None and primary.context["operation_id"] == _OPERATION
        asyncio.run(_retained_cleanup(primary).retry_cleanup())
        assert channel.close_calls == 2


def test_successful_bound_release_retires_historical_cleanup_without_native_replay() -> None:
    channel = ReleaseFaultChannel(close_failures=1)
    client = FramingFaultClient(channel)
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    with pytest.raises(RefusalError) as caught, context:
        bind_profile_client(context, client, profile_id=_PROFILE)
        client.native_connection.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=_PROFILE,
                session_id=_SESSION,
                observation=OperationObservationRequestV1(operation_id=_OPERATION, after_cursor=0, page_limit=1),
            ),
            deadline=time.monotonic() + 5,
        )
    assert caught.value is channel.failure
    assert channel.close_calls == 2
    cleanup = _retained_cleanup(caught.value)
    assert cleanup.resources == ()
    asyncio.run(cleanup.retry_cleanup())
    assert channel.close_calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_bound_cli_release_on_active_sdk_loop_keeps_context_and_exact_primary(cancel: bool) -> None:
    """A synchronous Click exit retains real transport cleanup on an active loop."""
    channel = ReleaseFaultChannel(close_failures=1)
    client = FramingFaultClient(channel)
    primary = asyncio.CancelledError() if cancel else RefusalError(RefusalCode.INVALID_FRAME)
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    token = _RELEASE_CONTEXT.set("active-sdk-scope")
    try:
        with pytest.raises(type(primary)) as caught, context:
            bind_profile_client(context, client, profile_id=_PROFILE)
            raise primary
        assert caught.value is primary
        assert channel.close_calls == 1 and channel.close_contexts == ["active-sdk-scope"]
        assert channel.close_threads[0] != get_ident()
        field = "cleanup_error" if cancel else "async_cleanup_error"
        cleanup = primary.__dict__.get(field)
        assert isinstance(cleanup, AsyncResourceCleanupError) and len(cleanup.resources) == 1
        await cleanup.retry_cleanup()
        assert channel.close_calls == 2
        assert channel.close_contexts == ["active-sdk-scope", "active-sdk-scope"]
    finally:
        _RELEASE_CONTEXT.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["normal", "typed", "cancel", "rendered", "exchange", "released_exchange"])
async def test_bound_cli_release_bridge_start_failure_retains_actual_owner_and_primary(
    body: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bridge setup failure owns the native channel before any release can run."""
    channel = ReleaseFaultChannel(close_failures=1 if body == "exchange" else 0)
    client = FramingFaultClient(channel)
    context = typer.Context(typer.main.TyperCommand(name="bound"))
    primary = (
        asyncio.CancelledError()
        if body == "cancel"
        else registered_operation_errors.submitted_operation_error(
            _OPERATION, RefusalCode.INVALID_FRAME.value, terminal_condition=None, effect=OperationEffect.UNKNOWN
        )
    )
    setup_failure = RuntimeError("synthetic thread startup failure")
    starts = 0

    class FailStartThread(Thread):
        @override
        def start(self) -> None:
            nonlocal starts
            starts += 1
            raise setup_failure

    with monkeypatch.context() as controls:
        controls.setattr(profile_binding, "Thread", FailStartThread)
        expected = (
            AsyncResourceCleanupError
            if body == "normal"
            else RefusalError
            if body in {"exchange", "released_exchange"}
            else type(primary)
        )
        with pytest.raises(expected) as caught, context:
            bind_profile_client(context, client, profile_id=_PROFILE)
            if body == "rendered":
                raise typer.Exit(code=1) from primary
            if body in {"exchange", "released_exchange"}:
                client.native_connection.operation(
                    OperationObserve(
                        request_id=uuid4(),
                        profile_id=_PROFILE,
                        session_id=_SESSION,
                        observation=OperationObservationRequestV1(
                            operation_id=_OPERATION, after_cursor=0, page_limit=1
                        ),
                    ),
                    deadline=time.monotonic() + 5,
                )
            elif body != "normal":
                raise primary
    if body == "released_exchange":
        assert caught.value is channel.failure and channel.close_calls == 1
        assert starts == 0
        assert not any(
            isinstance(caught.value.__dict__.get(field), AsyncResourceCleanupError)
            for field in ("async_cleanup_error", "cleanup_error")
        )
        assert client.cleanup_owner(primary_error=caught.value).released
        client.close()
        assert channel.close_calls == 1
        return
    assert starts == 1
    if body == "normal":
        cleanup = caught.value
        assert isinstance(cleanup, AsyncResourceCleanupError)
    else:
        assert caught.value is (channel.failure if body == "exchange" else primary)
        field = "cleanup_error" if body == "cancel" else "async_cleanup_error"
        cleanup = caught.value.__dict__.get(field)
        assert isinstance(cleanup, AsyncResourceCleanupError)
    assert caught.value.__cause__ is None
    assert channel.close_calls == (1 if body == "exchange" else 0)
    assert len(cleanup.resources) == 1
    await cleanup.retry_cleanup()
    assert channel.close_calls == (2 if body == "exchange" else 1)
    await cleanup.retry_cleanup()
    assert channel.close_calls == (2 if body == "exchange" else 1)


def _setup_review_from_public_command(
    monkeypatch: pytest.MonkeyPatch,
) -> RegisteredOperationReviewHandler[ProvisionReviewProjection]:
    """Capture the handler configured by the public setup command before transport starts."""
    from ..config import provision_cli

    class CapturedReviewError(Exception):
        pass

    handlers: list[RegisteredOperationReviewHandler[ProvisionReviewProjection]] = []

    def capture(*args: object, review: RegisteredOperationReviewHandler[ProvisionReviewProjection], **kwargs: object):
        handlers.append(review)
        raise CapturedReviewError

    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    ctx = typer.Context(typer.main.get_command(app), obj={"format": "json"})
    with monkeypatch.context() as scoped:
        scoped.setattr(provision_cli, "bound_profile_client", lambda _ctx: None)
        scoped.setattr(provision_cli, "run_registered_operation", capture)
        with pytest.raises(CapturedReviewError):
            provision_cli.provision_setup(ctx, yes=True)
    assert len(handlers) == 1
    return handlers[0]


@pytest.mark.parametrize("unbounded", [False, True])
def test_setup_wait_preserves_owned_review_and_download_beyond_short_budget(
    monkeypatch: pytest.MonkeyPatch, unbounded: bool
) -> None:
    """Human time and download cues spend no total budget only when explicitly requested."""
    import math

    from cadrumo_client.transport import operation_changes

    clock = [1000.0]
    waits: list[float | None] = []
    call_windows: list[float] = []
    monkeypatch.setattr(registered_operation_deadlines.time, "monotonic", lambda: clock[0])

    class SlowSetupWire(ProvisionReviewWire):
        downloads = 0

        @override
        def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
            call_windows.append(deadline - clock[0])
            return super().contract(definition_id, deadline=deadline)

        @override
        def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
            call_windows.append(deadline - clock[0])
            return super().operation(request, deadline=deadline)

        @override
        def read_result_document(
            self, request: OperationResultProjectionRequestV1, *, timeout: float, deadline: float
        ) -> dict[str, Any]:
            call_windows.append(deadline - clock[0])
            return super().read_result_document(request, timeout=timeout, deadline=deadline)

        @override
        def _provision_observation(self) -> OperationObservationSuccessV1:
            observed = super()._provision_observation()
            if self.action == "apply" and self.downloads < 1:
                self.downloads += 1
                return observed.model_copy(
                    update={
                        "projection": observed.projection.model_copy(
                            update={
                                "lifecycle": OperationLifecycle.RUNNING,
                                "terminal_condition": None,
                                "pending_interaction": OperationNoPendingInteractionV1(),
                                "result_ref": None,
                                "effect": OperationEffect.UNKNOWN,
                            }
                        )
                    }
                )
            return observed

    wire = SlowSetupWire()

    def decide(_: ProvisionReviewProjection) -> Literal["apply"]:
        clock[0] += 180.0
        return "apply"

    class DownloadCue:
        changed = False

        def clear(self) -> None:
            self.changed = False

        def set(self) -> None:
            self.changed = True

        def wait(self, timeout: float | None = None) -> bool:
            # Exercise the real OperationChanges wrapper: infinity must become
            # Event.wait(None), never an overflowing OS timeout or periodic poll.
            assert timeout is None and wire.observers
            waits.append(timeout)
            requests_before_cue = len(wire.requests)
            clock[0] += 180.0
            assert len(wire.requests) == requests_before_cue
            wire._cue()
            assert self.changed
            return True

    monkeypatch.setattr(operation_changes, "Event", DownloadCue)
    # The public command configures the actual digest-bound claim.
    handler = replace(_setup_review_from_public_command(monkeypatch), decide=decide)

    def run() -> (
        RegisteredOperationCompletion[ProvisionResult] | RegisteredOperationReviewCompletion[ProvisionReviewProjection]
    ):
        return run_registered_operation(
            cast(FrontendClient, wire),
            ProvisionMutationRequest(),
            definition_id=COMPONENTS_SETUP_DEFINITION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=120,
            review=handler,
            settlement_timeout=RegisteredOperationSettlement.UNBOUNDED if unbounded else None,
        )

    if unbounded:
        completion = run()
        assert isinstance(completion, RegisteredOperationCompletion)
        assert completion.operation_id == _OPERATION
        assert completion.projection.outcome is ProvisionOutcome.COMPLETED
        assert wire.action == "apply" and wire.downloads == 1 and waits == [None]
        assert clock[0] > 1000 + 120
    else:
        with pytest.raises(CliRefusedBoundaryError) as caught:
            run()
        assert caught.value.context is not None
        assert caught.value.context["operation_id"] == _OPERATION
        assert wire.action is None and not waits
    assert not wire.observers
    assert all(math.isfinite(window) and 0 < window <= 120 for window in call_windows)


def test_unbounded_settlement_preserves_exact_human_interrupt_and_releases_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wire = ProvisionReviewWire()
    interruption = KeyboardInterrupt()

    def decide(_: ProvisionReviewProjection) -> Literal["apply"]:
        raise interruption

    handler = replace(_setup_review_from_public_command(monkeypatch), decide=decide)
    with pytest.raises(KeyboardInterrupt) as caught:
        run_registered_operation(
            cast(FrontendClient, wire),
            ProvisionMutationRequest(),
            definition_id=COMPONENTS_SETUP_DEFINITION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=120,
            review=handler,
            settlement_timeout=RegisteredOperationSettlement.UNBOUNDED,
        )
    assert caught.value is interruption
    assert wire.action is None and not wire.claimed and not wire.observers


@pytest.mark.parametrize("wake", ["disconnect", "interrupt"])
def test_unbounded_signal_wait_releases_subscription_on_disconnect_or_interrupt(
    monkeypatch: pytest.MonkeyPatch, wake: str
) -> None:
    from cadrumo_client.transport import operation_changes

    class DownloadingWire(ProvisionReviewWire):
        @override
        def _provision_observation(self) -> OperationObservationSuccessV1:
            observed = super()._provision_observation()
            if self.action is not None:
                return observed.model_copy(
                    update={
                        "projection": observed.projection.model_copy(
                            update={
                                "lifecycle": OperationLifecycle.RUNNING,
                                "terminal_condition": None,
                                "pending_interaction": OperationNoPendingInteractionV1(),
                                "result_ref": None,
                                "effect": OperationEffect.UNKNOWN,
                            }
                        )
                    }
                )
            return observed

    wire = DownloadingWire()
    interruption = KeyboardInterrupt()
    waits: list[float | None] = []

    class LostConnectionCue:
        changed = False

        def clear(self) -> None:
            self.changed = False

        def set(self) -> None:
            self.changed = True

        def wait(self, timeout: float | None = None) -> bool:
            assert timeout is None and wire.observers
            waits.append(timeout)
            if wake == "interrupt":
                raise interruption
            # Native connection loss delivers the same wake as an operation cue;
            # the next observation must recheck the original session identity.
            wire.session_id = uuid4()
            wire._cue()
            assert self.changed
            return True

    monkeypatch.setattr(operation_changes, "Event", LostConnectionCue)
    with pytest.raises(KeyboardInterrupt if wake == "interrupt" else CliRefusedBoundaryError) as caught:
        run_registered_operation(
            cast(FrontendClient, wire),
            ProvisionMutationRequest(),
            definition_id=COMPONENTS_SETUP_DEFINITION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=120,
            review=_setup_review_from_public_command(monkeypatch),
            settlement_timeout=RegisteredOperationSettlement.UNBOUNDED,
        )
    if wake == "interrupt":
        assert caught.value is interruption
    else:
        assert isinstance(caught.value, CliRefusedBoundaryError)
        assert caught.value.context is not None and caught.value.context["operation_id"] == _OPERATION
    assert waits == [None] and not wire.observers

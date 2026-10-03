"""Registered REVIEW uses one correlated transport and never replays a response."""

from __future__ import annotations

import asyncio
import json
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import Thread, get_ident
from typing import Any, Literal, cast, override
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.runtime_frame_io import write_document
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
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
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
from cadrumo.entrypoints.cli import registered_operation_deadlines, registered_operation_errors, runtime_profile_binding
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError, emit_error_and_exit
from cadrumo.entrypoints.cli.registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from cadrumo.entrypoints.cli.runtime_profile_binding import bind_profile_client, bound_profile_client
from cadrumo.entrypoints.cli.runtime_registered_operation import run_registered_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION = "c" * 64
_INTERACTION = "d" * 64
_NOW = datetime(2026, 9, 29, tzinfo=UTC)


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
        self.requests: list[RuntimeOperationRequest] = []
        self.deadlines: list[float] = []
        self.action: Literal["apply", "reject"] | None = "apply" if already_terminal else None
        self.fault = fault
        self.result_reads = 0
        self.repeated_wait = False

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

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert request.profile_id == _PROFILE and request.session_id == _SESSION
        self.requests.append(request)
        self.deadlines.append(deadline)
        reply_id = request.request_id
        if isinstance(request, RuntimeOperationSubmit):
            return RuntimeOperationSubmitted(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None),
            )
        if isinstance(request, RuntimeOperationControl):
            assert request.action == "operation_start"
            return RuntimeOperationAcknowledged(
                request_id=reply_id, runtime_boot_id=_PROFILE, connection_id=_SESSION, operation_id=_OPERATION
            )
        if isinstance(request, RuntimeOperationObserve):
            terminal = self.action is not None
            if terminal and self.fault == "repeat-wait" and not self.repeated_wait:
                self.repeated_wait = True
                terminal = False
            return RuntimeOperationObserved(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                observation=self._observation(terminal=terminal),
            )
        if isinstance(request, RuntimeOperationReview):
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
            return RuntimeOperationProjected(
                request_id=reply_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                operation_id=_OPERATION,
                projection_kind="review",
                document=json.loads(success.model_dump_json()),
            )
        assert isinstance(request, RuntimeOperationManage)
        management = request.management
        if isinstance(management, OperationDetachRequestV1):
            assert management.expected_revision == 4
            document = OperationDetachSuccessV1(operation_id=_OPERATION, revision=4)
        elif isinstance(management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1):
            assert management.actor_ref == f"session:{_SESSION}"
            assert management.interaction_id == _INTERACTION and management.revision == 4
            self.action = management.response_action
            if self.fault == "lost-ack":
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
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
        return RuntimeOperationManaged(
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
        cast(RuntimeFrontendClient, wire),
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
    manages = [item.management for item in wire.requests if isinstance(item, RuntimeOperationManage)]
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


@pytest.mark.parametrize("fault", ["review-schema", "reply-id", "session", "control-revision", "no-authority"])
def test_registered_review_rejects_stale_or_unadmitted_control_before_mutation(fault: str) -> None:
    wire = ReviewWire(fault=fault)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _run(wire, _handler("apply"))
    assert caught.value.context is not None
    assert caught.value.context["operation_id"] == _OPERATION
    assert wire.action is None and wire.result_reads == 0
    assert not any(
        isinstance(item, RuntimeOperationManage)
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
            isinstance(item, RuntimeOperationManage) and isinstance(item.management, OperationResponseApplyRequestV1)
            for item in wire.requests
        )
        == 1
    )


def test_unhandled_waiting_review_refuses_and_unchanged_terminal_caller_still_reads_result() -> None:
    waiting = ReviewWire()
    with pytest.raises(CliRefusedBoundaryError):
        _run(waiting, None)
    assert not any(isinstance(item, RuntimeOperationReview | RuntimeOperationManage) for item in waiting.requests)
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
    assert not any(isinstance(item, RuntimeOperationManage) for item in wire.requests)

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
    assert refused.value.context["reason"] == RuntimeRefusalCode.DEADLINE_EXCEEDED.value
    assert not any(isinstance(item, RuntimeOperationManage) for item in timed.requests)


_RELEASE_CONTEXT: ContextVar[str | None] = ContextVar("cli_release_test_context", default=None)


class ReleaseFaultChannel:
    """Explicit byte port exercising real framing and native-release ownership."""

    def __init__(self, *, close_failures: int) -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.close_failures = close_failures
        self.failure = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
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

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))

    def close(self) -> None:
        self.close_calls += 1
        self.close_contexts.append(_RELEASE_CONTEXT.get())
        self.close_threads.append(get_ident())
        if self.close_calls <= self.close_failures:
            raise OSError("synthetic native release failure")


class FramingFaultClient(RuntimeFrontendClient):
    """Script submission only; observation uses the real verified byte connection."""

    def __init__(self, channel: ReleaseFaultChannel) -> None:
        deadline = time.monotonic() + 5
        hello = RuntimeServerHello(product_version="cleanup-test", storage_identity="a" * 64, boot_id=_PROFILE)
        write_document(channel, hello, deadline=deadline)
        channel.inbound.extend(b"".join(channel.writes))
        channel.writes.clear()
        self.native_connection = VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(product_version=hello.product_version, storage_identity=hello.storage_identity),
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
    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        if isinstance(request, RuntimeOperationObserve):
            reply = self.native_connection.operation(request, deadline=deadline)
            assert isinstance(reply, RuntimeOperationObserved)
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
    assert mapped.context["reason"] == RuntimeRefusalCode.DEADLINE_EXCEEDED.value
    assert mapped.__cause__ is None
    assert channel.close_calls == 2
    retained = _retained_cleanup(mapped)
    original = _retained_cleanup(channel.failure)
    assert len(retained.resources) == 1 and retained.resources == original.resources
    assert mapped.__dict__["_runtime_transport_cleanup"] is channel.failure.__dict__["_runtime_transport_cleanup"]
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
    primary = asyncio.CancelledError() if cancel else RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
        _OPERATION, RuntimeRefusalCode.INVALID_FRAME.value, terminal_condition=None, effect=OperationEffect.UNKNOWN
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
    with pytest.raises(RuntimeRefusalError) as caught, context:
        bind_profile_client(context, client, profile_id=_PROFILE)
        client.native_connection.operation(
            RuntimeOperationObserve(
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
    primary = asyncio.CancelledError() if cancel else RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
            _OPERATION, RuntimeRefusalCode.INVALID_FRAME.value, terminal_condition=None, effect=OperationEffect.UNKNOWN
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
        controls.setattr(runtime_profile_binding, "Thread", FailStartThread)
        expected = (
            AsyncResourceCleanupError
            if body == "normal"
            else RuntimeRefusalError
            if body in {"exchange", "released_exchange"}
            else type(primary)
        )
        with pytest.raises(expected) as caught, context:
            bind_profile_client(context, client, profile_id=_PROFILE)
            if body == "rendered":
                raise typer.Exit(code=1) from primary
            if body in {"exchange", "released_exchange"}:
                client.native_connection.operation(
                    RuntimeOperationObserve(
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

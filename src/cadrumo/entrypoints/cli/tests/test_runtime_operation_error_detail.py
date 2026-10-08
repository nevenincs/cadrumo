"""The CLI reports a stopped or unsettled runtime operation as what it is, not as a bare refusal.

A refused or failed operation carries its recorded public error detail back to
the command, so the envelope names the stopped executor's own code, message,
context and verdict. A failure with no registered code is an internal fault.
An operation still running when the command stops waiting is reported with its
identity, an unknown effect and the read that shows its outcome later -- never
as a refusal of work that may yet commit.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, cast, override
from uuid import UUID

import pytest
from pydantic import JsonValue, TypeAdapter

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
)
from cadrumo.application.cli_exception_preconditions import (
    CliExceptionPrecondition,
    cli_exception_no_recovery_verdict,
)
from cadrumo.application.modelo.action_errors import ModeloProfileReadinessError
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
    build_modelo_work_file_definition,
    build_modelo_work_file_registration,
    build_modelo_work_verify_definition,
    build_modelo_work_verify_registration,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from cadrumo.application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    build_operation_error_detail,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicEventV1,
    OperationPublicNoticeEventV1,
    OperationPublicPhaseEventV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus, PublicReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationResultPage,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.projection_pages import project_document_page
from cadrumo.core.errors.error_codes import build_error_envelope, get_registered_error_code
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.cli.errors import (
    CliOperationStillRunningError,
    CliOutboundPayloadBoundaryError,
    CliRecordedOperationError,
    CliUnexpectedBoundaryError,
)
from cadrumo.entrypoints.cli.registered_operation_contracts import RegisteredOperationProgress
from cadrumo.entrypoints.cli.registered_operation_errors import (
    detailed_registered_operation_error,
    submitted_operation_error,
)
from cadrumo.entrypoints.cli.registered_operation_observations import wait_registered_settlement
from cadrumo.entrypoints.cli.runtime_modelo_verification import run_modelo_work_filing, run_modelo_work_verification
from cadrumo.entrypoints.cli.runtime_registered_operation import run_registered_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION = "c" * 64
_WORK_UNIT = "b" * 64
_NOW = datetime(2026, 10, 2, tzinfo=UTC)
_REFUSAL_CODE = "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"
_DIAGNOSTIC = "sha256:" + "d" * 64


@pytest.mark.parametrize(
    "message_key",
    (
        "application.modelo.errors.profile_readiness_missing",
        "application.modelo.errors.profile_readiness_setup_incomplete_missing",
    ),
)
def test_profile_requirement_explanation_survives_recorded_detail(message_key: str) -> None:
    """Public labels survive native transport while wizard internals stay suppressed."""
    explanation = "Activity description (Ley 37/1992, art. 164)"
    error = ModeloProfileReadinessError(
        translated_message=message_key,
        context={
            "modelo": "303",
            "filing_year": 2024,
            "period": "1T",
            "profile_requirements": explanation,
            "missing": ("private-question-id",),
            "flow_id": "private-flow-id",
        },
    )
    detail = build_operation_error_detail(error)
    assert detail is not None
    persisted = OperationErrorDetailV1.model_validate_json(detail.model_dump_json())
    assert persisted.context_mapping()["profile_requirements"] == explanation
    assert "missing" not in persisted.context_mapping()
    assert "flow_id" not in persisted.context_mapping()
    recorded = detailed_registered_operation_error(persisted, {})
    envelope = build_error_envelope(recorded)
    assert envelope.message == build_error_envelope(error).message
    assert explanation in envelope.message
    assert "%{" not in envelope.message
    assert "private-question-id" not in envelope.model_dump_json()
    assert "private-flow-id" not in envelope.model_dump_json()


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_modelo_work_calculate_definition(
        calculation_action_ports_factory=_unavailable,
        attachment_store_factory=_unavailable,
    )
    return build_modelo_work_calculate_registration(definition).contract


def _registered_detail() -> OperationErrorDetailV1:
    verdict = cli_exception_no_recovery_verdict(
        CliExceptionPrecondition.REFUSAL_RETRIED, facts={"boundary_error_type": "probe"}
    )
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key="aggregation.grouping.errors.unsupported_modelo",
        context=(
            OperationErrorContextEntryV1(key="modelo", value="111"),
            OperationErrorContextEntryV1(key="reason", value="typed_reason"),
        ),
        precondition_verdict_json=verdict.model_dump_json(),
    )


class _SettlingWire:
    """An explicit runtime transport port whose operation settles one declared way."""

    profile_id = _PROFILE
    session_id = _SESSION
    frontend = OperationFrontendProjection.CLI

    def __init__(self, outcome: str, *, public_contract: OperationPublicDefinitionContractV1 | None = None) -> None:
        self.outcome = outcome
        self.public_contract = _contract() if public_contract is None else public_contract
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.detail_reads: list[OperationResultProjectionRequestV1] = []

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == self.public_contract.definition_id and deadline > 0
        return self.public_contract

    def read_result_document(
        self, request: OperationResultProjectionRequestV1, *, timeout: float, deadline: float
    ) -> dict[str, Any]:
        assert timeout > 0 and deadline > 0
        assert request.result_schema == operation_error_detail_schema()
        self.detail_reads.append(request)
        if self.outcome == "refused":
            document = OperationResultProjectionSuccessV1[OperationErrorDetailV1](
                result_schema=operation_error_detail_schema(),
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=_registered_detail(),
            )
        else:
            document = OperationResultProjectionRefusalV1(
                code=OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
                diagnostic_ref=None,
            )
        return json.loads(document.model_dump_json())

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0
        if isinstance(request, RuntimeOperationSubmit):
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION, secret_requirement=None),
            )
        if isinstance(request, RuntimeOperationControl):
            return RuntimeOperationAcknowledged(
                request_id=request.request_id, runtime_boot_id=_PROFILE, connection_id=_SESSION, operation_id=_OPERATION
            )
        assert isinstance(request, RuntimeOperationObserve)
        return RuntimeOperationObserved(
            request_id=request.request_id,
            runtime_boot_id=_PROFILE,
            connection_id=_SESSION,
            observation=self._observation(after_cursor=request.observation.after_cursor),
        )

    def _observation(self, *, after_cursor: int = 0) -> OperationObservationSuccessV1:
        running = self.outcome == "running"
        condition = {
            "refused": OperationTerminalCondition.REFUSED,
            "failed": OperationTerminalCondition.FAILED,
        }.get(self.outcome)
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION,
            definition_id=self.public_contract.definition_id,
            subject_ref=_WORK_UNIT,
            revision=2 if running else 3,
            anchor_cursor=1,
            definition_contract=self.public_contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=OperationLifecycle.RUNNING if running else OperationLifecycle.TERMINAL,
            terminal_condition=condition,
            effect=OperationEffect.NONE,
            phase_code=None,
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.public_contract.close_policy,
            cancellation=self.public_contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1(),
            result_ref=None,
            refusal_ref=_REFUSAL_CODE if condition is OperationTerminalCondition.REFUSED else None,
            failure_error_code=None,
            diagnostic_ref=_DIAGNOSTIC if condition is OperationTerminalCondition.FAILED else None,
        )
        page = OperationPublicEventPageV1(
            operation_id=_OPERATION,
            anchor_cursor=1,
            requested_cursor=after_cursor,
            status=OperationReplayStatus.PAGE if after_cursor == 0 else OperationReplayStatus.CAUGHT_UP,
            events=(
                OperationPublicPhaseEventV1(
                    revision=2,
                    sequence=1,
                    timestamp=_NOW,
                    code=self._phase_code(),
                    phase_code=self._phase_code(),
                ),
            )
            if after_cursor == 0
            else (),
            next_cursor=1,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=page)

    def _phase_code(self) -> str:
        if self.public_contract.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID:
            return "modelo.work.verify.gates"
        if self.public_contract.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID:
            return "modelo.work.file.preconditions"
        return "modelo.work.calculate.ledger"


def _calculate(wire: _SettlingWire, *, settlement_timeout: float | None = None) -> object:
    return run_registered_operation(
        cast(RuntimeFrontendClient, wire),
        ModeloWorkCalculateRequest(work_unit_id=_WORK_UNIT, actor="operator"),
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=_WORK_UNIT,
        result_type=ModeloWorkCalculatePublicResultV2,
        request_version=4,
        result_version=2,
        timeout=1,
        settlement_timeout=settlement_timeout,
        pending_check_command=f"aeat app modelo work revisions {_WORK_UNIT}",
    )


def test_a_refusal_with_recorded_detail_is_the_executors_own_error() -> None:
    """The code, message key, typed context and verdict the worker recorded reach the envelope."""
    wire = _SettlingWire("refused")
    with pytest.raises(CliRecordedOperationError) as raised:
        _calculate(wire)

    error = raised.value
    assert get_registered_error_code(error).code == _REFUSAL_CODE
    assert error.translated_message == "aggregation.grouping.errors.unsupported_modelo"
    assert error.context is not None
    assert error.context["modelo"] == "111"
    # The executor's own reason wins; the transport code does not overwrite it.
    assert error.context["reason"] == "typed_reason"
    assert error.context["operation_id"] == _OPERATION
    assert error.context["terminal_condition"] == OperationTerminalCondition.REFUSED.value
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == CliExceptionPrecondition.REFUSAL_RETRIED.value
    assert len(wire.detail_reads) == 1


def test_a_failure_without_a_registered_code_or_detail_is_an_internal_fault() -> None:
    """A failed executor that recorded nothing public is never reported as a refusal."""
    wire = _SettlingWire("failed")
    with pytest.raises(CliRecordedOperationError) as raised:
        _calculate(wire)

    error = raised.value
    assert get_registered_error_code(error).code == get_registered_error_code(CliUnexpectedBoundaryError).code
    assert error.context is not None
    assert error.context["diagnostic_ref"] == _DIAGNOSTIC
    assert error.context["terminal_condition"] == OperationTerminalCondition.FAILED.value
    assert "reason" not in error.context


def test_an_operation_still_running_when_the_wait_ends_is_reported_unsettled_not_refused() -> None:
    """The command names the operation, an unknown effect and how to read its outcome later."""
    wire = _SettlingWire("running")
    with pytest.raises(CliOperationStillRunningError) as raised:
        _calculate(wire, settlement_timeout=1.0)

    context = raised.value.context
    assert context == {
        "operation_id": _OPERATION,
        "effect": OperationEffect.UNKNOWN.value,
        "check_command": f"aeat app modelo work revisions {_WORK_UNIT}",
    }
    assert get_registered_error_code(raised.value).code == "LOCKED_CLI_OPERATION_STILL_RUNNING"


def test_a_settlement_wait_shorter_than_one_exchange_is_refused_as_a_programming_error() -> None:
    """The wait bounds settlement; it can never be shorter than one exchange."""
    with pytest.raises(ValueError, match="settlement wait"):
        _calculate(_SettlingWire("running"), settlement_timeout=0.5)


def test_a_record_fault_detail_keeps_the_outbound_payload_classification() -> None:
    """A worker-side record fault is reported as the in-process boundary reported it."""
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.RECORD_VALIDATION,
        error_code=None,
        message_key=None,
        context=(
            OperationErrorContextEntryV1(key="failing_record", value="BucketEvent"),
            OperationErrorContextEntryV1(key="violations", value="<key>: String should have at most 64 characters"),
        ),
    )
    error = submitted_operation_error(
        _OPERATION,
        OperationTerminalCondition.FAILED.value,
        terminal_condition=OperationTerminalCondition.FAILED,
        effect=OperationEffect.NONE,
        detail=detail,
    )

    assert isinstance(error, CliRecordedOperationError)
    assert get_registered_error_code(error).code == get_registered_error_code(CliOutboundPayloadBoundaryError).code
    assert error.context is not None
    assert error.context["failing_record"] == "BucketEvent"
    assert error.terminal_precondition_verdict is None


class _UnavailableOperatorScope:
    """Tripwire ports: constructing the real public contract needs no private custody."""

    def resolve(self, root: Path, bucket_id: str) -> NoReturn:
        return _unavailable(root, bucket_id)

    def acquire_lock(self, paths: OperatorScopeBucketPaths, *, wait_seconds: float) -> NoReturn:
        return _unavailable(paths, wait_seconds=wait_seconds)

    def release_lock(self, paths: OperatorScopeBucketPaths) -> NoReturn:
        return _unavailable(paths)

    def current(self) -> NoReturn:
        return _unavailable()

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> NoReturn:
        return _unavailable(session, bucket_id)


def _verification_contract() -> OperationPublicDefinitionContractV1:
    unavailable = _UnavailableOperatorScope()
    definition = build_modelo_work_verify_definition(
        certificate_secret_backend_factory=_unavailable,
        operator_scope_ports=OperatorScopePorts(storage=unavailable, session=unavailable),
        verification_repository_bundle_factory=_unavailable,
        profile_resolver=_unavailable,
    )
    return build_modelo_work_verify_registration(definition).contract


class _VerificationWire(RuntimeFrontendClient):
    """Typed transport with real result-page collection and a clock advanced only between polls."""

    def __init__(
        self,
        *,
        elapsed_after_poll: float,
        outcome_after_poll: str,
        public_contract: OperationPublicDefinitionContractV1 | None = None,
    ) -> None:
        self._profile_id = _PROFILE
        self._session_id = _SESSION
        self._frontend = OperationFrontendProjection.CLI
        self.wire = _SettlingWire(
            "running", public_contract=_verification_contract() if public_contract is None else public_contract
        )
        self.elapsed = 0.0
        self.elapsed_after_poll = elapsed_after_poll
        self.outcome_after_poll = outcome_after_poll
        self.exchanges: list[tuple[str, float, float]] = []
        self.requests: list[RuntimeOperationRequest] = []
        self.poll_sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        assert 0 < seconds <= 0.5
        self.poll_sleeps.append(seconds)
        self.elapsed = self.elapsed_after_poll
        self.wire.outcome = self.outcome_after_poll

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        self.exchanges.append(("contract", self.monotonic(), deadline))
        return self.wire.contract(definition_id, deadline=deadline)

    @override
    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        assert request.profile_id == self.profile_id
        assert request.session_id == self.session_id
        assert deadline > self.monotonic()
        self.requests.append(request)
        self.exchanges.append((request.action, self.monotonic(), deadline))
        if isinstance(request, RuntimeOperationResultPage):
            assert request.result.operation_id == _OPERATION
            assert request.result.terminal_revision == 3
            assert request.result.definition_contract_digest == self.wire.public_contract.definition_contract_digest
            assert request.result.result_schema == operation_error_detail_schema()
            self.wire.detail_reads.append(request.result)
            document = OperationResultProjectionSuccessV1[OperationErrorDetailV1](
                result_schema=operation_error_detail_schema(),
                definition_contract_digest=self.wire.public_contract.definition_contract_digest,
                projection=_registered_detail(),
            )
            encoded = TypeAdapter(dict[str, JsonValue]).validate_json(document.model_dump_json())
            return RuntimeOperationPage(
                request_id=request.request_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                operation_id=_OPERATION,
                page=project_document_page(encoded, request.page),
            )
        return self.wire.operation(request, deadline=deadline)


def _verification_clock(monkeypatch: pytest.MonkeyPatch, wire: _VerificationWire) -> None:
    monkeypatch.setattr("cadrumo.entrypoints.cli.registered_operation_deadlines.time.monotonic", wire.monotonic)
    monkeypatch.setattr("cadrumo.entrypoints.cli.registered_operation_observations.time.sleep", wire.sleep)


def _assert_verification_admission(wire: _VerificationWire, *, observations: int) -> None:
    bounded = [exchange for exchange in wire.exchanges if exchange[0] != "operation_result_page"]
    assert [stage for stage, _entered, _deadline in bounded] == [
        "contract",
        "operation_submit",
        "operation_start",
        *(["operation_observe"] * observations),
    ]
    assert all(0 < deadline - entered <= 60 for _stage, entered, deadline in bounded)
    submitted = wire.requests[0]
    assert isinstance(submitted, RuntimeOperationSubmit)
    assert submitted.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID
    assert submitted.subject_ref == _WORK_UNIT
    assert ModeloWorkVerifyRequest.model_validate_json(submitted.payload_json) == ModeloWorkVerifyRequest(
        calculation_revision_id=_WORK_UNIT, actor="operator"
    )
    started = wire.requests[1]
    assert isinstance(started, RuntimeOperationControl)
    assert started.action == "operation_start"
    assert started.operation_id == _OPERATION
    observed = [request for request in wire.requests if isinstance(request, RuntimeOperationObserve)]
    assert [request.observation.operation_id for request in observed] == [_OPERATION] * observations
    assert [request.observation.after_cursor for request in observed] == list(range(observations))
    assert len({request.request_id for request in wire.requests}) == len(wire.requests)
    assert wire.poll_sleeps == [0.02]


@pytest.mark.parametrize(
    ("elapsed", "settlement_timeout", "result_deadline"),
    [(61.0, None, 1800.0), (59.0, 60.0, 119.0)],
    ids=["default-settlement-after-exchange-budget", "custom-settlement-fresh-result-budget"],
)
def test_verification_settlement_and_recorded_detail_keep_distinct_read_budgets(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, settlement_timeout: float | None, result_deadline: float
) -> None:
    """A real verify contract preserves the terminal error and its separate result-page horizon."""
    wire = _VerificationWire(elapsed_after_poll=elapsed, outcome_after_poll="refused")
    _verification_clock(monkeypatch, wire)
    request = ModeloWorkVerifyRequest(calculation_revision_id=_WORK_UNIT, actor="operator")
    with pytest.raises(CliRecordedOperationError) as raised:
        if settlement_timeout is None:
            run_modelo_work_verification(wire, work_unit_id=_WORK_UNIT, request=request, timeout=60)
        else:
            run_modelo_work_verification(
                wire, work_unit_id=_WORK_UNIT, request=request, timeout=60, settlement_timeout=settlement_timeout
            )

    error = raised.value
    assert get_registered_error_code(error).code == _REFUSAL_CODE
    assert error.translated_message == "aggregation.grouping.errors.unsupported_modelo"
    assert error.context == {
        "modelo": "111",
        "reason": "typed_reason",
        "operation_id": _OPERATION,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }
    assert error.terminal_precondition_verdict == cli_exception_no_recovery_verdict(
        CliExceptionPrecondition.REFUSAL_RETRIED, facts={"boundary_error_type": "probe"}
    )
    _assert_verification_admission(wire, observations=2)
    assert len(wire.wire.detail_reads) == 1
    assert wire.exchanges[-1] == ("operation_result_page", elapsed, result_deadline)
    assert result_deadline > 60
    assert result_deadline - elapsed >= 60


@pytest.mark.parametrize(
    ("elapsed", "settlement_timeout"),
    [(61.0, 60.0), (1801.0, None)],
    ids=["custom-settlement-expiry", "default-settlement-expiry"],
)
def test_verification_wait_expiry_preserves_identity_without_reading_or_replaying(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, settlement_timeout: float | None
) -> None:
    """The real registered loop stops waiting, names the operation and leaves its effect unknown."""
    wire = _VerificationWire(elapsed_after_poll=elapsed, outcome_after_poll="running")
    _verification_clock(monkeypatch, wire)
    request = ModeloWorkVerifyRequest(calculation_revision_id=_WORK_UNIT, actor="operator")
    with pytest.raises(CliOperationStillRunningError) as raised:
        if settlement_timeout is None:
            run_modelo_work_verification(wire, work_unit_id=_WORK_UNIT, request=request, timeout=60)
        else:
            run_modelo_work_verification(
                wire, work_unit_id=_WORK_UNIT, request=request, timeout=60, settlement_timeout=settlement_timeout
            )

    assert get_registered_error_code(raised.value).code == "LOCKED_CLI_OPERATION_STILL_RUNNING"
    assert raised.value.context == {"operation_id": _OPERATION, "effect": OperationEffect.UNKNOWN.value}
    assert wire.wire.detail_reads == []
    _assert_verification_admission(wire, observations=1)
    assert wire.exchanges[-1][0] == "operation_observe"


@pytest.mark.parametrize(
    ("elapsed", "settlement_timeout", "outcome", "result_deadline"),
    [
        (61.0, None, "refused", 1800.0),
        (59.0, 60.0, "refused", 119.0),
        (61.0, 60.0, "running", None),
        (1801.0, None, "running", None),
    ],
    ids=["default-detail", "explicit-detail", "explicit-expiry", "default-expiry"],
)
def test_filing_settlement_preserves_approval_and_bounded_exchanges(
    monkeypatch: pytest.MonkeyPatch,
    elapsed: float,
    settlement_timeout: float | None,
    outcome: str,
    result_deadline: float | None,
) -> None:
    """Filing waits independently of transport, without replaying an approved operation on expiry."""
    unavailable = _UnavailableOperatorScope()
    definition = build_modelo_work_file_definition(
        operator_scope_ports=OperatorScopePorts(storage=unavailable, session=unavailable),
        filing_action_ports_factory=_unavailable,
        certificate_secret_backend_factory=_unavailable,
        profile_resolver=_unavailable,
    )
    wire = _VerificationWire(
        elapsed_after_poll=elapsed,
        outcome_after_poll=outcome,
        public_contract=build_modelo_work_file_registration(definition).contract,
    )
    _verification_clock(monkeypatch, wire)
    request = ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(calculation_revision_id=_WORK_UNIT, verification_report_id="e" * 64),
        actor="operator",
    )
    request_schema = wire.wire.public_contract.request_schema
    result_schema = wire.wire.public_contract.result_schema
    assert request_schema is not None and result_schema is not None
    assert (request_schema.schema_id, request_schema.schema_version) == ("modelo.work.file.request", 2)
    assert (result_schema.schema_id, result_schema.schema_version) == ("modelo.work.file.result", 2)
    expected_error = CliRecordedOperationError if outcome == "refused" else CliOperationStillRunningError
    with pytest.raises(expected_error) as raised:
        if settlement_timeout is None:
            run_modelo_work_filing(wire, work_unit_id=_WORK_UNIT, request=request, timeout=60)
        else:
            run_modelo_work_filing(
                wire, work_unit_id=_WORK_UNIT, request=request, timeout=60, settlement_timeout=settlement_timeout
            )

    submitted = wire.requests[0]
    assert isinstance(submitted, RuntimeOperationSubmit)
    assert submitted.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID
    assert submitted.subject_ref == _WORK_UNIT
    assert ModeloWorkFileRequest.model_validate_json(submitted.payload_json) == request
    started = wire.requests[1]
    assert isinstance(started, RuntimeOperationControl)
    assert started.action == "operation_start"
    assert started.operation_id == _OPERATION
    observations = 2 if outcome == "refused" else 1
    observed = [request for request in wire.requests if isinstance(request, RuntimeOperationObserve)]
    assert [request.observation.operation_id for request in observed] == [_OPERATION] * observations
    assert [request.observation.after_cursor for request in observed] == list(range(observations))
    bounded = [exchange for exchange in wire.exchanges if exchange[0] != "operation_result_page"]
    assert [stage for stage, _, _ in bounded] == [
        "contract",
        "operation_submit",
        "operation_start",
        *(["operation_observe"] * observations),
    ]
    assert all(0 < deadline - entered <= 60 for _, entered, deadline in bounded)
    assert len({request.request_id for request in wire.requests}) == len(wire.requests)
    assert wire.poll_sleeps == [0.02]
    if outcome == "refused":
        assert isinstance(raised.value, CliRecordedOperationError)
        assert get_registered_error_code(raised.value).code == _REFUSAL_CODE
        assert raised.value.translated_message == "aggregation.grouping.errors.unsupported_modelo"
        assert raised.value.context is not None
        assert raised.value.context["operation_id"] == _OPERATION
        assert raised.value.context["reason"] == "typed_reason"
        assert raised.value.context == {
            "modelo": "111",
            "reason": "typed_reason",
            "operation_id": _OPERATION,
            "effect": OperationEffect.NONE.value,
            "terminal_condition": OperationTerminalCondition.REFUSED.value,
        }
        assert raised.value.terminal_precondition_verdict == cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.REFUSAL_RETRIED, facts={"boundary_error_type": "probe"}
        )
        assert len(wire.wire.detail_reads) == 1
        assert wire.exchanges[-1] == ("operation_result_page", elapsed, result_deadline)
        assert result_deadline is not None
        assert result_deadline > 60
        assert result_deadline - elapsed >= 60
    else:
        assert get_registered_error_code(raised.value).code == "LOCKED_CLI_OPERATION_STILL_RUNNING"
        assert raised.value.context == {"operation_id": _OPERATION, "effect": OperationEffect.UNKNOWN.value}
        assert wire.wire.detail_reads == []


def _notice(sequence: int, notice_code: str, display_code: str | None = None) -> OperationPublicNoticeEventV1:
    return OperationPublicNoticeEventV1(
        revision=2,
        sequence=sequence,
        timestamp=_NOW,
        code=notice_code,
        notice_code=notice_code,
        display_code=display_code,
    )


class _NoticeWire:
    """A runtime observation port that answers each poll with one scripted event page."""

    session_id = _SESSION

    def __init__(self) -> None:
        self.public_contract = _contract()
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.requested_cursors: list[int] = []
        # (requested cursor, anchor, status, events, restart cursor, terminal)
        self.script: list[tuple[int, int, PublicReplayStatus, tuple[OperationPublicEventV1, ...], int | None, bool]] = [
            (
                0,
                2,
                OperationReplayStatus.PAGE,
                (_notice(1, "operation.started"), _notice(2, "auth.clave-movil.approval-pending", "YLL")),
                None,
                False,
            ),
            (2, 2, OperationReplayStatus.CAUGHT_UP, (), None, False),
            # Sequence 3 was compacted away; the CLI resumes at the restart cursor and never sees it.
            (2, 4, OperationReplayStatus.COMPACTED, (), 3, False),
            (
                3,
                5,
                OperationReplayStatus.PAGE,
                (_notice(4, "auth.clave-movil.qr-scan-pending"), _notice(5, "auth.clave-movil.unregistered")),
                None,
                True,
            ),
        ]

    def __call__(self, request: RuntimeOperationRequest) -> RuntimeOperationReply:
        assert isinstance(request, RuntimeOperationObserve)
        self.requested_cursors.append(request.observation.after_cursor)
        requested, anchor, status, events, restart, terminal = self.script.pop(0)
        assert request.observation.after_cursor == requested
        projection = OperationPublicProjectionV1(
            operation_id=_OPERATION,
            definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            subject_ref=_WORK_UNIT,
            revision=3 if terminal else 2,
            anchor_cursor=anchor,
            definition_contract=self.public_contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.RUNNING,
            terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
            effect=OperationEffect.NONE,
            phase_code=None,
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.public_contract.close_policy,
            cancellation=self.public_contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1(),
            result_ref="sha256:" + "e" * 64 if terminal else None,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        next_cursor = events[-1].sequence if events else (restart if restart is not None else anchor)
        page = OperationPublicEventPageV1(
            operation_id=_OPERATION,
            anchor_cursor=anchor,
            requested_cursor=requested,
            status=status,
            events=events,
            next_cursor=next_cursor,
            restart_cursor=restart,
        )
        return RuntimeOperationObserved(
            request_id=request.request_id,
            runtime_boot_id=_PROFILE,
            connection_id=_SESSION,
            observation=OperationObservationSuccessV1(projection=projection, event_page=page),
        )


def test_settlement_wait_prompts_each_known_operation_notice_once_on_stderr(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker's Cl@ve prompt reaches the operator; unknown notices and stdout stay silent."""
    monkeypatch.setattr("cadrumo.entrypoints.cli.registered_operation_observations.time.sleep", lambda _s: None)
    wire = _NoticeWire()
    state, review = wait_registered_settlement(
        cast(RuntimeFrontendClient, wire),
        _OPERATION,
        _PROFILE,
        _SESSION,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        _WORK_UNIT,
        wire.public_contract,
        float("inf"),
        None,
        RegisteredOperationProgress(),
        None,
        wire,
    )

    assert review is None
    assert state.lifecycle is OperationLifecycle.TERMINAL
    assert wire.requested_cursors == [0, 2, 2, 3]
    captured = capsys.readouterr()
    assert captured.out == ""
    approval = tr("operation.notice.clave_movil_approval_pending_with_code", code="YLL")
    scan = tr("operation.notice.clave_movil_qr_scan_pending")
    assert "YLL" in approval
    assert captured.err == f"{approval}\n{scan}\n"

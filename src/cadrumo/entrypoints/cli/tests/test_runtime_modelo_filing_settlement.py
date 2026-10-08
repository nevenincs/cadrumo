"""Filing settlement keeps bounded admission/polling and the existing settled-result read budget."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, override
from uuid import UUID

import pytest
from pydantic import JsonValue, TypeAdapter

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
)
from cadrumo.application.modelo.filing_projection import ModeloFilingRecordSnapshot
from cadrumo.application.modelo.lifecycle_advisories import ModeloLifecycleAdvisories
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    build_modelo_work_file_definition,
    build_modelo_work_file_registration,
)
from cadrumo.application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
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
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from cadrumo.entrypoints.cli.errors import (
    CliOperationStillRunningError,
)
from cadrumo.entrypoints.cli.runtime_modelo_verification import run_modelo_work_filing

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION = "c" * 64
_WORK_UNIT = "b" * 64
_NOW = datetime(2026, 10, 2, tzinfo=UTC)


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


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


def _filing_contract() -> OperationPublicDefinitionContractV1:
    unavailable = _UnavailableOperatorScope()
    definition = build_modelo_work_file_definition(
        certificate_secret_backend_factory=_unavailable,
        operator_scope_ports=OperatorScopePorts(storage=unavailable, session=unavailable),
        filing_action_ports_factory=_unavailable,
        profile_resolver=_unavailable,
    )
    return build_modelo_work_file_registration(definition).contract


class _FilingWire(RuntimeFrontendClient):
    """Typed transport with real result-page collection and a clock advanced only between polls."""

    def __init__(self, *, elapsed_after_poll: float, outcome_after_poll: str) -> None:
        self._profile_id = _PROFILE
        self._session_id = _SESSION
        self._frontend = OperationFrontendProjection.CLI
        self.public_contract = _filing_contract()
        self.contract_set_digest = OperationPublicContractSetV1.build((self.public_contract,)).contract_set_digest
        self.result_reads: list[OperationResultProjectionRequestV1] = []
        self.outcome = "running"
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
        self.outcome = self.outcome_after_poll

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        self.exchanges.append(("contract", self.monotonic(), deadline))
        assert definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID
        return self.public_contract

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
            assert request.result.definition_contract_digest == self.public_contract.definition_contract_digest
            expected_schema = self.public_contract.result_schema
            assert request.result.result_schema == expected_schema
            self.result_reads.append(request.result)
            assert expected_schema is not None
            document = OperationResultProjectionSuccessV1[ModeloWorkFilePublicResultV2](
                result_schema=expected_schema,
                definition_contract_digest=self.public_contract.definition_contract_digest,
                projection=_filing_result(),
            )
            encoded = TypeAdapter(dict[str, JsonValue]).validate_json(document.model_dump_json())
            return RuntimeOperationPage(
                request_id=request.request_id,
                runtime_boot_id=_PROFILE,
                connection_id=_SESSION,
                operation_id=_OPERATION,
                page=project_document_page(encoded, request.page),
            )
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
        condition = None if running else OperationTerminalCondition.SUCCEEDED
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
            effect=OperationEffect.NONE if running else OperationEffect.UPDATED,
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
            result_ref="sha256:" + "e" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
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
                    code="modelo.work.file.preconditions",
                    phase_code="modelo.work.file.preconditions",
                ),
            )
            if after_cursor == 0
            else (),
            next_cursor=1,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=page)


def _filing_clock(monkeypatch: pytest.MonkeyPatch, wire: _FilingWire) -> None:
    monkeypatch.setattr("cadrumo.entrypoints.cli.registered_operation_deadlines.time.monotonic", wire.monotonic)
    monkeypatch.setattr("cadrumo.entrypoints.cli.registered_operation_observations.time.sleep", wire.sleep)


def _assert_filing_admission(wire: _FilingWire, *, observations: int) -> None:
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
    assert submitted.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID
    assert submitted.subject_ref == _WORK_UNIT
    assert ModeloWorkFileRequest.model_validate_json(submitted.payload_json) == ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(calculation_revision_id=_WORK_UNIT, verification_report_id="d" * 64),
        actor="operator",
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
    ("elapsed", "settlement_timeout"),
    [(61.0, 60.0), (1801.0, None)],
    ids=["custom-settlement-expiry", "default-settlement-expiry"],
)
def test_filing_wait_expiry_preserves_identity_without_reading_or_replaying(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, settlement_timeout: float | None
) -> None:
    """The real registered loop stops waiting, names the operation and leaves its effect unknown."""
    wire = _FilingWire(elapsed_after_poll=elapsed, outcome_after_poll="running")
    _filing_clock(monkeypatch, wire)
    request = ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(calculation_revision_id=_WORK_UNIT, verification_report_id="d" * 64),
        actor="operator",
    )
    with pytest.raises(CliOperationStillRunningError) as raised:
        if settlement_timeout is None:
            run_modelo_work_filing(wire, work_unit_id=_WORK_UNIT, request=request, timeout=60)
        else:
            run_modelo_work_filing(
                wire, work_unit_id=_WORK_UNIT, request=request, timeout=60, settlement_timeout=settlement_timeout
            )

    assert get_registered_error_code(raised.value).code == "LOCKED_CLI_OPERATION_STILL_RUNNING"
    assert raised.value.context == {"operation_id": _OPERATION, "effect": OperationEffect.UNKNOWN.value}
    assert wire.result_reads == []
    _assert_filing_admission(wire, observations=1)
    assert wire.exchanges[-1][0] == "operation_observe"


@pytest.mark.parametrize("settlement_timeout", [0.0, 59.0, float("nan"), float("inf"), -float("inf"), 3601.0])
def test_filing_refuses_invalid_settlement_before_any_exchange(settlement_timeout: float) -> None:
    wire = _FilingWire(elapsed_after_poll=61.0, outcome_after_poll="running")
    request = ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(calculation_revision_id=_WORK_UNIT, verification_report_id="d" * 64),
        actor="operator",
    )
    with pytest.raises(ValueError, match="settlement wait"):
        run_modelo_work_filing(wire, work_unit_id=_WORK_UNIT, request=request, settlement_timeout=settlement_timeout)
    assert wire.exchanges == []
    assert wire.requests == []


def _filing_result() -> ModeloWorkFilePublicResultV2:
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT, calculation_revision_id=_WORK_UNIT, filed_by="operator"
        ),
        work_unit_id=_WORK_UNIT,
        calculation_revision_id=_WORK_UNIT,
        bucket_id=str(_PROFILE),
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        filed_at=_NOW,
        filed_by="operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    return ModeloWorkFilePublicResultV2(
        record=ModeloFilingRecordSnapshot.from_record(record),
        advisories=ModeloLifecycleAdvisories(
            work_unit_id=_WORK_UNIT, calculation_revision_id=_WORK_UNIT, modelo="303", filing_year=2025, period="4T"
        ),
        published=True,
        filing_record_id=record.filing_record_id,
        work_unit_id=_WORK_UNIT,
        calculation_revision_id=_WORK_UNIT,
    )


@pytest.mark.parametrize(("elapsed", "settlement_timeout"), [(61.0, None), (61.0, 120.0)])
def test_filing_returns_committed_record_after_one_exchange_budget(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, settlement_timeout: float | None
) -> None:
    wire = _FilingWire(elapsed_after_poll=elapsed, outcome_after_poll="succeeded")
    _filing_clock(monkeypatch, wire)
    request = ModeloWorkFileRequest(
        approval=ModeloWorkFileApproval(calculation_revision_id=_WORK_UNIT, verification_report_id="d" * 64),
        actor="operator",
    )
    if settlement_timeout is None:
        completed = run_modelo_work_filing(wire, work_unit_id=_WORK_UNIT, request=request)
    else:
        completed = run_modelo_work_filing(
            wire, work_unit_id=_WORK_UNIT, request=request, settlement_timeout=settlement_timeout
        )
    assert completed.effect is OperationEffect.UPDATED
    assert completed.projection == _filing_result()
    assert completed.projection.handoff_required
    _assert_filing_admission(wire, observations=2)
    assert len(wire.result_reads) == 1

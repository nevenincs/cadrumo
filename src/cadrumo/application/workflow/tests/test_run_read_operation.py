"""Workflow reads bind period authority to an explicit request and captured run."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.modelo import Modelo
from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..run_models import (
    WorkflowDeadlineContextDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from ..run_projection import WorkflowObligationSnapshot, WorkflowRunSnapshot, validate_run_period_facts
from ..run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    WorkflowRunListProjection,
    WorkflowRunListRequest,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
    _read_exact_run,
    build_workflow_run_list_definition,
    build_workflow_run_list_registration,
    build_workflow_run_read_definition,
    build_workflow_run_read_registration,
)
from ..run_read_ports import WorkflowRunReadPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 12, 9, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_NEXT = Period.from_year_and_code(2025, "2T")


def _run(*, period: Period | None = _PERIOD, detail_period: Period | None = None) -> WorkflowResult:
    obligation = (
        WorkflowObligationFacts(
            modelo=Modelo("303"),
            period=period,
            opens_on=date(2025, 4, 1),
            closes_on=date(2025, 4, 20),
            status=ObligationStatus.UPCOMING,
        )
        if period is not None
        else None
    )
    details = (
        WorkflowDeadlineContextDetails(
            kind="deadline_context",
            modelo=Modelo("303"),
            period=detail_period,
            opens_on=date(2025, 4, 1),
        )
        if detail_period is not None
        else None
    )
    steps = (
        (
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=_NOW,
                ended_at=_NOW,
                success=True,
                summary_locale_key="application.workflow.steps.deadline_open",
                details=details,
            ),
        )
        if details is not None
        else ()
    )
    return WorkflowResult(
        run_id="a" * 16,
        started_at=_NOW,
        ended_at=_NOW,
        final_stage=WorkflowStage.DONE,
        obligation=obligation,
        steps=steps,
        summary_locale_key="application.workflow.results.completed",
        summary_details=details,
    )


class _Reader:
    def __init__(self, run: WorkflowResult) -> None:
        self.run = run
        self.loads = 0

    def load(self, run_id: str) -> WorkflowResult:
        self.loads += 1
        assert run_id == "a" * 16
        return self.run

    def list(self, *, since: date | None = None) -> tuple[WorkflowResult, ...]:
        assert since is None
        return (self.run,)


def _factory(reader: _Reader, *, bucket_id: str = str(_PROFILE)):
    def factory(*, bucket_id: str) -> WorkflowRunReadPorts:
        assert bucket_id == str(_PROFILE)
        return WorkflowRunReadPorts(bucket_id=str(_OTHER) if wrong else bucket_id, runs=reader)

    wrong = bucket_id != str(_PROFILE)
    return factory


def _read_request(expected: PublicPeriod | None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
        subject_ref="a" * 16,
        payload=WorkflowRunReadRequest(profile_id=_PROFILE, run_id="a" * 16, expected_period=expected),
    )


def _context(
    registration, *, action: AccessAction = AccessAction.SUBMIT, admitted: OperationAccessRequest | None = None
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def test_projection_round_trip_and_terminal_boundary() -> None:
    run = _run(detail_period=_PERIOD)
    snapshot = WorkflowRunSnapshot.from_run(run)
    assert WorkflowRunSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert snapshot.to_terminal_details() == run.steps[-1].details
    assert snapshot.obligation is not None
    assert snapshot.obligation.to_obligation() == run.obligation
    assert run.obligation is not None
    assert WorkflowObligationSnapshot.from_obligation(run.obligation) == snapshot.obligation
    projection = WorkflowRunReadProjection(
        profile_id=_PROFILE,
        expected_period=PublicPeriod.from_period(_PERIOD),
        run=snapshot,
    )
    assert WorkflowRunReadProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        WorkflowRunReadProjection(profile_id=_PROFILE, expected_period=PublicPeriod.from_period(_NEXT), run=snapshot)
    with pytest.raises(ValidationError):
        WorkflowRunSnapshot.model_validate(snapshot.model_dump() | {"final_stage": WorkflowStage.LOADING_PROFILE})


@pytest.mark.parametrize("run", [_run(period=None), _run(period=_NEXT), _run(detail_period=_NEXT)])
def test_explicit_period_requires_trustworthy_matching_captured_record(run: WorkflowResult) -> None:
    reader = _Reader(run)
    payload = WorkflowRunReadRequest(
        profile_id=_PROFILE, run_id="a" * 16, expected_period=PublicPeriod.from_period(_PERIOD)
    )
    with pytest.raises((ProfileAccessRefusedError, ValueError)):
        _read_exact_run(payload, WorkflowRunReadPorts(bucket_id=str(_PROFILE), runs=reader))
    assert reader.loads == 1


def test_raw_summary_and_terminal_periods_must_match_obligation() -> None:
    validate_run_period_facts(_run(detail_period=_PERIOD))
    with pytest.raises(ValueError, match="contradictory period"):
        validate_run_period_facts(_run(detail_period=_NEXT))
    with pytest.raises(ValueError, match="contradictory period"):
        validate_run_period_facts(_run(period=None, detail_period=_PERIOD))


def test_finite_and_independent_admission_and_sealed_result() -> None:
    reader = _Reader(_run())
    factory = _factory(reader)
    definition = build_workflow_run_read_definition(factory)
    registration = build_workflow_run_read_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        finite = resolve_operation_access(
            registry=registry,
            request=_read_request(PublicPeriod.from_period(_PERIOD)),
            context=_context(registration),
        )
        assert finite.request.periods == frozenset({_PERIOD})
        assert not finite.request.period_independent and not finite.policy.requires_all_periods
        broad = resolve_operation_access(registry=registry, request=_read_request(None), context=_context(registration))
        assert broad.request.period_independent and not broad.request.periods
        assert broad.policy.requires_all_periods and broad.policy.allow_period_independent
        assert AccessAction.COMMIT not in broad.policy.actions
        reader.run = _run(period=_NEXT)
        sealed = resolve_operation_access(
            registry=registry,
            request=_read_request(PublicPeriod.from_period(_PERIOD)),
            context=_context(registration, action=AccessAction.RESULT, admitted=finite.request),
        )
        assert sealed.request.periods == finite.request.periods
        assert reader.loads == 2
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry,
                request=_read_request(PublicPeriod.from_period(_PERIOD)),
                context=_context(registration, action=AccessAction.START),
            )
        assert refused.value.reason is AccessDenialCode.PERIOD_DENIED


def test_inventory_is_complete_profile_scope_and_rejects_duplicate_runs() -> None:
    reader = _Reader(_run())
    factory = _factory(reader)
    definition = build_workflow_run_list_definition(factory)
    registration = build_workflow_run_list_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=WorkflowRunListRequest(profile_id=_PROFILE),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        resolved = resolve_operation_access(registry=registry, request=request, context=_context(registration))
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.requires_all_periods
    snapshot = WorkflowRunSnapshot.from_run(reader.run)
    with pytest.raises(ValidationError):
        WorkflowRunListProjection(profile_id=_PROFILE, runs=(snapshot, snapshot))

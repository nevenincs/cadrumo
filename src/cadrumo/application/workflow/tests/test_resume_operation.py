"""Recorded resume context has an exact selector, scope, and refusal contract."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.modelo import Modelo
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from ...modelo.calculation_action_ports import CalculationActionPortsFactory
from ...modelo.selectors import ModeloCalculationRevisionSelector
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..abort import WorkflowAbortReason
from ..resume import WorkflowResumeRefusalReason
from ..resume_operation import (
    WORKFLOW_RESUME_AMBIGUITY_CODE,
    WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
    WORKFLOW_RESUME_REFUSAL_CODE,
    WorkflowResumeAddress,
    WorkflowResumeAmbiguity,
    WorkflowResumeCandidateSnapshot,
    WorkflowResumeProjection,
    WorkflowResumeRefusal,
    WorkflowResumeRequest,
    WorkflowResumeResult,
    WorkflowResumeSuccess,
    build_workflow_resume_definition,
    build_workflow_resume_registration,
    project_workflow_resume_result,
)
from ..run_models import WorkflowObligationFacts, WorkflowStage
from ..run_projection import WorkflowObligationSnapshot
from ..run_read_ports import WorkflowRunReadPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 12, 9, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _registration():
    def unused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("policy must not use repositories")

    definition = build_workflow_resume_definition(
        cast(WorkflowRunReadPortsFactory, cast(object, unused)),
        cast(CalculationActionPortsFactory, cast(object, unused)),
    )
    registration = build_workflow_resume_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(payload: WorkflowResumeRequest, *, subject_ref: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or profile_operation_subject(str(payload.profile_id)),
        payload=payload,
    )


def _context(
    registration,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.SUBMIT,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def _obligation() -> WorkflowObligationSnapshot:
    return WorkflowObligationSnapshot.from_obligation(
        WorkflowObligationFacts(
            modelo=Modelo("303"),
            period=_PERIOD,
            opens_on=date(2025, 4, 1),
            closes_on=date(2025, 4, 20),
            status=ObligationStatus.UPCOMING,
        )
    )


def _success() -> WorkflowResumeSuccess:
    return WorkflowResumeSuccess(
        address=WorkflowResumeAddress(
            run_id="a" * 16,
            source="visible_target",
            modelo="303",
            period=PublicPeriod.from_period(_PERIOD),
            filing_year=2025,
            work_unit_id=None,
            short_work_unit_id=None,
            calculation_revision_id=None,
            short_calculation_revision_id=None,
        ),
        obligation=_obligation(),
        aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
    )


def _receipt(
    condition: OperationTerminalCondition,
    *,
    code: str | None = None,
    effect: OperationEffect = OperationEffect.NONE,
    subject_ref: str | None = None,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
            subject_ref=subject_ref or profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=_NOW,
        result_ref="f" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=code,
        refusal_detail_ref="e" * 64 if code is not None else None,
    )


def test_request_rejects_ambiguous_or_incomplete_targets() -> None:
    period = PublicPeriod.from_period(_PERIOD)
    for address in (
        {"target": "a" * 16, "work_unit_id": "b" * 64},
        {"target": "a" * 16, "modelo": "303", "period": period},
        {"modelo": "303"},
        {"period": period},
        {},
    ):
        with pytest.raises(ValidationError):
            WorkflowResumeRequest.model_validate({"profile_id": _PROFILE, **address})
    assert WorkflowResumeRequest(profile_id=_PROFILE, target="a" * 16).target == "a" * 16
    assert WorkflowResumeRequest(profile_id=_PROFILE, modelo="303", period=period).period == period
    with pytest.raises(ValidationError):
        WorkflowResumeRequest(
            profile_id=_PROFILE, target="a" * 16, selector=ModeloCalculationRevisionSelector.LATEST_DRAFT
        )
    with pytest.raises(ValidationError, match="constrains only an exact"):
        WorkflowResumeRequest(
            profile_id=_PROFILE,
            modelo="303",
            period=period,
            expected_period=period,
        )


def test_exact_expected_period_is_finite_without_claiming_a_natural_target() -> None:
    registry, registration = _registration()
    period = PublicPeriod.from_period(_PERIOD)
    constrained = WorkflowResumeRequest(profile_id=_PROFILE, target="a" * 16, expected_period=period)
    assert constrained.period is None and constrained.scope_period() == period
    resolved = resolve_operation_access(
        registry=registry, request=_request(constrained), context=_context(registration)
    )
    assert resolved.request.periods == frozenset({_PERIOD})
    assert not resolved.request.period_independent and not resolved.policy.requires_all_periods
    unconstrained = WorkflowResumeRequest(profile_id=_PROFILE, target="a" * 16)
    assert unconstrained.scope_period() is None
    broad = resolve_operation_access(registry=registry, request=_request(unconstrained), context=_context(registration))
    assert broad.policy.requires_all_periods


def test_exact_address_uses_independent_all_period_scope_and_visible_target_is_finite() -> None:
    registry, registration = _registration()
    exact = _request(WorkflowResumeRequest(profile_id=_PROFILE, target="a" * 16))
    independent = resolve_operation_access(registry=registry, request=exact, context=_context(registration))
    assert independent.request.period_independent and not independent.request.periods
    assert independent.policy.requires_all_periods and independent.policy.allow_period_independent
    assert AccessAction.COMMIT not in independent.policy.actions
    visible = _request(
        WorkflowResumeRequest(profile_id=_PROFILE, modelo="303", period=PublicPeriod.from_period(_PERIOD))
    )
    finite = resolve_operation_access(registry=registry, request=visible, context=_context(registration))
    assert finite.request.periods == frozenset({_PERIOD})
    assert not finite.request.period_independent and not finite.policy.requires_all_periods
    assert AccessAction.COMMIT not in finite.policy.actions
    historical = resolve_operation_access(
        registry=registry,
        request=visible,
        context=_context(registration, action=AccessAction.RESULT, admitted=finite.request),
    )
    assert historical.request.periods == finite.request.periods
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=visible,
            context=_context(registration, action=AccessAction.RESULT, admitted=independent.request),
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_profile_and_subject_are_rejected_before_any_repository_use() -> None:
    registry, registration = _registration()
    payload = WorkflowResumeRequest(profile_id=_PROFILE, target="a" * 16)
    for request, context in (
        (_request(payload), _context(registration, profile_id=_OTHER)),
        (_request(WorkflowResumeRequest(profile_id=_OTHER, target="a" * 16)), _context(registration)),
        (_request(payload, subject_ref="wrong"), _context(registration)),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=context)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_result_schema_is_distinct_and_success_receipt_must_match() -> None:
    private = WorkflowResumeResult(profile_id=_PROFILE, outcome=_success())
    assert WorkflowResumeProjection.model_validate_json(private.model_dump_json()).outcome == private.outcome
    projected = project_workflow_resume_result(private, _receipt(OperationTerminalCondition.SUCCEEDED))
    assert type(projected) is WorkflowResumeProjection
    assert WorkflowResumeProjection.model_validate_json(projected.model_dump_json()) == projected
    for receipt in (
        _receipt(OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.UPDATED),
        _receipt(OperationTerminalCondition.SUCCEEDED, subject_ref="wrong"),
        _receipt(OperationTerminalCondition.REFUSED, code=WORKFLOW_RESUME_REFUSAL_CODE),
    ):
        with pytest.raises(ValueError, match="terminal receipt"):
            project_workflow_resume_result(private, receipt)


def test_refusal_and_ambiguity_require_their_exact_receipt_codes() -> None:
    refused = WorkflowResumeResult(
        profile_id=_PROFILE,
        outcome=WorkflowResumeRefusal(
            run_id="a" * 16,
            reason=WorkflowResumeRefusalReason.TERMINAL_REASON,
            final_stage=WorkflowStage.ABORTED,
            aborted_reason=WorkflowAbortReason.ALREADY_FILED,
        ),
    )
    candidates = tuple(
        WorkflowResumeCandidateSnapshot(
            run_id=run_id,
            modelo="303",
            period=PublicPeriod.from_period(_PERIOD),
            final_stage=WorkflowStage.ABORTED,
            aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
            started_at=_NOW,
            short_work_unit_id=None,
            work_unit_id=None,
        )
        for run_id in ("a" * 16, "b" * 16)
    )
    ambiguous = WorkflowResumeResult(
        profile_id=_PROFILE,
        outcome=WorkflowResumeAmbiguity(modelo="303", period=PublicPeriod.from_period(_PERIOD), candidates=candidates),
    )
    for private, code in ((refused, WORKFLOW_RESUME_REFUSAL_CODE), (ambiguous, WORKFLOW_RESUME_AMBIGUITY_CODE)):
        projected = project_workflow_resume_result(private, _receipt(OperationTerminalCondition.REFUSED, code=code))
        assert type(projected) is WorkflowResumeProjection
        with pytest.raises(ValueError, match="terminal receipt"):
            project_workflow_resume_result(private, _receipt(OperationTerminalCondition.REFUSED, code="WRONG"))
    with pytest.raises(ValidationError, match="crosses filing targets"):
        WorkflowResumeAmbiguity(
            modelo="303",
            period=PublicPeriod.from_period(_PERIOD),
            candidates=(
                candidates[0],
                candidates[1].model_copy(update={"modelo": "130"}),
            ),
        )
    with pytest.raises(ValidationError, match="repeats a run"):
        WorkflowResumeAmbiguity(
            modelo="303", period=PublicPeriod.from_period(_PERIOD), candidates=(candidates[0], candidates[0])
        )
    with pytest.raises(ValidationError, match="differs from its selected target"):
        WorkflowResumeSuccess(
            address=_success().address.model_copy(update={"modelo": "130"}),
            obligation=_obligation(),
            aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        )
    with pytest.raises(ValidationError, match="non-resumable abort reason"):
        WorkflowResumeSuccess(
            address=_success().address,
            obligation=_obligation(),
            aborted_reason=WorkflowAbortReason.ALREADY_FILED,
        )
    with pytest.raises(ValidationError, match="contradicts its terminal facts"):
        WorkflowResumeRefusal(
            run_id="a" * 16,
            reason=WorkflowResumeRefusalReason.NOT_ABORTED,
            final_stage=WorkflowStage.ABORTED,
            aborted_reason=WorkflowAbortReason.ALREADY_FILED,
        )
    with pytest.raises(ValidationError, match="contradictory abort facts"):
        WorkflowResumeCandidateSnapshot.model_validate(candidates[0].model_dump() | {"final_stage": WorkflowStage.DONE})

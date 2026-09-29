"""Registered pipeline access retains whole-profile consent and exact scope."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry, OperationSchemaIdentityV1
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.access_policy import operation_scope_refusal
from ..pipeline_operation import (
    OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
    OverviewPipelineProjection,
    OverviewPipelineRequest,
    OverviewPipelineResult,
    build_overview_pipeline_definition,
    build_overview_pipeline_registration,
    project_overview_pipeline_result,
)
from ..pipeline_projection import PipelineHealthSnapshot, PipelineLedgerSnapshot
from ..pipeline_read_ports import PipelineReadPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2025, "1T")


def _registry():
    def unused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("access policy must not construct private repositories")

    definition = build_overview_pipeline_definition(cast(PipelineReadPortsFactory, cast(object, unused)))
    registration = build_overview_pipeline_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, subject_ref: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or profile_operation_subject(str(profile_id)),
        payload=OverviewPipelineRequest(
            profile_id=profile_id,
            period=PublicPeriod.from_period(_PERIOD),
            output_language=OutputLanguage.ES,
        ),
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
        authority_operation=None,
    )


def _snapshot() -> PipelineHealthSnapshot:
    return PipelineHealthSnapshot(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        ledger=PipelineLedgerSnapshot(
            business_income_total="0.00",
            business_expense_total="0.00",
            business_net_total="0.00",
            total_count=0,
            active_count=0,
            archived_count=0,
            stashed_count=0,
            split_count=0,
            pending_review_count=0,
            reviewed_count=0,
            skipped_count=0,
            checked_transaction_count=0,
            readiness_issue_count=0,
            unconverted_currency_count=0,
            ready=None,
        ),
        modelos=(),
        total_blocking_findings=0,
        total_warning_findings=0,
        ready=False,
    )


def test_selected_period_still_requires_all_periods_and_historical_scope_is_sealed() -> None:
    registry, registration = _registry()
    request = _request()
    resolved = resolve_operation_access(registry=registry, request=request, context=_context(registration))
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions
    finite = AccessScope(
        operations=frozenset({OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID}),
        actions=frozenset({AccessAction.SUBMIT}),
        disclosures=frozenset(),
        periods=frozenset({_PERIOD}),
        allow_period_independent=True,
        allow_delegation=False,
    )
    denied = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=finite)
    assert denied is not None and denied.code is AccessDenialCode.PERIOD_DENIED
    historical = resolve_operation_access(
        registry=registry,
        request=request,
        context=_context(registration, action=AccessAction.RESULT, admitted=resolved.request),
    )
    assert historical.request.period_independent and not historical.request.periods
    assert historical.policy.disclosures


def test_foreign_profile_subject_or_changed_admission_refused_before_private_ports() -> None:
    registry, registration = _registry()
    normal = resolve_operation_access(registry=registry, request=_request(), context=_context(registration))
    for request, context, reason in (
        (_request(profile_id=_OTHER), _context(registration), AccessDenialCode.PROFILE_MISMATCH),
        (_request(), _context(registration, profile_id=_OTHER), AccessDenialCode.PROFILE_MISMATCH),
        (_request(subject_ref="wrong"), _context(registration), AccessDenialCode.PROFILE_MISMATCH),
        (
            _request(),
            _context(
                registration,
                action=AccessAction.RESULT,
                admitted=normal.request.model_copy(
                    update={"period_independent": False, "periods": frozenset({_PERIOD})}
                ),
            ),
            AccessDenialCode.OPERATION_UNAVAILABLE,
        ),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=context)
        assert refused.value.reason is reason


def test_request_private_result_and_public_projection_are_distinct() -> None:
    registry, registration = _registry()
    assert registration.contract.request_schema is not None
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema == OperationSchemaIdentityV1.from_model(
        schema_id="overview.pipeline.result", schema_version=1, model_type=OverviewPipelineProjection
    )
    assert OverviewPipelineProjection is not OverviewPipelineResult
    result = OverviewPipelineResult(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        output_language=OutputLanguage.ES,
        report=_snapshot(),
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 3, 10, tzinfo=UTC),
        result_ref="f" * 64,
    )
    projection = project_overview_pipeline_result(result, receipt)
    assert type(projection) is OverviewPipelineProjection
    assert OverviewPipelineProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ProfileAccessRefusedError) as refused:
        project_overview_pipeline_result(
            result.model_copy(update={"period": PublicPeriod.from_period(Period.from_year_and_code(2025, "2T"))}),
            receipt,
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert registry is not None

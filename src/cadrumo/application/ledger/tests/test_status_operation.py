"""The registered status result is strict and its admission is profile-wide."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...modelo.verification_repository_ports import VerificationRepositoryBundle
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..models import LedgerStatusReport
from ..readiness_query import LedgerReadinessIssueV1
from ..stale_filing_query import LedgerStaleFilingV1
from ..status_operation import (
    LEDGER_STATUS_OPERATION_DEFINITION_ID,
    LedgerStatusProjection,
    LedgerStatusReadinessIssueProjection,
    LedgerStatusRequest,
    build_ledger_status_definition,
    build_ledger_status_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"access resolution attempted to compose ports for {bucket_id} with {operation!r}")


def _unexpected_repositories(bucket_id: str, /, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
    raise AssertionError(f"access resolution attempted to compose repositories for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = build_ledger_status_definition(
        _unexpected_ports,
        _unexpected_repositories,
    )
    registration = build_ledger_status_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, period: PublicPeriod | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=LedgerStatusRequest(profile_id=profile_id, period=period),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1, *, profile_id: UUID = _PROFILE
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_status_registers_exact_strict_request_and_result_models() -> None:
    registry, registration = _registry()

    definition = registry.lookup(LEDGER_STATUS_OPERATION_DEFINITION_ID)
    contract = registration.contract

    assert definition.request_type is LedgerStatusRequest
    assert definition.result_type is LedgerStatusProjection
    assert contract.request_schema.schema_id == "ledger.status.request"
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == "ledger.status.result"
    assert {binding.model_type for binding in registration.schema_bindings} == {
        LedgerStatusRequest,
        LedgerStatusProjection,
    }


def test_status_projection_roundtrips_zero_absence_decimal_issues_and_stale_facts() -> None:
    report = LedgerStatusReport(
        bucket_id=str(_PROFILE),
        business_income_total="0.00",
        business_expense_total="0.00",
        business_net_total="0.00",
        total_count=0,
        active_count=0,
        archived_count=0,
        stashed_count=0,
        pending_review_count=0,
        reviewed_count=0,
        skipped_count=0,
        period=None,
        ready=None,
    )
    issues = (
        LedgerReadinessIssueV1(
            transaction_id="a" * 64,
            reason="missing_tax_fact",
            detail="One optional value is absent.",
            transaction_present=True,
            business_classification="business",
            category_id=None,
            taxable_base=Decimal("0.00"),
            iva_rate=None,
            iva_amount=Decimal("2.50"),
        ),
        LedgerReadinessIssueV1(
            transaction_id="b" * 64,
            reason="transaction_missing",
            detail="The referenced transaction is no longer present.",
            transaction_present=False,
        ),
        LedgerReadinessIssueV1(
            transaction_id="c" * 64,
            reason="precision_preserved",
            detail="The projection preserves decimal coefficient and scale.",
            transaction_present=True,
            taxable_base=Decimal("123456789012345678901234567890.12345678901234567890"),
            iva_rate=Decimal("0.0000000000000000000000000000000000000001"),
            iva_amount=Decimal("0.0000000000000000000000000000000000000000"),
        ),
    )
    stale = (
        LedgerStaleFilingV1(
            modelo="303",
            filing_year=2025,
            period="1T",
            calculation_revision_id="c" * 64,
            work_unit_id="d" * 64,
            changed_count=2,
            removed_count=1,
            covers_current_fact_set=False,
        ),
    )

    projection = LedgerStatusProjection.from_report(report, readiness_issues=issues, stale_filings=stale)
    restored = LedgerStatusProjection.model_validate_json(projection.model_dump_json())

    assert restored.to_report() == report
    assert restored.readiness_issues[0].taxable_base == "0.00"
    assert restored.readiness_issues[0].iva_rate is None
    assert restored.readiness_issues[0].iva_amount == "2.50"
    assert tuple(issue.to_issue() for issue in restored.readiness_issues) == issues
    assert restored.readiness_issues[1].transaction_present is False
    assert restored.readiness_issues[1].taxable_base is None
    assert restored.readiness_issues[2].taxable_base == str(issues[2].taxable_base)
    assert restored.readiness_issues[2].iva_rate == str(issues[2].iva_rate)
    assert restored.readiness_issues[2].iva_amount == str(issues[2].iva_amount)
    assert restored.stale_filings == stale
    assert LedgerStatusReadinessIssueProjection.from_issue(issues[0]).to_issue() == issues[0]


@pytest.mark.parametrize("value", ["not-decimal", "NaN", "Infinity", "-Infinity"])
def test_readiness_issue_projection_rejects_invalid_or_non_finite_decimal_text(value: str) -> None:
    with pytest.raises(ValueError):
        LedgerStatusReadinessIssueProjection(
            transaction_id="a" * 64,
            reason="invalid_decimal",
            detail="Invalid private fact.",
            transaction_present=True,
            taxable_base=value,
        )


@pytest.mark.parametrize(
    "period",
    [None, PublicPeriod.from_period(Period.from_year_and_code(2026, "1T"))],
)
def test_status_access_always_requires_unrestricted_all_periods(period: PublicPeriod | None) -> None:
    registry, registration = _registry()
    request = _request(period=period)
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=_access_context(registration),
    )

    assert request.subject_ref == profile_operation_subject(str(_PROFILE))
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize(
    ("context_profile", "subject_profile"),
    [(_OTHER_PROFILE, _PROFILE), (_PROFILE, _OTHER_PROFILE)],
)
def test_status_access_refuses_a_foreign_profile_or_subject_without_store_reads(
    context_profile: UUID,
    subject_profile: UUID,
) -> None:
    registry, registration = _registry()
    request = _request(profile_id=subject_profile)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=context_profile),
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_status_access_refuses_a_wrong_subject_for_the_exact_profile_without_store_reads() -> None:
    registry, registration = _registry()
    request = _request().model_copy(update={"subject_ref": profile_operation_subject(str(_OTHER_PROFILE))})

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=_PROFILE),
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH

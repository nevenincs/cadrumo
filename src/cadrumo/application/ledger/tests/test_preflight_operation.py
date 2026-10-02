"""Registered ledger preflight binds one period and preserves its canonical report."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..preflight import LedgerPreflightIssue, LedgerPreflightIssueReason, LedgerPreflightReport
from ..preflight_operation import (
    LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
    LedgerPreflightProjection,
    LedgerPreflightRequest,
    build_ledger_preflight_definition,
    build_ledger_preflight_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2026, "1T")


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"access attempted to compose {bucket_id} with {operation!r}")


def _registry():
    definition = build_ledger_preflight_definition(_unexpected_ports)
    registration = build_ledger_preflight_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=LedgerPreflightRequest(profile_id=profile_id, period=PublicPeriod.from_period(_PERIOD)),
    )


def _context(registration, *, profile_id: UUID = _PROFILE) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_preflight_registers_closed_required_period_schemas_without_commit() -> None:
    registry, registration = _registry()
    definition = registry.lookup(LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID)

    assert definition.request_type is LedgerPreflightRequest
    assert definition.result_type is LedgerPreflightProjection
    assert registration.contract.request_schema.schema_id == "ledger.preflight.request"
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "ledger.preflight.result"
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    with pytest.raises(ValueError):
        LedgerPreflightRequest.model_validate({"profile_id": str(_PROFILE)})
    with pytest.raises(ValueError):
        LedgerPreflightRequest.model_validate(
            {"profile_id": str(_PROFILE), "period": PublicPeriod.from_period(_PERIOD), "extra": True}
        )


def test_preflight_access_stays_in_requested_period() -> None:
    registry, registration = _registry()
    resolved = resolve_operation_access(registry=registry, request=_request(), context=_context(registration))

    assert resolved.request.periods == frozenset({_PERIOD})
    assert resolved.request.period_independent is False
    assert resolved.policy.requires_all_periods is False
    assert resolved.policy.allow_period_independent is False
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize("context_profile,subject_profile", [(_OTHER, _PROFILE), (_PROFILE, _OTHER)])
def test_preflight_access_refuses_foreign_profile(context_profile: UUID, subject_profile: UUID) -> None:
    registry, registration = _registry()
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=_request(profile_id=subject_profile),
            context=_context(registration, profile_id=context_profile),
        )
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_preflight_access_refuses_wrong_subject() -> None:
    registry, registration = _registry()
    request = _request().model_copy(update={"subject_ref": profile_operation_subject(str(_OTHER))})
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(registry=registry, request=request, context=_context(registration))
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_encrypted_projection_roundtrips_canonical_issue_and_empty_period() -> None:
    issue = LedgerPreflightIssue(
        transaction_id="b" * 64,
        reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
        detail="The category is missing.",
    )
    report = LedgerPreflightReport(
        bucket_id=str(_PROFILE), period=_PERIOD, checked_transaction_count=1, issues=(issue,)
    )
    projection = LedgerPreflightProjection.from_report(report, profile_id=_PROFILE)
    sealed = LedgerPreflightProjection.model_validate_json(projection.model_dump_json())

    assert sealed.to_report() == report
    assert sealed.issues[0].detail == issue.detail
    with pytest.raises(ValueError):
        LedgerPreflightProjection.model_validate({**projection.model_dump(), "ready": True})
    with pytest.raises(ValueError):
        LedgerPreflightProjection.model_validate({**projection.model_dump(), "bucket_id": str(_OTHER)})

    empty = LedgerPreflightReport(bucket_id=str(_PROFILE), period=_PERIOD, checked_transaction_count=0, issues=())
    assert LedgerPreflightProjection.from_report(empty, profile_id=_PROFILE).to_report() == empty

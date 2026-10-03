"""Registered ledger check preserves canonical facts and whole-profile authority."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.invoice_link import LinkInconsistencyDirection
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.service import LinkInconsistency
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..check_operation import (
    LEDGER_CHECK_OPERATION_DEFINITION_ID,
    LedgerCheckIssueProjection,
    LedgerCheckProjection,
    LedgerCheckRequest,
    build_ledger_check_definition,
    build_ledger_check_registration,
)
from ..check_query import LedgerCheckV1
from ..preflight import LedgerPreflightIssue, LedgerPreflightIssueReason

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"access attempted to compose {bucket_id} with {operation!r}")


def _registry():
    definition = build_ledger_check_definition(_unexpected_ports)
    registration = build_ledger_check_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, period: PublicPeriod | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=LedgerCheckRequest(profile_id=profile_id, period=period),
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


def test_check_registers_strict_versioned_models_without_commit() -> None:
    registry, registration = _registry()
    definition = registry.lookup(LEDGER_CHECK_OPERATION_DEFINITION_ID)

    assert definition.request_type is LedgerCheckRequest
    assert definition.result_type is LedgerCheckProjection
    assert registration.contract.request_schema.schema_id == "ledger.check.request"
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "ledger.check.result"
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert LedgerCheckRequest.model_json_schema().get("additionalProperties") is False
    assert LedgerCheckProjection.model_json_schema().get("additionalProperties") is False


@pytest.mark.parametrize("period", [None, PublicPeriod.from_period(Period.from_year_and_code(2026, "1T"))])
def test_check_access_is_whole_profile_even_with_period(period: PublicPeriod | None) -> None:
    registry, registration = _registry()
    resolved = resolve_operation_access(
        registry=registry, request=_request(period=period), context=_context(registration)
    )

    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize("context_profile,subject_profile", [(_OTHER, _PROFILE), (_PROFILE, _OTHER)])
def test_check_access_refuses_other_profile(context_profile: UUID, subject_profile: UUID) -> None:
    registry, registration = _registry()
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=_request(profile_id=subject_profile),
            context=_context(registration, profile_id=context_profile),
        )
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_check_access_refuses_wrong_subject() -> None:
    registry, registration = _registry()
    request = _request().model_copy(update={"subject_ref": profile_operation_subject(str(_OTHER))})
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(registry=registry, request=request, context=_context(registration))
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_encrypted_projection_roundtrips_global_link_with_selected_period() -> None:
    period = PublicPeriod.from_period(Period.from_year_and_code(2026, "1T"))
    link = LinkInconsistency(
        invoice_id="missing-invoice",
        transaction_id="a" * 64,
        direction=LinkInconsistencyDirection.TRANSACTION_ONLY,
    )
    issue = LedgerPreflightIssue(
        transaction_id="b" * 64,
        reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
        detail="The category is missing.",
    )
    check = LedgerCheckV1(
        bucket_id=str(_PROFILE),
        periods=(str(period.to_period()),),
        checked_transaction_count=0,
        issues=(issue,),
        link_inconsistencies=(link,),
        ready=False,
    )
    projection = LedgerCheckProjection.from_check(check, profile_id=_PROFILE, period=period)
    sealed = LedgerCheckProjection.model_validate_json(projection.model_dump_json())

    assert sealed.to_check() == check
    assert sealed.issues[0].detail == issue.detail
    assert sealed.link_inconsistencies == (link,)
    assert sealed.period == period
    with pytest.raises(ValueError):
        LedgerCheckProjection.model_validate({**projection.model_dump(), "ready": True})
    with pytest.raises(ValueError):
        LedgerCheckProjection.model_validate({**projection.model_dump(), "bucket_id": str(_OTHER)})


def test_issue_wire_refuses_overlong_prose_without_elision() -> None:
    with pytest.raises(ValueError):
        LedgerCheckIssueProjection.model_validate(
            {
                "transaction_id": "b" * 64,
                "reason": LedgerPreflightIssueReason.MISSING_CATEGORY,
                "detail": "x" * 513,
            }
        )

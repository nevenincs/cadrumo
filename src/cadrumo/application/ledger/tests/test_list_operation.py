"""The registered ledger list binds closed filters to exact-profile scope."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..list_operation import (
    LEDGER_LIST_OPERATION_DEFINITION_ID,
    LedgerListProjection,
    LedgerListRequest,
    build_ledger_list_definition,
    build_ledger_list_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2026, "1T")


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    """Fail if schema construction or access admission composes persistence ports."""
    raise AssertionError(f"list schema composed ports for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    """Build the real list contract without composing worker dependencies."""
    definition = build_ledger_list_definition(_unexpected_ports)
    registration = build_ledger_list_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(
    *,
    profile_id: UUID = _PROFILE,
    subject_profile_id: UUID | None = None,
    filters: tuple[str, ...] = (),
) -> OperationRequest[BaseModel]:
    """Build the registered request with an optional wrong subject for refusal cases."""
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerListRequest(profile_id=profile_id, filters=filters),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
    destination_id: UUID | None = None,
    admitted_request: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    """Build a result-disclosure context for the exact registered contract."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=destination_id or uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted_request,
    )


def test_list_registration_binds_exact_strict_models_without_composing_ports() -> None:
    registry, registration = _registry()

    definition = registry.lookup(LEDGER_LIST_OPERATION_DEFINITION_ID)
    contract = registration.contract

    assert definition.request_type is LedgerListRequest
    assert definition.result_type is LedgerListProjection
    assert contract.request_schema.schema_id == "ledger.list.request"
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == "ledger.list.result"
    assert {binding.model_type for binding in registration.schema_bindings} == {
        LedgerListRequest,
        LedgerListProjection,
    }
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


@pytest.mark.parametrize("raw_filter", ["private-filter-sentinel", "unknown=private-filter-sentinel"])
def test_list_request_refuses_malformed_filters_without_echoing_private_input(raw_filter: str) -> None:
    with pytest.raises(ValidationError) as error:
        LedgerListRequest(profile_id=_PROFILE, filters=(raw_filter,))

    assert "invalid ledger selection filters" in str(error.value)
    assert raw_filter not in str(error.value)
    assert "private-filter-sentinel" not in str(error.value)


@pytest.mark.parametrize("limit", [0, -1])
def test_list_request_rejects_nonpositive_limits(limit: int) -> None:
    with pytest.raises(ValidationError):
        LedgerListRequest(profile_id=_PROFILE, limit=limit)


@pytest.mark.parametrize("limit", [0, -1])
def test_list_projection_rejects_nonpositive_limits(limit: int) -> None:
    with pytest.raises(ValidationError):
        LedgerListProjection(
            profile_id=_PROFILE,
            rows=(),
            total=0,
            truncated=False,
            offset=0,
            limit=limit,
            by_group=False,
        )


@pytest.mark.parametrize(
    ("filters", "expected_period"),
    [
        ((), None),
        (("period=1T", "year=2026"), _PERIOD),
    ],
)
def test_list_access_uses_period_derived_from_canonical_filter_clauses(
    filters: tuple[str, ...], expected_period: Period | None
) -> None:
    registry, registration = _registry()
    request = _request(filters=filters)
    context = _access_context(registration)

    assert isinstance(request.payload, LedgerListRequest)
    assert request.payload.filter_spec().period == expected_period
    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    expected_scope = frozenset({expected_period}) if expected_period is not None else frozenset()
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == expected_scope
    assert resolved.request.period_independent is (expected_period is None)
    assert resolved.policy.requires_all_periods is (expected_period is None)
    assert resolved.policy.allow_period_independent is (expected_period is None)
    assert AccessAction.COMMIT not in resolved.policy.actions
    assert registration.contract.result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == registration.contract.result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        (_OTHER_PROFILE, _PROFILE, _PROFILE),
        (_PROFILE, _PROFILE, _OTHER_PROFILE),
    ],
)
def test_list_access_refuses_foreign_profile_or_subject(
    context_profile: UUID,
    payload_profile: UUID,
    subject_profile: UUID,
) -> None:
    registry, registration = _registry()
    request = _request(profile_id=payload_profile, subject_profile_id=subject_profile)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=context_profile),
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_list_access_refuses_sealed_admission_with_a_tampered_period_scope() -> None:
    registry, registration = _registry()
    request = _request(filters=("period=1T", "year=2026"))
    destination_id = uuid4()
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({Period.from_year_and_code(2026, "2T")}),
        period_independent=False,
        destination_id=destination_id,
    )

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, destination_id=destination_id, admitted_request=admitted),
        )

    assert error.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

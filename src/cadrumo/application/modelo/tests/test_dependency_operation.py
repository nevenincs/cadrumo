"""Dependency admission covers every published source period before private reads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.operation_access_policy import operation_scope_refusal
from ..dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
    ModeloDependencyResult,
    ModeloDependencySnapshot,
    build_modelo_dependency_definition,
    build_modelo_dependency_registration,
    dependency_access_periods,
    project_modelo_dependency_result,
)
from ..dependency_read_ports import DependencyReadPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_TARGET = Period.from_year_and_code(2025, "0A")


def _registry():
    def unused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("access policy must not construct private repositories")

    definition = build_modelo_dependency_definition(cast(DependencyReadPortsFactory, cast(object, unused)))
    registration = build_modelo_dependency_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration


def _request(*, profile_id: UUID = _PROFILE, period: Period | None = _TARGET) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloDependencyRequest(
            profile_id=profile_id,
            filing_year=2025,
            modelo="100" if period is not None else None,
            period=PublicPeriod.from_period(period) if period is not None else None,
        ),
    )


def _context(
    registration,
    authority_operation: PinnedAuthorityOperation | None,
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
        authority_operation=authority_operation,
    )


def test_period_request_covers_published_source_union_and_target_only_scope_denies(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry, registration = _registry()
    request = _request()
    payload = request.payload
    assert isinstance(payload, ModeloDependencyRequest)
    expected = dependency_access_periods(payload, authority_operation)
    assert _TARGET in expected
    assert any(item != _TARGET for item in expected)
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=_context(registration, authority_operation),
    )
    assert resolved.request.periods == expected
    assert not resolved.request.period_independent and not resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions
    target_only = AccessScope(
        operations=frozenset({MODELO_DEPENDENCY_OPERATION_DEFINITION_ID}),
        actions=frozenset({AccessAction.SUBMIT}),
        disclosures=frozenset(),
        periods=frozenset({_TARGET}),
        allow_period_independent=False,
        allow_delegation=False,
    )
    denied = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=target_only)
    assert denied is not None and denied.code is AccessDenialCode.PERIOD_DENIED


def test_inventory_is_independent_and_historical_result_keeps_admitted_source_scope(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry, registration = _registry()
    inventory = resolve_operation_access(
        registry=registry, request=_request(period=None), context=_context(registration, authority_operation)
    )
    assert inventory.request.period_independent and not inventory.request.periods
    assert inventory.policy.requires_all_periods
    finite = resolve_operation_access(
        registry=registry, request=_request(), context=_context(registration, authority_operation)
    )
    historical = resolve_operation_access(
        registry=registry,
        request=_request(),
        context=_context(registration, None, action=AccessAction.RESULT, admitted=finite.request),
    )
    assert historical.request.periods == finite.request.periods
    assert historical.policy.disclosures
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(),
            context=_context(registration, None, action=AccessAction.RESULT, admitted=inventory.request),
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_exact_profile_and_subject_refused_before_authority_or_private_ports() -> None:
    registry, registration = _registry()
    for request, context in (
        (_request(profile_id=_OTHER), _context(registration, None)),
        (_request(), _context(registration, None, profile_id=_OTHER)),
        (
            OperationRequest[BaseModel](
                definition_id=MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
                subject_ref="wrong",
                payload=_request().payload,
            ),
            _context(registration, None),
        ),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=context)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_request_snapshot_and_explicit_public_projection_contract() -> None:
    with pytest.raises(ValidationError):
        ModeloDependencyRequest(
            profile_id=_PROFILE,
            filing_year=2025,
            modelo=None,
            period=PublicPeriod.from_period(_TARGET),
        )
    private = ModeloDependencyResult(
        profile_id=_PROFILE,
        snapshot=ModeloDependencySnapshot(
            filing_year=2025,
            modelo_filter=None,
            period_filter=None,
            target_modelos=(),
            source_modelos=(),
            items=(),
            clean_state=None,
        ),
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 3, 10, tzinfo=UTC),
        result_ref="f" * 64,
    )
    public = project_modelo_dependency_result(private, receipt)
    assert type(public) is ModeloDependencyProjection
    assert ModeloDependencyProjection.model_validate_json(public.model_dump_json()) == public
    with pytest.raises(ValueError, match="terminal receipt"):
        project_modelo_dependency_result(private, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))

"""The registered censal REVIEW resolves only its exact profile and disclosures."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.application.user_profile.operation_access_policy import operation_scope_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _registry() -> OperationRegistry:
    definition = build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=build_operator_scope_ports(),
        censal_fetch_port=fetch_censal_datos,
        provider_preflight=lambda _profile_id, _operation: None,
    )
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_censal_operation_registration(definition),),
    )


def _request(profile_id: UUID) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=str(profile_id),
        payload=CensalOperationRequest(
            baseline=CensalProfileBaseline(profile_id=str(profile_id), record_revision=3, content_digest="a" * 64),
            field_intents=tuple(
                CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.PRESERVE)
                for path in CENSAL_ADOPTABLE_PATHS
            ),
        ),
    )


def _context(registry: OperationRegistry, profile_id: UUID, action: AccessAction) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(CENSAL_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )


def test_registered_censal_review_resolves_exact_profile_and_policy_axes() -> None:
    registry = _registry()
    profile_id = uuid4()
    request = _request(profile_id)
    for action in AccessAction:
        context = _context(registry, profile_id, action)
        resolved = resolve_operation_access(registry=registry, request=request, context=context)
        assert resolved.request.profile_id == profile_id
        assert resolved.request.period_independent and not resolved.request.periods
        assert resolved.policy.allow_period_independent and resolved.policy.periods == frozenset()
        assert resolved.policy.published_authority is context.published_authority
        assert resolved.policy.backend is Availability.AVAILABLE
        # Provider readiness is the bound worker's preflight; a START policy
        # demanding it is refused ``provider_required`` before the worker runs.
        assert resolved.policy.provider is Availability.NOT_REQUIRED
        assert resolved.policy.transaction_authority_required is False
        if action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            expected_projection = OPERATION_OBSERVATION_PROJECTION_ID
            expected_category = DisclosureCategory.OPERATION_METADATA
        elif action in {AccessAction.REVIEW, AccessAction.RESPOND}:
            assert context.contract.review_projection_schema is not None
            expected_projection = context.contract.review_projection_schema.schema_id
            expected_category = DisclosureCategory.PROFILE_VALUES
        elif action is AccessAction.RESULT:
            assert context.contract.result_schema is not None
            expected_projection = context.contract.result_schema.schema_id
            expected_category = DisclosureCategory.PROFILE_VALUES
        else:
            assert resolved.policy.disclosures == frozenset()
            continue
        assert len(resolved.policy.disclosures) == 1
        disclosure = next(iter(resolved.policy.disclosures))
        assert disclosure.destination_id == context.destination_id
        assert disclosure.projection_id == expected_projection
        assert disclosure.category is expected_category


def test_censal_review_refuses_mismatched_profile_and_narrow_scope() -> None:
    registry = _registry()
    profile_id = uuid4()
    request = _request(profile_id)
    context = _context(registry, profile_id, AccessAction.REVIEW)
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    scope = AccessScope(
        operations=frozenset({CENSAL_OPERATION_DEFINITION_ID}),
        actions=frozenset(AccessAction),
        disclosures=resolved.policy.disclosures,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    assert operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=scope) is None
    response = resolve_operation_access(
        registry=registry, request=request, context=replace(context, action=AccessAction.RESPOND)
    )
    assert operation_scope_refusal(request=response.request, policy=response.policy, scope=scope) is None
    unavailable = resolve_operation_access(
        registry=registry,
        request=request,
        context=replace(context, published_authority=Availability.UNAVAILABLE),
    )
    assert unavailable.policy.published_authority is Availability.UNAVAILABLE
    disclosure = next(iter(resolved.policy.disclosures))
    for narrowed, code in (
        (scope.model_copy(update={"disclosures": frozenset()}), AccessDenialCode.DISCLOSURE_DENIED),
        (
            scope.model_copy(
                update={
                    "disclosures": frozenset(
                        {
                            DisclosurePermission(
                                destination_id=disclosure.destination_id,
                                projection_id=disclosure.projection_id,
                                category=DisclosureCategory.TAX_VALUES,
                            )
                        }
                    )
                }
            ),
            AccessDenialCode.DISCLOSURE_DENIED,
        ),
        (scope.model_copy(update={"allow_period_independent": False}), AccessDenialCode.PERIOD_DENIED),
        (scope.model_copy(update={"actions": frozenset({AccessAction.SUBMIT})}), AccessDenialCode.OPERATION_DENIED),
    ):
        refusal = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=narrowed)
        assert refusal is not None and refusal.code is code

    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        resolve_operation_access(registry=registry, request=request, context=replace(context, profile_id=uuid4()))
    assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH
    wrong_subject = request.model_copy(update={"subject_ref": f"profile:{profile_id}"})
    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        resolve_operation_access(registry=registry, request=wrong_subject, context=context)
    assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH

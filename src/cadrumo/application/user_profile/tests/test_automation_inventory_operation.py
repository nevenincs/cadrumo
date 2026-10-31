"""Human automation projections require exact-profile registered authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.tests._access_authority_support import build_access_authority, new_access_binding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationReceiptProjection,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AUTOMATION_RENEW_OPERATION_DEFINITION_ID,
    AUTOMATION_REQUEST_OPERATION_DEFINITION_ID,
    AUTOMATION_ROTATE_OPERATION_DEFINITION_ID,
    AUTOMATION_SCOPE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
    resolve_automation_human_access,
)
from cadrumo.core.operations import profile_operation_subject
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    Availability,
    DisclosureCategory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _registry() -> OperationRegistry:
    definitions = build_automation_operation_definitions()
    registrations = build_automation_operation_registrations(definitions)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )


def test_inventory_and_reviewed_decisions_expose_typed_human_cli_and_tui_results() -> None:
    registry = _registry()
    for definition in registry.definitions:
        contract = registry.lookup_public_contract(definition.definition_id)
        result_types = {
            AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID: AutomationInventoryProjection,
            AUTOMATION_APPROVE_OPERATION_DEFINITION_ID: AutomationReceiptProjection,
            AUTOMATION_DECLINE_OPERATION_DEFINITION_ID: AutomationReceiptProjection,
        }
        if definition.definition_id in result_types:
            assert contract.result_schema is not None
            binding = registry.lookup_public_registration(definition.definition_id).schema_bindings
            assert any(
                item.identity == contract.result_schema and item.model_type is result_types[definition.definition_id]
                for item in binding
            )
        else:
            assert contract.result_schema is None


@pytest.mark.parametrize(
    "definition_id",
    (
        AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
        AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
        AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    ),
)
def test_resolver_pins_profile_human_policy_and_disclosure_category(definition_id: str) -> None:
    registry = _registry()
    profile_id, destination_id = uuid4(), uuid4()
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4(), review_digest="a" * 64),
    )
    contract = registry.lookup_public_contract(request.definition_id)
    assert contract.result_schema is not None
    for action, category in (
        (AccessAction.SUBMIT, None),
        (AccessAction.OBSERVE, DisclosureCategory.OPERATION_METADATA),
        (AccessAction.RESULT, DisclosureCategory.PROFILE_VALUES),
    ):
        context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=destination_id,
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        )
        resolved = resolve_operation_access(registry=registry, request=request, context=context)
        assert resolved.policy.requires_human
        assert resolved.request.profile_id == profile_id
        assert resolved.request.period_independent
        assert {item.category for item in resolved.policy.disclosures} == (set() if category is None else {category})
    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=uuid4(),
                destination_id=destination_id,
                action=AccessAction.RESULT,
                frontend=OperationFrontendProjection.CLI,
                contract=contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
    assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(
    "definition_id",
    (
        AUTOMATION_REQUEST_OPERATION_DEFINITION_ID,
        AUTOMATION_ROTATE_OPERATION_DEFINITION_ID,
        AUTOMATION_RENEW_OPERATION_DEFINITION_ID,
        AUTOMATION_SCOPE_OPERATION_DEFINITION_ID,
    ),
)
def test_a_proposal_is_admitted_alike_on_every_frontend_for_the_exact_profile_and_releases_no_result(
    definition_id: str,
) -> None:
    registry = _registry()
    profile_id, destination_id = uuid4(), uuid4()
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
    )
    contract = registry.lookup_public_contract(definition_id)

    def context(
        frontend: OperationFrontendProjection, action: AccessAction, *, foreign: bool = False
    ) -> OperationAccessContext:
        return OperationAccessContext(
            profile_id=uuid4() if foreign else profile_id,
            destination_id=destination_id,
            action=action,
            frontend=frontend,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        )

    assert contract.ephemeral_secret_required and contract.result_schema is None
    for action, categories in (
        (AccessAction.SUBMIT, set[DisclosureCategory]()),
        (AccessAction.START, set[DisclosureCategory]()),
        (AccessAction.COMMIT, set[DisclosureCategory]()),
        (AccessAction.OBSERVE, {DisclosureCategory.OPERATION_METADATA}),
    ):
        resolved = {
            frontend: resolve_operation_access(registry=registry, request=request, context=context(frontend, action))
            for frontend in OperationFrontendProjection
        }
        for frontend, access in resolved.items():
            assert access.request.frontend is frontend and access.request.profile_id == profile_id
            assert access.request.period_independent and not access.policy.requires_human
            assert access.policy == resolved[OperationFrontendProjection.CLI].policy
            assert {item.category for item in access.policy.disclosures} == categories
    for frontend in OperationFrontendProjection:
        with pytest.raises(ProfileAccessRefusedError) as unreadable:
            resolve_operation_access(registry=registry, request=request, context=context(frontend, AccessAction.RESULT))
        assert unreadable.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
        with pytest.raises(ProfileAccessRefusedError) as mismatch:
            resolve_operation_access(
                registry=registry, request=request, context=context(frontend, AccessAction.SUBMIT, foreign=True)
            )
        assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(
    "definition_id", (AUTOMATION_APPROVE_OPERATION_DEFINITION_ID, AUTOMATION_DECLINE_OPERATION_DEFINITION_ID)
)
def test_reviewed_decisions_require_the_digest_before_authorization(definition_id: str) -> None:
    registry = _registry()
    profile_id = uuid4()
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
    )
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=profile_id,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registry.lookup_public_contract(definition_id),
                published_authority=Availability.AVAILABLE,
            ),
        )
    assert refusal.value.reason is AccessDenialCode.OPERATION_DENIED


def test_result_without_a_registered_result_schema_is_unavailable() -> None:
    registry = _registry()
    profile_id = uuid4()
    definition_id = AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
    )
    contract = registry.lookup_public_contract(definition_id).model_copy(update={"result_schema": None})
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_automation_human_access(
            request,
            OperationAccessContext(
                profile_id=profile_id,
                destination_id=uuid4(),
                action=AccessAction.RESULT,
                frontend=OperationFrontendProjection.CLI,
                contract=contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
    assert refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_live_api_key_cannot_decline_a_reviewed_request() -> None:
    registry = _registry()
    profile_id, destination_id = uuid4(), uuid4()
    definition_id = AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4(), review_digest="a" * 64),
    )
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=OperationAccessContext(
            profile_id=profile_id,
            destination_id=destination_id,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registry.lookup_public_contract(definition_id),
            published_authority=Availability.AVAILABLE,
        ),
    )
    current = datetime(2026, 9, 27, 12, tzinfo=UTC)
    scope = AccessScope(
        operations=frozenset({definition_id}),
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
    )
    authority = build_access_authority(
        binding=new_access_binding(profile_id),
        now=current,
        grant_scope=scope,
        session_lease=timedelta(minutes=5),
        allow_os_lock=True,
        login_id="login-a",
    )
    assert authority.evaluate(registry=registry, request=resolved.request, policy=resolved.policy) == AccessDenied(
        code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
    )

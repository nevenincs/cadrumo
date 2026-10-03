"""The registered bundle export has one exact profile and disclosure scope."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_policy import operation_scope_refusal
from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from cadrumo.application.user_profile.operations import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    USER_PROFILE_OPERATION_DEFINITIONS,
    ProfileBundleExportOperationProjection,
    ProfileBundleExportOperationRequest,
    build_user_profile_operation_registrations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )


def test_runtime_bundle_export_refuses_relative_destination() -> None:
    with pytest.raises(ValidationError, match="absolute destination"):
        ProfileBundleExportOperationRequest(
            profile_id=uuid4(),
            destination=Path("private.bundle"),
            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        )


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.RESULT, AccessAction.OBSERVE])
def test_bundle_export_resolution_requires_exact_profile_and_scoped_projection(
    action: AccessAction, tmp_path: Path
) -> None:
    registry = _registry()
    profile, destination = uuid4(), uuid4()
    contract = registry.lookup_public_contract(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID)
    assert contract.result_schema is not None
    registration = registry.lookup_public_registration(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID)
    assert any(binding.model_type is ProfileBundleExportOperationProjection for binding in registration.schema_bindings)
    assert registration.result_projector is not None
    context = OperationAccessContext(
        profile_id=profile,
        destination_id=destination,
        action=action,
        frontend=OperationFrontendProjection.TUI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )
    request = OperationRequest(
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile}",
        payload=ProfileBundleExportOperationRequest(
            profile_id=profile,
            destination=tmp_path / "private.bundle",
            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        ),
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.request.profile_id == profile
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.published_authority is Availability.AVAILABLE
    assert resolved.policy.provider is Availability.NOT_REQUIRED
    if action is AccessAction.RESULT:
        permission = next(iter(resolved.policy.disclosures))
        assert permission.destination_id == destination
        assert permission.projection_id == contract.result_schema.schema_id
        assert permission.category is DisclosureCategory.PROFILE_VALUES
    elif action is AccessAction.OBSERVE:
        assert {permission.category for permission in resolved.policy.disclosures} == {
            DisclosureCategory.OPERATION_METADATA
        }
    else:
        assert not resolved.policy.disclosures

    allowed_scope = AccessScope(
        operations=frozenset({PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID}),
        actions=frozenset({action}),
        disclosures=resolved.policy.disclosures,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    assert operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=allowed_scope) is None
    if resolved.policy.disclosures:
        narrow = allowed_scope.model_copy(update={"disclosures": frozenset()})
        denied = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=narrow)
        assert denied is not None and denied.code is AccessDenialCode.DISCLOSURE_DENIED
    denied_action = operation_scope_refusal(
        request=resolved.request,
        policy=resolved.policy,
        scope=allowed_scope.model_copy(update={"actions": frozenset()}),
    )
    assert denied_action is not None and denied_action.code is AccessDenialCode.OPERATION_DENIED

    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        resolve_operation_access(registry=registry, request=request, context=replace(context, profile_id=uuid4()))
    assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH
    with pytest.raises(ProfileAccessRefusedError) as wrong_subject:
        resolve_operation_access(
            registry=registry,
            request=request.model_copy(update={"subject_ref": f"profile:{uuid4()}"}),
            context=context,
        )
    assert wrong_subject.value.reason is AccessDenialCode.PROFILE_MISMATCH

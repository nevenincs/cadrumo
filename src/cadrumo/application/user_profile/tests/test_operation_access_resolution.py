"""Operation-owned coordinates cannot be replaced by frontend policy claims."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
    ProfileLogoutOperationRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("wrong_coordinate", [None, "profile", "subject", "definition", "contract", "payload"])
def test_profile_owner_resolves_only_exact_registered_work(wrong_coordinate: str | None) -> None:
    registry = OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )
    profile = uuid4()
    context = OperationAccessContext(
        profile_id=profile,
        destination_id=uuid4(),
        action=AccessAction.COMMIT,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )
    request = OperationRequest(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{uuid4() if wrong_coordinate == 'subject' else profile}",
        payload=ProfileLogoutOperationRequest(profile_id=profile)
        if wrong_coordinate == "payload"
        else ProfileFieldMutationOperationRequest(
            profile_id=profile,
            expected_revision=1,
            expected_content_digest="0" * 64,
            path="preferences.output_language",
            value="es",
        ),
    )
    if wrong_coordinate == "profile":
        context = replace(context, profile_id=uuid4())
    elif wrong_coordinate in {"definition", "contract"}:
        context = replace(
            context,
            contract=context.contract.model_copy(update={"definition_id": PROFILE_LOGOUT_OPERATION_DEFINITION_ID}),
        )
        if wrong_coordinate == "definition":
            request = OperationRequest(
                definition_id=PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
                subject_ref=request.subject_ref,
                payload=ProfileLogoutOperationRequest(profile_id=profile),
            )
    if wrong_coordinate is not None:
        with pytest.raises(ProfileAccessRefusedError) as error:
            resolve_operation_access(registry=registry, request=request, context=context)
        assert error.value.reason in {AccessDenialCode.PROFILE_MISMATCH, AccessDenialCode.OPERATION_UNAVAILABLE}
        return
    resolution = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolution.request.profile_id == profile
    assert resolution.request.period_independent and not resolution.request.periods
    assert resolution.request.destination_id == context.destination_id
    assert resolution.policy.definition_contract_digest == context.contract.definition_contract_digest
    assert AccessAction.COMMIT in resolution.policy.actions
    assert AccessAction.RESULT in resolution.policy.actions
    assert AccessAction.REVIEW not in resolution.policy.actions

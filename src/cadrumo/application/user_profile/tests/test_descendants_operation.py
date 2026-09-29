"""Family replacement cannot borrow filing scope or another profile's authority."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow
from cadrumo.application.user_profile.operations import (
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    USER_PROFILE_OPERATION_DEFINITIONS,
    ProfileDescendantsOperationRequest,
    build_user_profile_operation_registrations,
)
from cadrumo.core.operations import profile_operation_subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.mark.parametrize("action", [AccessAction.COMMIT, AccessAction.RESULT])
def test_family_replacement_requires_profile_wide_authority(action: AccessAction) -> None:
    registry = OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )
    profile_id, destination = uuid4(), uuid4()
    payload = ProfileDescendantsOperationRequest(
        profile_id=profile_id, expected_revision=1, expected_content_digest="0" * 64, descendants=()
    )
    request = OperationRequest(
        definition_id=PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=destination,
        action=action,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.allow_period_independent
    if action is AccessAction.RESULT:
        assert len(resolved.policy.disclosures) == 1
        disclosure = next(iter(resolved.policy.disclosures))
        assert disclosure.destination_id == destination
        assert disclosure.category is DisclosureCategory.PROFILE_VALUES
    with pytest.raises(ProfileAccessRefusedError) as failure:
        resolve_operation_access(
            registry=registry,
            request=request.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))}),
            context=context,
        )
    assert failure.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_family_omission_cannot_clear_rows_and_payload_repr_hides_personal_values() -> None:
    profile_id = uuid4()
    with pytest.raises(ValidationError):
        ProfileDescendantsOperationRequest.model_validate(
            {"profile_id": profile_id, "expected_revision": 1, "expected_content_digest": "0" * 64}
        )
    descendant = ProfileDescendantRow(
        facts=(
            ProfileDescendantFact(field_key="birth_date", value="2020-03-04"),
            ProfileDescendantFact(field_key="nif", value="12345678Z"),
        )
    )
    payload = ProfileDescendantsOperationRequest(
        profile_id=profile_id, expected_revision=1, expected_content_digest="0" * 64, descendants=(descendant,)
    )
    assert "12345678Z" not in repr(payload)
    restored = ProfileDescendantsOperationRequest.model_validate_json(payload.model_dump_json())
    assert restored.descendants == (descendant,)

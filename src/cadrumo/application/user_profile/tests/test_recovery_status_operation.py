"""Recovery enrollment inspection cannot expand its profile or output authority."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..access_contracts import AccessAction, AccessDenialCode, Availability, DisclosureCategory
from ..access_errors import ProfileAccessRefusedError
from ..recovery_status_operation import (
    RECOVERY_STATUS_OPERATION_DEFINITION_ID,
    RecoveryStatusRequest,
    build_recovery_status_definition,
    build_recovery_status_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_recovery_status_requires_exact_profile_and_independent_result_disclosure() -> None:
    definition = build_recovery_status_definition()
    registry = OperationRegistry(
        definitions=(definition,), public_registrations=(build_recovery_status_registration(definition),)
    )
    profile_id = uuid4()
    request = OperationRequest[BaseModel](
        definition_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=RecoveryStatusRequest(profile_id=profile_id),
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(definition.definition_id),
        published_authority=Availability.AVAILABLE,
    )
    access = resolve_operation_access(registry=registry, request=request, context=context)
    assert access.request.period_independent
    assert access.policy.provider is Availability.NOT_REQUIRED
    assert {(item.destination_id, item.projection_id, item.category) for item in access.policy.disclosures} == {
        (context.destination_id, RECOVERY_STATUS_OPERATION_DEFINITION_ID + ".result", DisclosureCategory.PROFILE_VALUES)
    }
    for changed, reason in (
        (replace(context, profile_id=uuid4()), AccessDenialCode.PROFILE_MISMATCH),
        (replace(context, action=AccessAction.COMMIT), AccessDenialCode.OPERATION_DENIED),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=changed)
        assert refused.value.reason is reason

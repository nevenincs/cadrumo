"""A census preview may persist authentication without adopting profile facts."""

from uuid import uuid4

import pytest

from cadrumo.application.operations.access_resolution import OperationAccessContext
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessAction, Availability, OperationAccessRequest
from cadrumo.application.user_profile.censal_operation import CensalProfileBaseline
from cadrumo.application.user_profile.censal_preview_operation import (
    CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
    CensalPreviewOperationRequest,
    resolve_censal_preview_operation_access,
)
from cadrumo.core.operations import profile_operation_subject
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
def test_preview_admits_guarded_session_publication(frontend: OperationFrontendProjection) -> None:
    profile_id, destination_id = uuid4(), uuid4()
    definition_id = CENSAL_PREVIEW_OPERATION_DEFINITION_ID
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=CensalPreviewOperationRequest(
            baseline=CensalProfileBaseline(profile_id=str(profile_id), record_revision=1, content_digest="a" * 64)
        ),
    )
    admitted = OperationAccessRequest(
        profile_id=profile_id,
        definition_id=definition_id,
        action=AccessAction.SUBMIT,
        frontend=frontend,
        periods=frozenset(),
        period_independent=True,
        destination_id=destination_id,
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=destination_id,
        action=AccessAction.COMMIT,
        frontend=frontend,
        contract=build_production_operation_registry().lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )
    resolved = resolve_censal_preview_operation_access(request, context)
    assert AccessAction.COMMIT in resolved.policy.actions
    assert resolved.request.profile_id == profile_id
    assert resolved.request.definition_id == definition_id
    assert resolved.request.period_independent

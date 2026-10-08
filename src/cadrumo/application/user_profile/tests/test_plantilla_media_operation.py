"""Workforce-year commands preserve precision and require profile-wide authority."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessAction, Availability, DisclosureCategory
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaSet,
)
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("action", [AccessAction.COMMIT, AccessAction.RESULT])
def test_calendar_year_never_claims_filing_period_authority(action: AccessAction) -> None:
    """The stored year identifies a profile fact, not a filing scope."""
    registry = OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )
    profile_id, destination = uuid4(), uuid4()
    payload = ProfilePlantillaMediaOperationRequest(
        profile_id=profile_id,
        expected_revision=1,
        expected_content_digest="0" * 64,
        year=2025,
        change=ProfilePlantillaMediaSet(average_workforce="12.50", state=PlantillaMediaState.OBSERVED),
    )
    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest(
            definition_id=PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=payload,
        ),
        context=OperationAccessContext(
            profile_id=profile_id,
            destination_id=destination,
            action=action,
            frontend=OperationFrontendProjection.MCP,
            contract=registry.lookup_public_contract(PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID),
            published_authority=Availability.AVAILABLE,
        ),
    )
    assert resolved.request.period_independent
    assert not resolved.request.periods
    assert resolved.policy.allow_period_independent
    assert resolved.request.profile_id == profile_id
    if action is AccessAction.RESULT:
        assert len(resolved.policy.disclosures) == 1
        disclosure = next(iter(resolved.policy.disclosures))
        assert disclosure.destination_id == destination
        assert disclosure.category is DisclosureCategory.PROFILE_VALUES


def test_decimal_text_round_trip_preserves_precision_for_canonical_validation() -> None:
    """Transport cannot round an invalid third decimal place into an admissible value."""
    change = ProfilePlantillaMediaSet(average_workforce="12.500", state=PlantillaMediaState.COMMITTED)
    restored = ProfilePlantillaMediaSet.model_validate_json(change.model_dump_json())
    assert restored.average_workforce == "12.500"
    assert Decimal(restored.average_workforce).as_tuple().exponent == -3
    assert restored.average_workforce not in repr(change)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "workforce"])
def test_non_decimal_workforce_refuses_before_execution(value: str) -> None:
    with pytest.raises(ValidationError):
        ProfilePlantillaMediaSet(average_workforce=value, state=PlantillaMediaState.OBSERVED)

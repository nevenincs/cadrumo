"""Agent timeline exposes only vetted event metadata under exact authority."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..history_ports import ModeloHistoryPorts
from ..history_timeline_operation import (
    MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
    ModeloHistoryTimelineProjection,
    ModeloHistoryTimelineRequest,
    ModeloTimelineEvent,
    build_modelo_history_timeline_definition,
    build_modelo_history_timeline_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _registry() -> OperationRegistry:
    def unopened(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloHistoryPorts:
        raise AssertionError("timeline access must not open a private catalogue")

    definition = build_modelo_history_timeline_definition(unopened)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_modelo_history_timeline_registration(definition),)
    )


def _request(*, year: int | None = None, period: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloHistoryTimelineRequest(profile_id=_PROFILE, modelo="130", year=year, period=period),
    )


def test_timeline_mcp_result_disclosure_and_full_period_scope(authority_operation: PinnedAuthorityOperation) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID)
    assert contract.permitted_frontends == frozenset({OperationFrontendProjection.MCP})
    assert contract.result_schema is not None
    destination = uuid4()
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=destination,
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.MCP,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    selected = resolve_operation_access(registry=registry, request=_request(year=2025, period="1T"), context=context)
    assert selected.request.periods == frozenset({Period.from_year_and_code(2025, "1T")})
    assert not selected.policy.requires_all_periods
    assert AccessAction.COMMIT not in selected.policy.actions
    assert selected.policy.disclosures == frozenset(
        {
            DisclosurePermission(
                destination_id=destination,
                projection_id=contract.result_schema.schema_id,
                category=DisclosureCategory.OPERATION_METADATA,
            )
        }
    )
    full = resolve_operation_access(registry=registry, request=_request(year=2025), context=context)
    assert full.request.period_independent and full.policy.requires_all_periods
    assert full.request.periods == frozenset()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=_request(), context=replace(context, profile_id=_OTHER))
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_timeline_omits_export_path_and_free_text_even_if_source_event_contains_them() -> None:
    occurred_at = datetime(2025, 5, 1, 12, 34, 56, 123456, tzinfo=UTC)
    payload = {
        "modelo": "130",
        "filing_year": "2025",
        "period": "1T",
        "output_path": "C:/private/tax-export.txt",
        "prior_domiciliation_baseline_source_header_locator": "private-source-locator",
        "reason": "operator-free-text-secret",
    }
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=str(_PROFILE),
            event_type=BucketEventType.MODELO_EXPORTED,
            occurred_at=occurred_at,
            actor="private-actor",
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="a" * 64,
            payload=payload,
        ),
        bucket_id=str(_PROFILE),
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=occurred_at,
        actor="private-actor",
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="a" * 64,
        payload_version=1,
        payload=payload,
    )
    projected = ModeloHistoryTimelineProjection(
        profile_id=_PROFILE,
        modelo="130",
        year=2025,
        period="1T",
        count=1,
        events=(ModeloTimelineEvent.from_event(event),),
    )
    public_json = projected.model_dump_json()
    assert projected.events[0].event_id == event.event_id
    assert projected.events[0].event_type is BucketEventType.MODELO_EXPORTED
    assert projected.events[0].occurred_at == event.occurred_at
    assert projected.events[0].occurred_at.microsecond == 123456
    for forbidden in ("output_path", "private/tax-export", "source_header_locator", "private-actor", "reason"):
        assert forbidden not in public_json
    assert ModeloHistoryTimelineProjection.model_validate_json(public_json) == projected
    with pytest.raises(ValidationError):
        ModeloHistoryTimelineProjection(profile_id=_PROFILE, modelo="130", count=2, events=projected.events)
    with pytest.raises(ValidationError):
        ModeloTimelineEvent(
            event_id=event.event_id, event_type=BucketEventType.PROFILE_ACTIVATED, occurred_at=occurred_at
        )


@pytest.mark.parametrize(
    "occurred_at",
    (
        datetime(2025, 5, 1),
        datetime(2025, 5, 1, tzinfo=timezone(timedelta(hours=2))),
    ),
)
def test_timeline_rejects_noncanonical_timestamp(occurred_at: datetime) -> None:
    with pytest.raises(ValidationError):
        ModeloTimelineEvent(
            event_id="a" * 64,
            event_type=BucketEventType.MODELO_EXPORTED,
            occurred_at=occurred_at,
        )
    with pytest.raises(ValidationError):
        ModeloTimelineEvent.model_validate_json(
            json.dumps(
                {
                    "event_id": "a" * 64,
                    "event_type": BucketEventType.MODELO_EXPORTED.value,
                    "occurred_at": occurred_at.isoformat(),
                }
            )
        )

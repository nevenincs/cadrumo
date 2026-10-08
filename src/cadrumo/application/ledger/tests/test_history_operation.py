"""The encrypted history projection is exact and admitted only profile-wide."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.hashing import canonical_json_bytes
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...bucket_event_projection import BucketEventProjection
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LedgerHistoryProjection,
    LedgerHistoryRequest,
    build_ledger_history_definition,
    build_ledger_history_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_TRANSACTION_ID = "c" * 64
_OCCURRED_AT = datetime(2026, 7, 31, 12, 30, tzinfo=UTC)


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    """Fail if schema construction attempts profile service composition."""
    raise AssertionError(f"history schema construction composed ports for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    """Build the real history contract without resolving worker dependencies."""
    definition = build_ledger_history_definition(_unexpected_ports)
    registration = build_ledger_history_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration


def _request(
    *,
    profile_id: UUID = _PROFILE,
    subject_profile_id: UUID | None = None,
    include_split_siblings: bool = False,
) -> OperationRequest[BaseModel]:
    """Build a history request while allowing a deliberately mismatched subject."""
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerHistoryRequest(
            profile_id=profile_id,
            transaction_prefix=_TRANSACTION_ID[:12],
            include_split_siblings=include_split_siblings,
        ),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    """Build a result-disclosure context for the exact registered contract."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _event(
    *,
    bucket_id: UUID = _PROFILE,
    payload: dict[str, str] | None = None,
    object_id: str = _TRANSACTION_ID,
) -> BucketEvent:
    """Construct a canonical content-addressed transaction event."""
    event_payload = payload if payload is not None else {"change": "updated", "transaction_id": object_id}
    event_type = BucketEventType.LEDGER_TRANSACTION_UPDATED
    object_type = BucketEventObjectType.LEDGER_TRANSACTION
    event_id = derive_bucket_event_id(
        bucket_id=str(bucket_id),
        event_type=event_type,
        occurred_at=_OCCURRED_AT,
        actor="operator",
        object_type=object_type,
        object_id=object_id,
        payload=event_payload,
    )
    return BucketEvent(
        event_id=event_id,
        bucket_id=str(bucket_id),
        event_type=event_type,
        occurred_at=_OCCURRED_AT,
        actor="operator",
        object_type=object_type,
        object_id=object_id,
        payload_version=3,
        payload=event_payload,
    )


def _history_projection(
    event: BucketEvent,
    *,
    profile_id: UUID = _PROFILE,
    event_count: int = 1,
    transaction_id: str = _TRANSACTION_ID,
    object_ids: tuple[str, ...] = (_TRANSACTION_ID,),
) -> LedgerHistoryProjection:
    """Build one strict history result around a canonical event."""
    return LedgerHistoryProjection(
        profile_id=profile_id,
        transaction_prefix=event.object_id[:12],
        include_split_siblings=False,
        transaction_id=transaction_id,
        object_ids=object_ids,
        events=(BucketEventProjection.from_event(event),),
        event_count=event_count,
    )


def test_history_registration_binds_exact_models_without_composing_ports() -> None:
    registry, registration = _registry()

    definition = registry.lookup(LEDGER_HISTORY_OPERATION_DEFINITION_ID)
    contract = registration.contract

    assert definition.request_type is LedgerHistoryRequest
    assert definition.result_type is LedgerHistoryProjection
    assert contract.request_schema.schema_id == "ledger.history.request"
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == "ledger.history.result"
    assert {binding.model_type for binding in registration.schema_bindings} == {
        LedgerHistoryRequest,
        LedgerHistoryProjection,
    }
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


def test_history_access_is_full_profile_even_when_siblings_are_excluded() -> None:
    registry, registration = _registry()
    request = _request(include_split_siblings=False)
    context = _access_context(registration)
    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert isinstance(request.payload, LedgerHistoryRequest)
    assert request.payload.include_split_siblings is False
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert AccessAction.COMMIT not in resolved.policy.actions
    assert registration.contract.result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == registration.contract.result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        (_OTHER_PROFILE, _PROFILE, _PROFILE),
        (_PROFILE, _PROFILE, _OTHER_PROFILE),
    ],
)
def test_history_access_refuses_a_foreign_profile_or_subject(
    context_profile: UUID,
    payload_profile: UUID,
    subject_profile: UUID,
) -> None:
    registry, registration = _registry()
    request = _request(profile_id=payload_profile, subject_profile_id=subject_profile)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=context_profile),
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_history_projection_json_roundtrip_preserves_canonical_event_facts() -> None:
    event = _event(payload={"change": "updated", "transaction_id": _TRANSACTION_ID})
    projection = _history_projection(event)
    restored = LedgerHistoryProjection.model_validate_json(projection.model_dump_json())
    history = restored.to_history()

    assert restored == projection
    assert history.event_count == 1
    assert history.events == (event,)
    assert history.events[0].event_id == event.event_id
    assert history.events[0].payload_version == event.payload_version == 3
    assert history.events[0].actor == event.actor == "operator"
    assert dict(history.events[0].payload) == dict(event.payload)


def test_history_event_projection_rejects_duplicate_payload_names() -> None:
    projection = BucketEventProjection.from_event(_event())
    data = projection.model_dump(mode="json")
    data["details"] = [{"name": "change", "value": "first"}, {"name": "change", "value": "second"}]

    with pytest.raises(ValidationError, match="bucket event repeats a payload name"):
        BucketEventProjection.model_validate_json(canonical_json_bytes(data))


def test_history_event_projection_rejects_payload_names_that_collide_after_normalization() -> None:
    event = _event(payload={"memo": "same"})
    projection = BucketEventProjection.from_event(event)
    data = projection.model_dump(mode="json")
    data["details"] = [{"name": " memo", "value": "same"}, {"name": "memo ", "value": "same"}]

    with pytest.raises(ValidationError, match="bucket event projection contains noncanonical facts"):
        BucketEventProjection.model_validate_json(canonical_json_bytes(data))


@pytest.mark.parametrize(
    ("field", "altered"),
    [("actor", " operator "), ("object_id", f" {_TRANSACTION_ID} ")],
)
def test_history_event_projection_rejects_identity_text_that_bucket_events_would_normalize(
    field: str,
    altered: str,
) -> None:
    projection = BucketEventProjection.from_event(_event())
    data = projection.model_dump(mode="json")
    data[field] = altered

    with pytest.raises(ValidationError, match="bucket event projection contains noncanonical facts"):
        BucketEventProjection.model_validate_json(canonical_json_bytes(data))


def test_history_event_projection_rejects_altered_content_under_an_existing_event_id() -> None:
    projection = BucketEventProjection.from_event(_event())
    data = projection.model_dump(mode="json")
    data["actor"] = "different-operator"

    with pytest.raises(ValidationError):
        BucketEventProjection.model_validate_json(canonical_json_bytes(data))


def test_history_event_projection_rejects_payload_values_that_bucket_events_would_normalize() -> None:
    event = _event(payload={"memo": "same"})
    projection = BucketEventProjection.from_event(event)
    data = projection.model_dump(mode="json")
    data["details"] = [{"name": "memo", "value": " same "}]

    with pytest.raises(ValidationError, match="bucket event projection contains noncanonical facts"):
        BucketEventProjection.model_validate_json(canonical_json_bytes(data))


def test_history_projection_rejects_a_foreign_profile_event() -> None:
    with pytest.raises(ValidationError, match="ledger history events do not match their profile or count"):
        _history_projection(_event(bucket_id=_OTHER_PROFILE))


def test_history_projection_rejects_an_inconsistent_event_count() -> None:
    with pytest.raises(ValidationError, match="ledger history events do not match their profile or count"):
        _history_projection(_event(), event_count=2)


def test_history_projection_rejects_a_missing_transaction_anchor() -> None:
    with pytest.raises(ValidationError, match="ledger history has invalid lineage anchors"):
        _history_projection(_event(), transaction_id="d" * 64)


def test_history_projection_requires_canonical_event_id_tie_order_across_anchors() -> None:
    current_event = _event(object_id=_TRANSACTION_ID)
    previous_event = _event(object_id="d" * 64)
    current_event, previous_event = sorted(
        (current_event, previous_event),
        key=lambda event: event.event_id,
        reverse=True,
    )
    assert current_event.event_id > previous_event.event_id
    assert current_event.occurred_at == previous_event.occurred_at

    ordered = LedgerHistoryProjection(
        profile_id=_PROFILE,
        transaction_prefix=current_event.object_id[:12],
        include_split_siblings=False,
        transaction_id=current_event.object_id,
        object_ids=(current_event.object_id, previous_event.object_id),
        events=tuple(BucketEventProjection.from_event(event) for event in (previous_event, current_event)),
        event_count=2,
    )
    assert tuple(event.event_id for event in ordered.events) == (previous_event.event_id, current_event.event_id)

    with pytest.raises(ValidationError, match="ledger history is not in canonical event order"):
        LedgerHistoryProjection(
            profile_id=_PROFILE,
            transaction_prefix=current_event.object_id[:12],
            include_split_siblings=False,
            transaction_id=current_event.object_id,
            object_ids=(current_event.object_id, previous_event.object_id),
            events=tuple(BucketEventProjection.from_event(event) for event in (current_event, previous_event)),
            event_count=2,
        )

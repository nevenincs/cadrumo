"""Encrypted-profile seeds and exact readback assertions for recipient operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import BaseModel

from ...adapters.persistence.profile.buckets import build_bucket_event_history_repository
from ...adapters.persistence.profile.review_package_recipient_registry import (
    build_recipient_fingerprint_registry_ports,
)
from ...application.modelo.review_package_recipient_operations import (
    REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
    REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
    REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
    ReviewPackageRecipientAddProjection,
    ReviewPackageRecipientAddRequest,
    ReviewPackageRecipientListProjection,
    ReviewPackageRecipientListRequest,
    ReviewPackageRecipientProjection,
    ReviewPackageRecipientRemoveProjection,
    ReviewPackageRecipientRemoveRequest,
)
from ...application.modelo.review_package_recipient_registry import (
    RecipientFingerprintRecord,
    RecipientFingerprintRegister,
    add_recipient_fingerprint,
    list_recipient_fingerprints,
)
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType

RecipientAction = Literal["add", "list", "remove"]


@dataclass(frozen=True, slots=True)
class RecipientOperationConformanceCase:
    """One exact request and its encrypted before-state expectations."""

    action: RecipientAction
    request: BaseModel
    expected_effect: OperationEffect
    expected_projection: BaseModel | None
    expected_register_before: RecipientFingerprintRegister
    expected_history_before: BucketEventHistoryCatalogue
    recipient_id: str
    public_key_hex: str | None = None
    label: str | None = None


def _key_hex(seed: int) -> str:
    private_bytes = bytes((seed + offset) % 256 for offset in range(32))
    return X25519PrivateKey.from_private_bytes(private_bytes).public_key().public_bytes_raw().hex()


def _record(recipient_id: str, *, seed: int, label: str) -> RecipientFingerprintRecord:
    return RecipientFingerprintRecord(
        recipient_id=recipient_id,
        public_key_hex=_key_hex(seed),
        label=label,
        added_at=now(),
    )


def _seed(*records: RecipientFingerprintRecord, bucket_id: str) -> RecipientFingerprintRegister:
    ports = build_recipient_fingerprint_registry_ports(bucket_id=bucket_id)
    for record in records:
        add_recipient_fingerprint(
            recipient_id=record.recipient_id,
            public_key_hex=record.public_key_hex,
            label=record.label,
            added_at=record.added_at,
            ports=ports,
        )
    return RecipientFingerprintRegister(records=list_recipient_fingerprints(ports=ports))


def prepare_recipient_operation_case(
    definition_id: str,
    profile_id: UUID,
) -> RecipientOperationConformanceCase:
    """Prepare canonical add/list/remove cases in the actual profile storage."""
    bucket_id = str(profile_id)
    history_before = build_bucket_event_history_repository(bucket_id=bucket_id).load()
    if definition_id == REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID:
        register_before = _seed(bucket_id=bucket_id)
        recipient_id = "recipient-conformance"
        public_key_hex = _key_hex(7)
        label = "Conformance accountant"
        return RecipientOperationConformanceCase(
            action="add",
            request=ReviewPackageRecipientAddRequest(
                profile_id=profile_id,
                recipient_id=recipient_id,
                public_key_hex=public_key_hex,
                label=label,
            ),
            expected_effect=OperationEffect.UPDATED,
            expected_projection=None,
            expected_register_before=register_before,
            expected_history_before=history_before,
            recipient_id=recipient_id,
            public_key_hex=public_key_hex,
            label=label,
        )
    if definition_id == REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID:
        register_before = _seed(
            _record("zulu-conformance", seed=2, label="Zulu adviser"),
            _record("alpha-conformance", seed=3, label="Alpha adviser"),
            bucket_id=bucket_id,
        )
        expected_projection = ReviewPackageRecipientListProjection(
            profile_id=profile_id,
            recipients=tuple(
                ReviewPackageRecipientProjection.from_record(record)
                for record in sorted(register_before.records, key=lambda item: item.recipient_id)
            ),
            count=len(register_before.records),
        )
        return RecipientOperationConformanceCase(
            action="list",
            request=ReviewPackageRecipientListRequest(profile_id=profile_id),
            expected_effect=OperationEffect.NONE,
            expected_projection=expected_projection,
            expected_register_before=register_before,
            expected_history_before=history_before,
            recipient_id="",
        )
    if definition_id == REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID:
        recipient_id = "remove-conformance"
        register_before = _seed(
            _record(recipient_id, seed=4, label="Removed adviser"),
            _record("retained-conformance", seed=5, label="Retained adviser"),
            bucket_id=bucket_id,
        )
        expected_projection = ReviewPackageRecipientRemoveProjection(
            profile_id=profile_id,
            recipient_id=recipient_id,
            remaining=len(register_before.records) - 1,
        )
        return RecipientOperationConformanceCase(
            action="remove",
            request=ReviewPackageRecipientRemoveRequest(profile_id=profile_id, recipient_id=recipient_id),
            expected_effect=OperationEffect.UPDATED,
            expected_projection=expected_projection,
            expected_register_before=register_before,
            expected_history_before=history_before,
            recipient_id=recipient_id,
        )
    raise ValueError(f"unsupported recipient operation definition: {definition_id}")


def read_recipient_operation_register(profile_id: UUID) -> RecipientFingerprintRegister:
    """Read the full encrypted recipient register for the exact profile."""
    ports = build_recipient_fingerprint_registry_ports(bucket_id=str(profile_id))
    return RecipientFingerprintRegister(records=list_recipient_fingerprints(ports=ports))


def read_recipient_operation_history(profile_id: UUID) -> BucketEventHistoryCatalogue:
    """Read the exact profile's complete encrypted bucket-event history."""
    return build_bucket_event_history_repository(bucket_id=str(profile_id)).load()


def assert_recipient_operation_conformance_result(
    case: RecipientOperationConformanceCase,
    projection: BaseModel,
    *,
    profile_id: UUID,
    operation_id: str,
) -> None:
    """Compare the full public DTO and canonical post-write stores with the seed."""
    assert len(operation_id) == 64
    after = read_recipient_operation_register(profile_id)
    history_after = read_recipient_operation_history(profile_id)
    assert len({row.recipient_id for row in after.records}) == len(after.records)

    if case.action == "list":
        assert isinstance(case.request, ReviewPackageRecipientListRequest)
        assert isinstance(projection, ReviewPackageRecipientListProjection)
        assert projection == case.expected_projection
        assert after == case.expected_register_before
        assert history_after == case.expected_history_before
        return

    if case.action == "add":
        assert isinstance(case.request, ReviewPackageRecipientAddRequest)
        assert isinstance(projection, ReviewPackageRecipientAddProjection)
        assert projection.profile_id == profile_id
        matches = tuple(row for row in after.records if row.recipient_id == case.recipient_id)
        assert len(matches) == 1
        stored = matches[0]
        assert stored.public_key_hex == case.public_key_hex
        assert stored.label == case.label
        assert projection.recipient == ReviewPackageRecipientProjection.from_record(stored)
        assert tuple(row for row in after.records if row.recipient_id != case.recipient_id) == tuple(
            row for row in case.expected_register_before.records if row.recipient_id != case.recipient_id
        )
        event_type = BucketEventType.COLLAB_RECIPIENT_REGISTERED
        expected_payload = {
            "recipient_id": stored.recipient_id,
            "label": stored.label,
            "fingerprint_sha256": stored.fingerprint_sha256,
        }
    else:
        assert case.action == "remove"
        assert isinstance(case.request, ReviewPackageRecipientRemoveRequest)
        assert isinstance(projection, ReviewPackageRecipientRemoveProjection)
        expected_records = tuple(
            row for row in case.expected_register_before.records if row.recipient_id != case.recipient_id
        )
        assert after.records == expected_records
        assert projection == case.expected_projection
        event_type = BucketEventType.COLLAB_RECIPIENT_REMOVED
        expected_payload = {"recipient_id": case.recipient_id}

    assert len(after.records) == len(case.expected_register_before.records) + (1 if case.action == "add" else -1)
    assert all(
        history_after.events.get(event_id) == event for event_id, event in case.expected_history_before.events.items()
    )
    new_events = tuple(
        event for event_id, event in history_after.events.items() if event_id not in case.expected_history_before.events
    )
    assert len(new_events) == 1
    event = new_events[0]
    assert event.bucket_id == str(profile_id)
    assert event.event_type is event_type
    assert event.object_type is BucketEventObjectType.RECIPIENT
    assert event.object_id == case.recipient_id
    assert event.actor == "operator"
    assert dict(event.payload) == expected_payload
    assert "public_key_hex" not in event.payload


__all__ = [
    "RecipientAction",
    "RecipientOperationConformanceCase",
    "assert_recipient_operation_conformance_result",
    "prepare_recipient_operation_case",
    "read_recipient_operation_history",
    "read_recipient_operation_register",
]

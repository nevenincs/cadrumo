"""Google Drive response-metadata parsing and terminal-failure contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from ....application.operator_actions import no_action_precondition_verdict
from ....core.errors.hierarchy import CoreValidationError
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.time import parse_iso_datetime, validate_utc_aware
from ._records import ProviderObjectMetadata
from .errors import OutboundStorageIntegrityError

if TYPE_CHECKING:
    from ..google.records import DriveAppProperties


class DriveStoragePreconditionCondition(StrEnum):
    """Closed terminal conditions for observed Google Drive provider failures."""

    API_CLIENT_AVAILABLE = "storage.google_drive.api_client.available"
    REQUEST_AUTHORIZED = "storage.google_drive.request.authorized"
    TARGET_PRESENT = "storage.google_drive.target.present"
    REQUEST_CONFLICT_FREE = "storage.google_drive.request.conflict_free"
    REQUEST_WITHIN_QUOTA = "storage.google_drive.request.within_quota"
    REQUEST_AVAILABLE = "storage.google_drive.request.available"
    REQUEST_TRANSPORT_AVAILABLE = "storage.google_drive.request.transport_available"
    RESPONSE_IDENTIFIER_PRESENT = "storage.google_drive.response.identifier_present"
    OWNERSHIP_ALIGNED = "storage.google_drive.ownership.aligned"
    RESPONSE_MAPPING = "storage.google_drive.response.mapping"
    NAMESPACE_PRESENT = "storage.google_drive.namespace.present"
    OBJECT_PRESENT = "storage.google_drive.object.present"
    MEDIA_PAYLOAD_BYTES = "storage.google_drive.media.payload_bytes"
    METADATA_SIZE_VALID = "storage.google_drive.metadata.size_valid"
    METADATA_MODIFIED_TIME_VALID = "storage.google_drive.metadata.modified_time_valid"
    METADATA_APP_PROPERTIES_VALID = "storage.google_drive.metadata.app_properties_valid"


def _drive_external_verdict(
    condition: DriveStoragePreconditionCondition,
    *,
    facts: Mapping[str, str | bool],
    outcome: NoRecoveryOutcome,
):
    """Project an observed Drive-provider refusal through the public no-action authority."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


def _parse_drive_size(value: object, *, provider_object_id: str) -> int:
    """Return the byte length Drive reported, or refuse malformed metadata."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise OutboundStorageIntegrityError(
            "drive object metadata carries no usable size",
            context={"provider_object_id": provider_object_id, "actual_value": repr(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    try:
        byte_length = int(value)
    except ValueError:
        raise OutboundStorageIntegrityError(
            "drive object size is not an integer",
            context={"provider_object_id": provider_object_id, "actual_value": str(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    if byte_length < 0:
        raise OutboundStorageIntegrityError(
            "drive object size is negative",
            context={"provider_object_id": provider_object_id, "actual_value": str(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return byte_length


def _parse_drive_modified_time(value: object, *, provider_object_id: str) -> datetime:
    """Return the write instant Drive reported, or refuse malformed metadata."""
    if not isinstance(value, str) or not value.strip():
        raise OutboundStorageIntegrityError(
            "drive object metadata carries no modifiedTime",
            context={"provider_object_id": provider_object_id, "actual_value": repr(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    try:
        written_at = parse_iso_datetime(value)
    except ValueError:
        raise OutboundStorageIntegrityError(
            "drive object modifiedTime is not an RFC 3339 instant",
            context={"provider_object_id": provider_object_id, "actual_value": value},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    try:
        validate_utc_aware(written_at)
    except CoreValidationError:
        raise OutboundStorageIntegrityError(
            "drive object modifiedTime carries no timezone",
            context={"provider_object_id": provider_object_id, "actual_value": value},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    return written_at


def _metadata_from_drive_entry(
    entry: dict[str, Any], *, namespace: str, object_key_hmac: str
) -> ProviderObjectMetadata:
    """Convert a Drive ``files().get/list`` response into provider metadata."""
    provider_object_id = str(entry.get("id", ""))
    byte_length = _parse_drive_size(entry.get("size"), provider_object_id=provider_object_id)
    written_at = _parse_drive_modified_time(entry.get("modifiedTime"), provider_object_id=provider_object_id)
    app_properties = entry.get("appProperties") or {}
    content_hash = str(app_properties.get("content_hash", "") or "")
    if not content_hash:
        md5 = entry.get("md5Checksum")
        content_hash = f"md5-{md5}" if md5 else "sha256-unverified"
    return ProviderObjectMetadata(
        namespace=namespace,
        object_key_hmac=object_key_hmac,
        provider_object_id=provider_object_id,
        byte_length=byte_length,
        content_hash=content_hash,
        written_at=written_at,
    )


def _drive_storage_app_properties(entry: dict[str, Any]) -> DriveAppProperties:
    """Return the validated app-owned metadata for a Drive storage object."""
    from pydantic import ValidationError

    from ..google.records import DriveAppProperties

    try:
        return DriveAppProperties.model_validate(entry.get("appProperties"))
    except ValidationError as exc:
        raise OutboundStorageIntegrityError(
            "drive object appProperties do not match the storage metadata contract",
            context={"provider_object_id": str(entry.get("id", ""))},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_APP_PROPERTIES_VALID,
                facts={"field": "appProperties", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc


def _drive_storage_content_hash(entry: dict[str, Any]) -> str:
    """Return the validated storage content hash for a Drive read."""
    return _drive_storage_app_properties(entry).content_hash

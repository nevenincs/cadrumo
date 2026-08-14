"""Application-owned current-format profile custody transactions.

This module is deliberately independent of the retired profile repository.
It owns only local current-format capsule transactions: bounded canonical
journals, root-before-profile locking, pointer compare-and-swap, local deletion
preflight and receipts.  It never contacts a remote system and it never reads a
retired custody layout.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ...adapters.persistence.storage.custody import (
    ProfileCustodyInventory,
)
from ...core import (
    STRICT_FROZEN_CONFIG,
)
from ...core.errors import CadrumoError
from ...core.identity import ProfileLabel
from ...core.time import validate_utc_aware
from .._profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection
from ._custody_pointer import ProfileCustodyPointerSnapshot

CUSTODY_TRANSACTION_SCHEMA_VERSION = 1
CUSTODY_TRANSACTION_MAX_BYTES = 16 * 1024
CUSTODY_RECEIPT_SCHEMA_VERSION = 1
CUSTODY_RECEIPT_MAX_BYTES = 4 * 1024
_SHA256_PREFIX = "sha256:"
_EXTERNAL_STATE_RETAINED: tuple[str, ...] = (
    "remote registrations retained",
    "external backups retained",
    "recovery artifacts retained",
    "external certificate and token state retained",
)
_ModelT = TypeVar("_ModelT", bound="_CustodyDigestModel")


class ProfileCapsuleLabel(BaseModel):
    """The one canonical label representation admitted into a create journal."""

    model_config = STRICT_FROZEN_CONFIG

    label: ProfileLabel


class ProfileCustodyTransactionError(CadrumoError):
    """Base error for local current-format custody transactions."""


class ProfileCustodyTransactionConflictError(ProfileCustodyTransactionError):
    """Raised when a captured local witness no longer matches live state."""


class ProfileCustodyTransactionRefusalError(ProfileCustodyTransactionError):
    """Raised when local deletion is not explicitly authorized by its evidence."""


class ProfileCustodyTransactionCorruptError(ProfileCustodyTransactionError):
    """Raised for a malformed, oversized, noncanonical, or swapped journal."""


class ProfileCustodyTransactionOperation(StrEnum):
    CREATE = "create"
    DELETE = "delete"


class ProfileCustodyTransactionState(StrEnum):
    PREPARED = "prepared"
    STAGE_VERIFIED = "stage_verified"
    CAPSULE_PUBLISHED = "capsule_published"
    POINTER_PUBLISHED = "pointer_published"
    DELETE_PREPARED = "delete_prepared"
    DELETE_MARKED = "delete_marked"
    PROCESS_SECRETS_REVOKED = "process_secrets_revoked"
    SESSION_ACCELERATION_DELETED = "session_acceleration_deleted"
    POINTER_CLEARED = "pointer_cleared"
    CAPSULE_RENAMED = "capsule_renamed"
    LOCAL_REMOVED = "local_removed"
    COMPLETE = "complete"
    ROLLED_BACK = "rolled_back"


def _digest(value: bytes) -> str:
    return f"{_SHA256_PREFIX}{sha256(value).hexdigest()}"


def _validate_sha256_digest(value: str, *, subject: str) -> str:
    if (
        len(value) != 71
        or not value.startswith(_SHA256_PREFIX)
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{subject} must be a lowercase sha256 digest")
    return value


def _canonical_bytes(value: object, *, maximum_bytes: int, subject: str) -> bytes:
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be canonically encoded") from exc
    if len(encoded) > maximum_bytes:
        raise ProfileCustodyTransactionCorruptError(f"{subject} exceeds its byte limit")
    return encoded


def canonical_model_bytes(model: BaseModel, *, maximum_bytes: int, subject: str) -> bytes:
    return _canonical_bytes(model.model_dump(mode="json"), maximum_bytes=maximum_bytes, subject=subject)


def _payload_without_self_digest(model: BaseModel) -> dict[str, object]:
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    payload.pop("self_digest", None)
    return payload


def _computed_self_digest(model: BaseModel, *, maximum_bytes: int, subject: str) -> str:
    return _digest(_canonical_bytes(_payload_without_self_digest(model), maximum_bytes=maximum_bytes, subject=subject))


def _model_json_with_self_digest(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    maximum_bytes: int,
    subject: str,
) -> bytes:
    payload = cast(dict[str, object], model_type.model_construct(**values, self_digest="").model_dump(mode="json"))
    payload["self_digest"] = _digest(
        _canonical_bytes(
            {key: value for key, value in payload.items() if key != "self_digest"},
            maximum_bytes=maximum_bytes,
            subject=subject,
        )
    )
    return _canonical_bytes(payload, maximum_bytes=maximum_bytes, subject=subject)


def read_profile_custody_record(path: Path, *, maximum_bytes: int, subject: str) -> bytes:
    if not os.path.lexists(path):
        raise ProfileCustodyTransactionConflictError(f"{subject} is absent")
    try:
        from ...adapters.persistence.storage.custody import read_profile_custody_local_record

        return read_profile_custody_local_record(path, maximum_bytes=maximum_bytes)
    except Exception as exc:
        raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be opened") from exc


class _CustodyDigestModel(BaseModel):
    """Shared canonical digest and JSON behavior for custody records."""

    model_config = STRICT_FROZEN_CONFIG
    _digest_maximum_bytes: ClassVar[int]
    _digest_subject: ClassVar[str]

    @property
    def computed_self_digest(self) -> str:
        return _computed_self_digest(
            self,
            maximum_bytes=self._digest_maximum_bytes,
            subject=self._digest_subject,
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_model_bytes(
            self,
            maximum_bytes=self._digest_maximum_bytes,
            subject=self._digest_subject,
        )

    @classmethod
    def _create_with_self_digest(cls: type[_ModelT], values: dict[str, Any], error_message: str) -> _ModelT:
        try:
            return cls.model_validate_json(
                _model_json_with_self_digest(
                    cls,
                    values,
                    maximum_bytes=cls._digest_maximum_bytes,
                    subject=cls._digest_subject,
                )
            )
        except ValidationError as exc:
            raise ProfileCustodyTransactionCorruptError(error_message) from exc


class ProfileCustodyInventoryWitness(BaseModel):
    """Non-secret exact-inventory witness bound into a destructive journal."""

    model_config = STRICT_FROZEN_CONFIG

    digest: str = Field(min_length=71, max_length=71)
    file_count: int = Field(ge=1, le=2048)
    total_bytes: int = Field(ge=1, le=512 * 1024 * 1024)

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _validate_sha256_digest(value, subject="inventory digest")

    @classmethod
    def from_inventory(cls, inventory: ProfileCustodyInventory) -> ProfileCustodyInventoryWitness:
        return cls(digest=inventory.digest, file_count=len(inventory.entries), total_bytes=inventory.total_bytes)


class ProfileCustodyHoldAssessment(BaseModel):
    """The bound outcome from the independent legal and filing hold owners."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    legal_hold: bool
    filing_hold: bool
    assessed_at: datetime
    assessor: Literal["application-custody-hold-owner"] = "application-custody-hold-owner"
    evidence_digest: str = Field(min_length=71, max_length=71)

    @model_validator(mode="after")
    def _validate_assessed_at(self) -> ProfileCustodyHoldAssessment:
        validate_utc_aware(self.assessed_at)
        return self

    @property
    def permits_local_deletion(self) -> bool:
        return not self.legal_hold and not self.filing_hold

    @classmethod
    def from_owner_evidence(
        cls,
        *,
        legal: ProfileCustodyHoldEvidence,
        filing: ProfileCustodyHoldEvidence,
    ) -> ProfileCustodyHoldAssessment:
        if legal.profile_id != filing.profile_id:
            raise ProfileCustodyTransactionCorruptError("hold owners disagree on profile identity")
        assessed_at = max(legal.assessed_at, filing.assessed_at)
        payload = {
            "profile_id": str(legal.profile_id),
            "legal_evidence_digest": legal.evidence_digest,
            "filing_evidence_digest": filing.evidence_digest,
            "assessed_at": assessed_at.astimezone(UTC).isoformat(),
            "assessor": "application-custody-hold-owner",
        }
        return cls(
            profile_id=legal.profile_id,
            legal_hold=legal.blocks_local_deletion,
            filing_hold=filing.blocks_local_deletion,
            assessed_at=assessed_at,
            assessor="application-custody-hold-owner",
            evidence_digest=_digest(_canonical_bytes(payload, maximum_bytes=1024, subject="hold assessment")),
        )


class ProfileCustodyHoldEvidence(BaseModel):
    """One immutable canonical answer from a legal or filing hold owner."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    owner: Literal["legal", "filing"]
    profile_id: UUID
    disposition: Literal["cleared", "held"]
    source_record_id: str = Field(min_length=3, max_length=256)
    source_record_digest: str = Field(min_length=71, max_length=71)
    assessed_at: datetime
    authority: Literal["application-legal-hold-owner", "application-filing-hold-owner"]
    evidence_digest: str = Field(min_length=71, max_length=71)

    @field_validator("source_record_id")
    @classmethod
    def _validate_source_record_id(cls, value: str) -> str:
        if value != value.strip() or any(character in value for character in "\\/\x00"):
            raise ValueError("hold source record id must be one bounded canonical identifier")
        return value

    @field_validator("source_record_digest")
    @classmethod
    def _validate_source_record_digest(cls, value: str) -> str:
        return _validate_sha256_digest(value, subject="hold source record digest")

    @model_validator(mode="after")
    def _validate_proof(self) -> ProfileCustodyHoldEvidence:
        validate_utc_aware(self.assessed_at)
        expected_authority = f"application-{self.owner}-hold-owner"
        if self.authority != expected_authority:
            raise ValueError("hold evidence authority does not own its evidence kind")
        if self.evidence_digest != self.computed_evidence_digest:
            raise ValueError("hold evidence digest does not match its authoritative fields")
        return self

    @property
    def blocks_local_deletion(self) -> bool:
        return self.disposition == "held"

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["evidence_digest"]
        return payload

    @property
    def computed_evidence_digest(self) -> str:
        return _digest(_canonical_bytes(self.canonical_payload, maximum_bytes=1024, subject="hold evidence"))


def evidence_from_owner_projection(projection: ProfileDeletionHoldOwnerProjection) -> ProfileCustodyHoldEvidence:
    """Create derived custody evidence from a read-only external owner projection."""
    authority = cast(
        Literal["application-legal-hold-owner", "application-filing-hold-owner"],
        f"application-{projection.owner}-hold-owner",
    )
    values: dict[str, Any] = {
        "owner": projection.owner,
        "profile_id": projection.profile_id,
        "disposition": "held" if projection.blocks_local_deletion else "cleared",
        "source_record_id": projection.source_record_id,
        "source_record_digest": projection.source_record_digest,
        "assessed_at": projection.assessed_at,
        "authority": authority,
    }
    unsigned = ProfileCustodyHoldEvidence.model_construct(**values, evidence_digest="")
    return ProfileCustodyHoldEvidence(**values, evidence_digest=unsigned.computed_evidence_digest)


class ProfileCustodyDeleteConfirmation(BaseModel):
    """A confirmation whose exact target is bound to one prepared journal."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: UUID
    profile_id: UUID
    inventory_digest: str = Field(min_length=71, max_length=71)
    challenge: str = Field(min_length=64, max_length=64)


class ProfileCustodyTransactionJournal(_CustodyDigestModel):
    """One bounded canonical, credential-free local custody transaction record."""

    _digest_maximum_bytes = CUSTODY_TRANSACTION_MAX_BYTES
    _digest_subject = "custody journal"

    schema_version: Literal[1] = CUSTODY_TRANSACTION_SCHEMA_VERSION
    transaction_id: UUID
    operation: ProfileCustodyTransactionOperation
    profile_id: UUID
    state: ProfileCustodyTransactionState
    started_at: datetime
    updated_at: datetime
    pointer_before: ProfileCustodyPointerSnapshot
    expected_custody_digest: str | None = Field(default=None, min_length=71, max_length=71)
    proposed_custody_digest: str | None = Field(default=None, min_length=71, max_length=71)
    proposed_generation: int | None = Field(default=None, ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    staged_relative_path: str | None = Field(default=None, min_length=1, max_length=256)
    inventory: ProfileCustodyInventoryWitness | None = None
    hold_assessment: ProfileCustodyHoldAssessment | None = None
    confirmation_challenge: str | None = Field(default=None, min_length=64, max_length=64)
    tombstone_relative_path: str | None = Field(default=None, min_length=1, max_length=256)
    self_digest: str = Field(min_length=71, max_length=71)

    @field_validator("expected_custody_digest", "proposed_custody_digest")
    @classmethod
    def _validate_optional_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256_digest(value, subject="custody digest")

    @field_validator("label")
    @classmethod
    def _validate_canonical_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(ProfileCapsuleLabel(label=value).label)

    @field_validator("staged_relative_path", "tombstone_relative_path")
    @classmethod
    def _validate_single_component_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("custody transaction path must be one local component")
        return value

    @model_validator(mode="after")
    def _validate_record(self) -> ProfileCustodyTransactionJournal:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("custody transaction update precedes start")
        if self.self_digest != self.computed_self_digest:
            raise ValueError("custody transaction self digest does not match")
        self._validate_operation_shape()
        return self

    def _validate_operation_shape(self) -> None:
        if self.operation is ProfileCustodyTransactionOperation.CREATE:
            self._validate_create_operation_shape()
            return
        self._validate_delete_operation_shape()

    def _validate_create_operation_shape(self) -> None:
        if self.proposed_generation is None or self.staged_relative_path is None or self.label is None:
            raise ValueError("create transaction requires proposed custody generation and stage")
        if (
            self.state
            not in {
                ProfileCustodyTransactionState.PREPARED,
                ProfileCustodyTransactionState.ROLLED_BACK,
            }
            and self.proposed_custody_digest is None
        ):
            raise ValueError("verified create transaction requires its staged custody digest")
        if self.inventory is not None or self.hold_assessment is not None or self.confirmation_challenge is not None:
            raise ValueError("create transaction cannot carry deletion authorization")

    def _validate_delete_operation_shape(self) -> None:
        if self.inventory is None or self.hold_assessment is None or self.confirmation_challenge is None:
            raise ValueError("delete transaction requires inventory, hold assessment, and confirmation challenge")
        if (
            self.state
            in {
                ProfileCustodyTransactionState.CAPSULE_RENAMED,
                ProfileCustodyTransactionState.LOCAL_REMOVED,
                ProfileCustodyTransactionState.COMPLETE,
            }
            and self.tombstone_relative_path is None
        ):
            raise ValueError("advanced delete transaction requires a tombstone path")

    @property
    def canonical_payload(self) -> dict[str, object]:
        return _payload_without_self_digest(self)

    @classmethod
    def create(cls, **values: Any) -> ProfileCustodyTransactionJournal:
        return cls._create_with_self_digest(values, "cannot construct custody journal")

    def with_update(self, **changes: object) -> ProfileCustodyTransactionJournal:
        payload = dict(self.__dict__)
        payload.update(changes)
        payload.pop("self_digest")
        return self.create(**payload)


class ProfileCustodyTransactionReceipt(_CustodyDigestModel):
    """One idempotent durable receipt for the application local-delete owner."""

    schema_version: Literal[1] = CUSTODY_RECEIPT_SCHEMA_VERSION
    owner: Literal["application-local-custody"] = "application-local-custody"
    transaction_id: UUID
    profile_id: UUID
    operation: ProfileCustodyTransactionOperation = ProfileCustodyTransactionOperation.DELETE
    completed_at: datetime
    inventory: ProfileCustodyInventoryWitness
    pointer_cleared: bool
    pointer_published: bool = False
    retained_external_state: tuple[str, ...] = _EXTERNAL_STATE_RETAINED
    self_digest: str = Field(min_length=71, max_length=71)

    @model_validator(mode="after")
    def _validate_receipt(self) -> ProfileCustodyTransactionReceipt:
        validate_utc_aware(self.completed_at)
        if self.retained_external_state != _EXTERNAL_STATE_RETAINED:
            raise ValueError("local custody receipt must disclose every retained external state")
        if self.operation is ProfileCustodyTransactionOperation.CREATE:
            if not self.pointer_published or self.pointer_cleared:
                raise ValueError("create receipt requires exactly pointer publication")
        elif self.pointer_published:
            raise ValueError("delete receipt cannot claim pointer publication")
        if self.self_digest != self.computed_self_digest:
            raise ValueError("custody receipt self digest does not match")
        return self

    @classmethod
    def create(cls, **values: Any) -> ProfileCustodyTransactionReceipt:
        return cls._create_with_self_digest(values, "cannot construct custody receipt")


class ProfileCustodyOwnerReceipt(_CustodyDigestModel):
    """One durable idempotence receipt for an ordered local deletion owner."""

    schema_version: Literal[1] = 1
    transaction_id: UUID
    profile_id: UUID
    owner: Literal["process-secret-revocation", "local-session-acceleration"]
    effect: Literal["revoked", "removed", "verified_absent"]
    completed_at: datetime
    self_digest: str = Field(min_length=71, max_length=71)

    @model_validator(mode="after")
    def _validate_receipt(self) -> ProfileCustodyOwnerReceipt:
        validate_utc_aware(self.completed_at)
        if self.self_digest != self.computed_self_digest:
            raise ValueError("custody owner receipt self digest does not match")
        return self

    @classmethod
    def create(cls, **values: Any) -> ProfileCustodyOwnerReceipt:
        return cls._create_with_self_digest(values, "cannot construct custody owner receipt")


__all__ = [
    "CUSTODY_RECEIPT_MAX_BYTES",
    "CUSTODY_RECEIPT_SCHEMA_VERSION",
    "CUSTODY_TRANSACTION_MAX_BYTES",
    "CUSTODY_TRANSACTION_SCHEMA_VERSION",
    "ProfileCustodyDeleteConfirmation",
    "ProfileCustodyHoldAssessment",
    "ProfileCustodyHoldEvidence",
    "ProfileCustodyInventoryWitness",
    "ProfileCustodyPointerSnapshot",
    "ProfileCustodyTransactionConflictError",
    "ProfileCustodyTransactionCorruptError",
    "ProfileCustodyTransactionError",
    "ProfileCustodyTransactionJournal",
    "ProfileCustodyTransactionOperation",
    "ProfileCustodyTransactionReceipt",
    "ProfileCustodyTransactionRefusalError",
    "ProfileCustodyTransactionState",
]

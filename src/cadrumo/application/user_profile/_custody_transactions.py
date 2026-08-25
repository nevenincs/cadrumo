"""Application-owned current-format profile custody transactions.

This module is deliberately independent of the retired profile repository.
It owns only local current-format capsule transactions: bounded canonical
journals, root-before-profile locking, pointer compare-and-swap, local deletion
preflight and receipts.  It never contacts a remote system and it never reads a
retired custody layout.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
)
from ...core.errors import CadrumoError
from ...core.hashing import (
    bounded_canonical_json_bytes,
    prefixed_digest,
    validate_prefixed_digest,
)
from ...core.identity import PrefixedContentDigest, ProfileLabel
from ...core.time import validate_utc_aware
from ._custody_hold_models import (
    ProfileCustodyHoldAssessment,
    ProfileCustodyHoldEvidence,
    ProfileCustodyRetentionOverride,
)
from ._custody_pointer import ProfileCustodyPointerSnapshot
from ._custody_ports import ProfileCustodyInventoryPort, default_profile_custody_local_record_store

CUSTODY_TRANSACTION_SCHEMA_VERSION = 1
CUSTODY_TRANSACTION_MAX_BYTES = 16 * 1024
CUSTODY_RECEIPT_SCHEMA_VERSION = 1
CUSTODY_RECEIPT_MAX_BYTES = 4 * 1024
_EXTERNAL_STATE_RETAINED: tuple[str, ...] = (
    "remote registrations retained",
    "external backups retained",
    "recovery artifacts retained",
    "external certificate and token state retained",
)
_ModelT = TypeVar("_ModelT", bound="CustodyDigestModel")
_PROFILE_LABEL_ADAPTER: TypeAdapter[str] = TypeAdapter(ProfileLabel)


class ProfileCustodyTransactionError(CadrumoError):
    """Base error for local current-format custody transactions."""


class ProfileCustodyTransactionConflictError(ProfileCustodyTransactionError):
    """Raised when a captured local witness no longer matches live state."""


class ProfileCustodyDuplicateLabelError(ProfileCustodyTransactionConflictError):
    """Raised when the requested label already names a committed capsule.

    A SUBCLASS of the conflict error because every existing handler that treats
    a custody conflict as a conflict should keep catching this one. It carries
    its own error code for one reason: retryability. Its parent means "a
    captured witness went stale", which a re-read genuinely fixes, so that code
    is published as retryable. A label collision is permanent -- the name is
    bound to a committed capsule and the identical command can never succeed --
    and a non-interactive caller may retry what it is told
    is retryable.
    """


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


def _canonical_bytes(value: object, *, maximum_bytes: int, subject: str) -> bytes:
    try:
        return bounded_canonical_json_bytes(value, maximum_bytes=maximum_bytes, subject=subject)
    except (TypeError, ValueError) as exc:
        raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be canonically encoded") from exc


def canonical_model_bytes(model: BaseModel, *, maximum_bytes: int, subject: str) -> bytes:
    return _canonical_bytes(model.model_dump(mode="json"), maximum_bytes=maximum_bytes, subject=subject)


def canonical_payload_digest(payload: object, *, maximum_bytes: int, subject: str) -> str:
    """Digest an already-JSON-shaped payload under the one canonical encoding."""
    return prefixed_digest(_canonical_bytes(payload, maximum_bytes=maximum_bytes, subject=subject))


def _payload_without_self_digest(model: BaseModel) -> dict[str, object]:
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    payload.pop("self_digest", None)
    return payload


def _computed_self_digest(model: BaseModel, *, maximum_bytes: int, subject: str) -> str:
    return prefixed_digest(
        _canonical_bytes(_payload_without_self_digest(model), maximum_bytes=maximum_bytes, subject=subject)
    )


def _model_json_with_self_digest(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    maximum_bytes: int,
    subject: str,
) -> bytes:
    payload = cast(dict[str, object], model_type.model_construct(**values, self_digest="").model_dump(mode="json"))
    payload["self_digest"] = prefixed_digest(
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
        return default_profile_custody_local_record_store().read(path, maximum_bytes=maximum_bytes)
    except Exception as exc:
        raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be opened") from exc


class CustodyDigestModel(BaseModel):
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
    """Non-secret exact-inventory witness bound into a destructive journal.

    All three fields describe the SAME set of capsule members: the ones the
    inventory's digest covers. Counting or measuring the wider observed set
    instead would make the witness self-inconsistent, and the local delete
    compares whole witnesses for equality between preflight and execution --
    so a file the digest deliberately ignores would still refuse the deletion
    through the count, which is the defect the narrowed digest exists to fix.
    """

    model_config = STRICT_FROZEN_CONFIG

    digest: str = Field(min_length=71, max_length=71)
    file_count: int = Field(ge=1, le=2048)
    total_bytes: int = Field(ge=1, le=512 * 1024 * 1024)

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="inventory digest")

    @classmethod
    def from_inventory(cls, inventory: ProfileCustodyInventoryPort) -> ProfileCustodyInventoryWitness:
        return cls(
            digest=inventory.digest,
            file_count=len(inventory.digest_entries),
            total_bytes=sum(entry.size_bytes for entry in inventory.digest_entries),
        )


class ProfileCustodyDeleteConfirmation(BaseModel):
    """A confirmation whose exact target is bound to one prepared journal."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: UUID
    profile_id: UUID
    inventory_digest: str = Field(min_length=71, max_length=71)
    challenge: str = Field(min_length=64, max_length=64)


class ProfileCustodyTransactionJournal(CustodyDigestModel):
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
    label_revision: int | None = Field(default=None, ge=1)
    label_content_digest: PrefixedContentDigest | None = None
    label_self_digest: str | None = Field(default=None, min_length=71, max_length=71)
    staged_relative_path: str | None = Field(default=None, min_length=1, max_length=256)
    inventory: ProfileCustodyInventoryWitness | None = None
    hold_assessment: ProfileCustodyHoldAssessment | None = None
    #: The operator authorisation, if any, to proceed past the FILING half of
    #: ``hold_assessment``. Digest-bound like every other field here, so the
    #: authorisation cannot be edited into a journal after the fact, and the
    #: recorded reason survives with the transaction that acted on it.
    retention_override: ProfileCustodyRetentionOverride | None = None
    #: True only for a single-target delete whose authority requires the
    #: target to remain inactive across preparation, confirmation, crash
    #: recovery, and every destructive owner effect.
    requires_inactive_target: bool = False
    confirmation_challenge: str | None = Field(default=None, min_length=64, max_length=64)
    tombstone_relative_path: str | None = Field(default=None, min_length=1, max_length=256)
    self_digest: str = Field(min_length=71, max_length=71)

    @field_validator(
        "expected_custody_digest",
        "proposed_custody_digest",
        "label_content_digest",
        "label_self_digest",
    )
    @classmethod
    def _validate_optional_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_prefixed_digest(value, field_name="custody digest")

    @field_validator("label")
    @classmethod
    def _validate_canonical_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _PROFILE_LABEL_ADAPTER.validate_python(value)

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
        self._require_create_label_provenance()
        self._require_create_custody_digest()
        self._reject_create_authorization()

    def _require_create_label_provenance(self) -> None:
        if any(value is None for value in (self.proposed_generation, self.staged_relative_path, self.label)):
            raise ValueError("create transaction requires canonical initial label provenance and stage")
        if self.label_revision != 1:
            raise ValueError("create transaction requires canonical initial label provenance and stage")
        if self.label_content_digest is None:
            raise ValueError("create transaction requires canonical initial label provenance and stage")
        if self.label_self_digest is None:
            raise ValueError("create transaction requires canonical initial label provenance and stage")

    def _require_create_custody_digest(self) -> None:
        if self.state in {
            ProfileCustodyTransactionState.PREPARED,
            ProfileCustodyTransactionState.ROLLED_BACK,
        }:
            return
        if self.proposed_custody_digest is None:
            raise ValueError("verified create transaction requires its staged custody digest")

    def _reject_create_authorization(self) -> None:
        if self.requires_inactive_target or any(
            value is not None for value in (self.inventory, self.hold_assessment, self.confirmation_challenge)
        ):
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


class ProfileCustodyTransactionReceipt(CustodyDigestModel):
    """One idempotent durable receipt for the application local-delete owner."""

    _digest_maximum_bytes = CUSTODY_RECEIPT_MAX_BYTES
    _digest_subject = "custody receipt"

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


class ProfileCustodyOwnerReceipt(CustodyDigestModel):
    """One durable idempotence receipt for an ordered local deletion owner."""

    _digest_maximum_bytes = CUSTODY_RECEIPT_MAX_BYTES
    _digest_subject = "custody owner receipt"

    schema_version: Literal[1]
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
    "CustodyDigestModel",
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

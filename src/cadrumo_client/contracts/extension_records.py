"""Bounded opaque extension-record custody; content travels only in secret frames."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

EXTENSION_RECORD_MAX_BYTES = 32_768


class ExtensionRecordCapability(BaseModel):
    """Installed policy, never accepted as client namespace or classification input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    capability: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    namespace: Annotated[str, Field(min_length=1, max_length=128)]
    schema_version: Annotated[int, Field(ge=1)]
    classification: SensitivityClass
    key_pattern: Annotated[str, Field(min_length=1, max_length=256)]
    maximum_bytes: Annotated[int, Field(ge=1, le=EXTENSION_RECORD_MAX_BYTES)] = EXTENSION_RECORD_MAX_BYTES
    actions: frozenset[Literal["read", "write", "delete", "generation"]]


class ExtensionRecordRefusal(StrEnum):
    """Reasons a service-owned extension-record request can be refused."""

    LEASE_INACTIVE = "lease_inactive"
    CAPABILITY_DENIED = "capability_denied"
    REVISION_CONFLICT = "revision_conflict"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ExtensionRecordRequest(BaseModel):
    """Exact admitted lease and opaque key; writes authorize one protected frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal[
        "extension_record_read", "extension_record_write", "extension_record_delete", "extension_record_generation"
    ]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    lease_id: UUID
    capability: Annotated[str, Field(min_length=1, max_length=64)]
    object_key: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    expected_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    byte_count: Annotated[int, Field(ge=1, le=EXTENSION_RECORD_MAX_BYTES)] | None = None

    @model_validator(mode="after")
    def _shape(self) -> ExtensionRecordRequest:
        generation = self.action == "extension_record_generation"
        mutation = self.action in ("extension_record_write", "extension_record_delete")
        if generation != (self.object_key is None):
            raise ValueError("only generation omits a record key")
        if mutation != (self.expected_revision is not None):
            raise ValueError("every mutation requires an exact revision")
        if (self.action == "extension_record_write") != (self.byte_count is not None):
            raise ValueError("only a write declares secret frame length")
        return self


class ExtensionRecordReply(BaseModel):
    """Metadata only; a present record's bytes follow in one protected frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["extension_record_result"] = "extension_record_result"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    state: Literal["present", "absent", "unreadable", "written", "deleted", "generation", "refused"]
    revision: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    byte_count: Annotated[int, Field(ge=0, le=EXTENSION_RECORD_MAX_BYTES)] = 0
    custody_generation: str | None = None
    records_generation: str | None = None
    refusal: ExtensionRecordRefusal | None = None


class ProfileWorkerExtensionRecordRequest(BaseModel):
    """Runtime-verified installed policy on the private worker control channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["extension_record"] = "extension_record"
    request_id: UUID
    request: ExtensionRecordRequest
    policy: ExtensionRecordCapability

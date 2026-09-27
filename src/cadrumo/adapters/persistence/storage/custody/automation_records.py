"""Current-only internal automation records; private payloads are always sealed."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .....application.user_profile.access_contracts import AuthorityState, AutomationGrant, ProfileAccessBinding
from .....application.user_profile.automation_custody_port import AutomationKeyVerifier
from .....application.user_profile.automation_enrollment import EnrollmentRecord
from .....application.user_profile.automation_lifecycle import AutomationDenial, ProfileGlobalLockState
from .....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

type RecordDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StoredAutomationGrant(BaseModel):
    """Sealed grant facts and its independently protected DEK wrapper."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grant: AutomationGrant
    keys: tuple[AutomationKeyVerifier, ...] = Field(repr=False)
    wrap_key_id: UUID | None
    wrapped_dek: str | None = Field(repr=False)

    @model_validator(mode="after")
    def _custody(self) -> StoredAutomationGrant:
        has_custody = self.grant.state in {AuthorityState.PENDING, AuthorityState.ACTIVE}
        if has_custody != (self.wrap_key_id is not None) or has_custody != (self.wrapped_dek is not None):
            raise ValueError("grant lifecycle does not match unwrap custody")
        return self


class AutomationControlPayload(BaseModel):
    """Complete encrypted profile automation policy at one revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    binding: ProfileAccessBinding
    profile_lock_generation: Annotated[int, Field(ge=0)]
    automation_enabled: bool
    grants: tuple[StoredAutomationGrant, ...] = Field(repr=False)
    requests: tuple[EnrollmentRecord, ...] = Field(default=(), repr=False)
    last_denial: AutomationDenial | None = None

    @model_validator(mode="after")
    def _validate_inventory(self) -> AutomationControlPayload:
        ids = [entry.grant.grant_id for entry in self.grants]
        key_ids = [item.key.key_id for entry in self.grants for item in entry.keys]
        wrap_ids = [entry.wrap_key_id for entry in self.grants if entry.wrap_key_id is not None]
        request_ids = [entry.request_id for entry in self.requests]
        if len(set(request_ids)) != len(request_ids) or any(item.binding != self.binding for item in self.requests):
            raise ValueError("invalid enrollment inventory")
        if len(set(ids)) != len(ids) or len(set(key_ids)) != len(key_ids) or len(set(wrap_ids)) != len(wrap_ids):
            raise ValueError("duplicate automation authority")
        if self.last_denial is not None and self.last_denial.binding != self.binding:
            raise ValueError("denial binding mismatch")
        for entry in self.grants:
            grant = entry.grant
            if grant.binding != self.binding or grant.profile_lock_generation > self.profile_lock_generation:
                raise ValueError("grant binding mismatch")
            for item in entry.keys:
                key = item.key
                if (
                    key.binding != self.binding
                    or key.grant_id != grant.grant_id
                    or key.valid_from < grant.valid_from
                    or key.expires_at > grant.expires_at
                ):
                    raise ValueError("key binding mismatch")
        return self


class AutomationRecordHeader(BaseModel):
    """Nonsecret routing coordinates authenticated as associated data."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    purpose: Literal["cadrumo.automation-control/v1"] = "cadrumo.automation-control/v1"
    record_id: UUID
    profile_id: UUID
    installation_id: UUID
    custody_generation: Annotated[int, Field(ge=1)]
    dek_epoch: UUID
    revision: Annotated[int, Field(ge=1)]


class SealedAutomationControl(BaseModel):
    """Filesystem ciphertext, never a source of unverified authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    header: AutomationRecordHeader
    ciphertext: str = Field(repr=False, min_length=1, max_length=1024 * 1024)


class ControlWitness(BaseModel):
    """Exact immutable record selected by the protected native anchor."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    record_id: UUID
    revision: Annotated[int, Field(ge=1)]
    digest: RecordDigest


class ProtectedControlAnchor(BaseModel):
    """Native-only control key and anti-rollback witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    binding: ProfileAccessBinding
    witness: ControlWitness
    control_key_b64: str = Field(repr=False)


class ControlPublicationIntent(BaseModel):
    """Only safe identities/digests; no key, private payload or unlock material."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    predecessor: ControlWitness | None
    successor: ControlWitness
    created_wrap_keys: tuple[UUID, ...]
    retired_wrap_keys: tuple[UUID, ...]

    @model_validator(mode="after")
    def _ordered_revision(self) -> ControlPublicationIntent:
        if self.successor.revision != (1 if self.predecessor is None else self.predecessor.revision + 1):
            raise ValueError("invalid publication revision")
        return self


class AutomationRetirementIntent(BaseModel):
    """Profile lifecycle denial independent of optional native-store availability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    profile_id: UUID
    installation_id: UUID


class ProfileGlobalLockRecord(ProfileGlobalLockState):
    """Credential-free local fence, independent of protected automation policy."""

    schema_version: Literal[1] = 1
    request_id: UUID | None = None

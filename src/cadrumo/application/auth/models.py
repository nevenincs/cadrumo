"""Canonical persisted authentication contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ...core.time import validate_utc_aware

type _AuthOperationId = Hex64Str
"""Identity of one durable auth operation.

Producers derive it as ``hashlib.sha256(...).hexdigest()``, so the value is
always lowercase hex. The previous length-only bound admitted uppercase and
non-hex strings that no producer can emit, which a resume path would then
fail to match against the operation it was meant to continue.
"""


type CertificateSourceName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
"""Canonical spelling of a named certificate source.

The name is the natural key three separate surfaces derive an identity from:
the ``certificate_sources`` registry dict, the active-source selector, and the
secret-store key. Each of those used to strip independently, so a record
persisted as ``" personal "`` kept its padding in durable state while the
secret backend filed its passphrase under ``"personal"`` — one nominal source
addressed under two spellings, with exact-dict selection unable to resolve the
padded record from the canonical selector. Stripping at the boundary makes the
persisted spelling the canonical one, and ``min_length`` applies *after* the
strip, so a blank-after-strip name is refused rather than stored.
"""


def _require_utc(*values: datetime | None) -> None:
    """Reject any populated timestamp that is not UTC-aware.

    Timestamps on these records are persisted as JSON, which preserves the
    offset, so the canonical contract is enforceable at the model boundary.
    """
    for value in values:
        if value is not None:
            validate_utc_aware(value)


class CertificateSourceRecord(BaseModel):
    """One named, registered PKCS#12 certificate source."""

    model_config = STRICT_FROZEN_CONFIG

    name: CertificateSourceName
    certificate_path: str = Field(min_length=1)
    friendly_name: str | None = None
    registered_at: datetime

    @model_validator(mode="after")
    def _timestamps_are_utc(self) -> CertificateSourceRecord:
        """Reject a registration instant that is naive or not UTC."""
        _require_utc(self.registered_at)
        return self


class AuthCleanupOperationKind(StrEnum):
    """Durable auth cleanup operation kinds."""

    LOGOUT = "logout"
    RESET = "reset"


class AuthCleanupCertificateSource(BaseModel):
    """Version witness for one certificate source captured by auth cleanup."""

    model_config = STRICT_FROZEN_CONFIG

    name: CertificateSourceName
    registered_at: datetime

    @model_validator(mode="after")
    def _timestamps_are_utc(self) -> AuthCleanupCertificateSource:
        """Reject a witness instant that is naive or not UTC."""
        _require_utc(self.registered_at)
        return self


class AuthCleanupIntent(BaseModel):
    """Secret-free durable plan for one resumable operator auth cleanup."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: _AuthOperationId
    operation_kind: AuthCleanupOperationKind
    bucket_id: BucketId
    provider_ids: tuple[str, ...]
    all_providers: bool
    started_at: datetime
    provider_at_start: str | None = None
    configured_at_at_start: datetime | None = None
    authenticated_at_at_start: datetime | None = None
    had_session_state: bool = False
    certificate_path_at_start: str | None = None
    active_certificate_source_at_start: CertificateSourceName | None = None
    certificate_sources: tuple[AuthCleanupCertificateSource, ...] = ()
    provider_configuration_ids: tuple[str, ...] = ()
    session_provider_ids: tuple[str, ...] = ()
    lock_provider_ids: tuple[str, ...] = ()
    secret_source_names: tuple[CertificateSourceName, ...] = ()

    @model_validator(mode="after")
    def _timestamps_are_utc(self) -> AuthCleanupIntent:
        """Reject any populated intent instant that is naive or not UTC."""
        _require_utc(self.started_at, self.configured_at_at_start, self.authenticated_at_at_start)
        return self


class CertificateSecretMutationEventKind(StrEnum):
    """Stable event classifications for certificate-secret mutations."""

    SET = "set"
    ROTATED = "rotated"
    REMOVED = "removed"


class CertificateSecretMutationIntent(BaseModel):
    """Secret-free durable plan for one resumable certificate-secret mutation."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: _AuthOperationId
    bucket_id: BucketId
    source_name: CertificateSourceName
    event_kind: CertificateSecretMutationEventKind
    started_at: datetime
    prior_present: bool
    request_witness: Hex64Str | None = None
    completion_witness: str | None = None

    @model_validator(mode="after")
    def _timestamps_are_utc(self) -> CertificateSecretMutationIntent:
        """Reject a mutation start instant that is naive or not UTC."""
        _require_utc(self.started_at)
        return self


class AuthState(BaseModel):
    """Persisted local AEAT access readiness embedded in workflow state."""

    model_config = STRICT_FROZEN_CONFIG

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None
    certificate_sources: dict[CertificateSourceName, CertificateSourceRecord] = Field(default_factory=dict)
    active_certificate_source: CertificateSourceName | None = None
    cleanup_intent: AuthCleanupIntent | None = None
    certificate_secret_mutation_intent: CertificateSecretMutationIntent | None = None

    @model_validator(mode="after")
    def _timestamps_are_utc(self) -> AuthState:
        """Reject any populated auth-state instant that is naive or not UTC."""
        _require_utc(self.configured_at, self.authenticated_at)
        return self


__all__ = [
    "AuthCleanupCertificateSource",
    "AuthCleanupIntent",
    "AuthCleanupOperationKind",
    "AuthState",
    "CertificateSecretMutationEventKind",
    "CertificateSecretMutationIntent",
    "CertificateSourceName",
    "CertificateSourceRecord",
]

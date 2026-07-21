"""Internal definitions for workflow-owned persisted authentication records.

The public contract is exported by :mod:`application.workflow`. This shared
leaf defines :class:`AuthState`, :class:`CertificateSourceRecord`, and the
durable cleanup and certificate-secret mutation intents without creating an
import cycle between workflow persistence and auth services.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG


class CertificateSourceRecord(BaseModel):
    """One named, registered PKCS#12 certificate source."""

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1, max_length=160)
    certificate_path: str = Field(min_length=1)
    friendly_name: str | None = None
    registered_at: datetime


class AuthCleanupOperationKind(StrEnum):
    """Durable auth cleanup operation kinds."""

    LOGOUT = "logout"
    RESET = "reset"


class AuthCleanupCertificateSource(BaseModel):
    """Version witness for one certificate source captured by auth cleanup."""

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1, max_length=160)
    registered_at: datetime


class AuthCleanupIntent(BaseModel):
    """Secret-free durable plan for one resumable operator auth cleanup."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: str = Field(min_length=64, max_length=64)
    operation_kind: AuthCleanupOperationKind
    bucket_id: str = Field(min_length=1)
    provider_ids: tuple[str, ...]
    all_providers: bool
    started_at: datetime
    provider_at_start: str | None = None
    configured_at_at_start: datetime | None = None
    authenticated_at_at_start: datetime | None = None
    had_session_state: bool = False
    certificate_path_at_start: str | None = None
    active_certificate_source_at_start: str | None = None
    certificate_sources: tuple[AuthCleanupCertificateSource, ...] = ()
    provider_configuration_ids: tuple[str, ...] = ()
    session_provider_ids: tuple[str, ...] = ()
    lock_provider_ids: tuple[str, ...] = ()
    secret_source_names: tuple[str, ...] = ()


class CertificateSecretMutationEventKind(StrEnum):
    """Stable event classifications for certificate-secret mutations."""

    SET = "set"
    ROTATED = "rotated"
    REMOVED = "removed"


class CertificateSecretMutationIntent(BaseModel):
    """Secret-free durable plan for one resumable certificate-secret mutation."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: str = Field(min_length=64, max_length=64)
    bucket_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1, max_length=160)
    event_kind: CertificateSecretMutationEventKind
    started_at: datetime
    prior_present: bool
    request_witness: str | None = Field(default=None, min_length=64, max_length=64)
    completion_witness: str | None = None


class AuthState(BaseModel):
    """Persisted local AEAT access readiness embedded in workflow state."""

    model_config = STRICT_FROZEN_CONFIG

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None
    certificate_sources: dict[str, CertificateSourceRecord] = Field(default_factory=dict)
    active_certificate_source: str | None = None
    cleanup_intent: AuthCleanupIntent | None = None
    certificate_secret_mutation_intent: CertificateSecretMutationIntent | None = None

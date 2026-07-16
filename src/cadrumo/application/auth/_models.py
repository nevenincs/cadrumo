"""Strict pydantic v2 records for AEAT auth readiness.

:class:`AuthState` is the workflow-state auth snapshot embedded in
:class:`application.workflow.WorkflowState` and updated by
:func:`application.auth.update_auth`. Operator-facing status and test
surfaces expose redacted readiness through
:class:`application.state_projection.ProjectionAuthReadiness` rather than
re-reading this model independently.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG


class CertificateSourceRecord(BaseModel):
    """One named, registered PKCS#12 certificate source.

    A gestor managing several entities (their own personal certificate
    plus one or more apoderado certificates) registers each certificate
    under a distinct ``name`` so the active one can be selected without
    re-supplying the filesystem path. Only the filesystem reference is
    stored here; certificate passwords, private keys, and session
    material never enter this record (or any persisted workflow
    state), matching the existing single-certificate contract.

    Attributes:
        name: Operator-chosen identifier for this certificate source
            (e.g. ``"personal"``, ``"apoderado-empresa-x"``). Unique
            within the active profile's registry.
        certificate_path: Filesystem path to the PKCS#12 (.p12/.pfx)
            bundle.
        friendly_name: Optional human-readable label distinct from
            ``name``, mirroring
            :attr:`core.config.Settings.cadrumo_certificate_friendly_name`.
        registered_at: UTC timestamp the source was registered or last
            re-pointed at a different path.
    """

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
    """Persisted local AEAT access readiness state.

    This record stores provider selection, the certificate filesystem
    reference, and local session timestamps inside
    :class:`application.workflow.WorkflowState`. Public CLI emit shapes
    read the canonical projection into
    :class:`application.auth.AuthStatusResult` and
    :class:`application.auth.AuthTestResult`.

    ``certificate_sources`` and ``active_certificate_source`` extend the
    single-certificate contract with a named multi-certificate registry:
    an operator (typically a gestor) may register several PKCS#12
    sources — one per entity they act for — and select which one is
    active. ``certificate_path`` remains the single field the rest of
    the auth surface (backend probes, live login, health reporting)
    reads; selecting an active source mirrors its path onto
    ``certificate_path`` so every existing consumer keeps working
    unchanged.
    """

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

"""Resolve the active certificate credential from settings and workflow state."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import SecretStr

from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ..auth_credentials import (
    ActiveCertificateCredentials,
    unnamed_certificate_credentials,
)
from ._certificate_secret_backend import SecureStorageCertificateSecretBackend
from ._certificate_sources import active_certificate_source
from ._operator_scope import active_profile_storage_span

if TYPE_CHECKING:
    from ..workflow import WorkflowState, WorkflowStateRepository


def _workflow_state_repository() -> WorkflowStateRepository:
    """Resolve the public workflow repository without loading workflow at auth import time."""
    workflow = import_module("cadrumo.application.workflow")
    factory = cast(Callable[[], object], workflow.workflow_state_repository)
    return cast("WorkflowStateRepository", factory())


def resolve_certificate_source_secret(
    *,
    name: str,
    bucket_id: str,
    settings: Settings | None = None,
) -> SecretStr | None:
    """Return the passphrase registered for certificate source ``name``."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=bucket_id, settings=settings)
    return backend.get(name)


def _resolve_named_certificate_source_secret(
    *,
    name: str,
    bucket_id: str,
    settings: Settings,
) -> SecretStr | None:
    """Resolve one named secret through secure storage, failing closed on read errors."""
    try:
        return resolve_certificate_source_secret(
            name=name,
            bucket_id=bucket_id,
            settings=settings,
        )
    except (OSError, AeatError):
        return None


@dataclass(frozen=True, slots=True)
class ActiveAuthProjectionSnapshot:
    """Route-witnessed workflow state and certificate credential projection."""

    bucket_id: str | None
    state: WorkflowState | None
    certificate_credentials: ActiveCertificateCredentials | None


def _resolve_witnessed_certificate_credentials(
    state: WorkflowState,
    *,
    bucket_id: str,
    settings: Settings,
) -> ActiveCertificateCredentials:
    """Bind a secret to certificate metadata loaded from the witnessed bucket."""
    credentials = project_active_certificate_credentials(state, settings=settings)
    if credentials.source_name is None:
        return credentials
    password = _resolve_named_certificate_source_secret(
        name=credentials.source_name,
        bucket_id=bucket_id,
        settings=settings,
    )
    return credentials.model_copy(update={"password": password})


@contextmanager
def active_auth_projection_span(
    *,
    settings: Settings | None = None,
    requested_provider: str | None = None,
) -> Iterator[ActiveAuthProjectionSnapshot]:
    """Pin one active route while loading state, credentials, and their consumers."""
    resolved = settings or load_settings()
    with active_profile_storage_span(resolved) as bucket_id:
        if bucket_id is None:
            yield ActiveAuthProjectionSnapshot(
                bucket_id=None,
                state=None,
                certificate_credentials=None,
            )
            return
        from ...core.config import override_settings

        with override_settings(cadrumo_active_profile=bucket_id):
            state = _workflow_state_repository().load()
            provider = (requested_provider or state.auth.provider or "").strip().lower()
            credentials = (
                _resolve_witnessed_certificate_credentials(
                    state,
                    bucket_id=bucket_id,
                    settings=resolved,
                )
                if provider == "certificate"
                else None
            )
            yield ActiveAuthProjectionSnapshot(
                bucket_id=bucket_id,
                state=state,
                certificate_credentials=credentials,
            )


def resolve_active_certificate_credentials(
    *,
    settings: Settings | None = None,
) -> ActiveCertificateCredentials:
    """Resolve the exact certificate credential selected for the active profile."""
    resolved = settings or load_settings()
    try:
        with active_auth_projection_span(
            settings=resolved,
            requested_provider="certificate",
        ) as snapshot:
            if snapshot.state is None:
                return unnamed_certificate_credentials(resolved)
            return snapshot.certificate_credentials or ActiveCertificateCredentials()
    except (OSError, AeatError):
        return ActiveCertificateCredentials()


def project_active_certificate_credentials(
    state: WorkflowState,
    *,
    settings: Settings,
) -> ActiveCertificateCredentials:
    """Project selected certificate metadata without reading secure storage.

    Caller-supplied workflow state carries no storage-route provenance.  This
    boundary therefore never accepts a bucket identifier and always leaves a
    selected named source's password absent.  Secret-bearing credentials must
    be obtained through :func:`resolve_active_certificate_credentials`, which
    loads the workflow state inside its own witnessed active-profile span.
    """
    active_record = active_certificate_source(state)
    if active_record is None:
        certificate_path = settings.cadrumo_certificate_path
        if certificate_path is None and state.auth.certificate_path:
            certificate_path = Path(state.auth.certificate_path)
        credentials = unnamed_certificate_credentials(settings)
        return credentials.model_copy(update={"certificate_path": certificate_path})
    return ActiveCertificateCredentials(
        certificate_path=Path(active_record.certificate_path),
        password=None,
        friendly_name=active_record.friendly_name,
        source_name=active_record.name,
    )


__all__ = [
    "ActiveAuthProjectionSnapshot",
    "active_auth_projection_span",
    "project_active_certificate_credentials",
    "resolve_active_certificate_credentials",
    "resolve_certificate_source_secret",
]

"""A served runtime over one enrolled profile, with the native login observation as the only test port."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from .served_runtime import ServedRuntime, serving_runtime
from .test_profile_connections import LoginObservation


@dataclass(frozen=True)
class ServedProfile:
    """The running runtime with the endpoint, enrolled subject and profile a test signs in to."""

    served: ServedRuntime
    root: Path
    endpoint: WindowsEndpoint
    subject: AdministrationSubject
    profile_id: UUID


@contextmanager
def serving_enrolled_profile(tmp_path: Path, *, workers: int = 1, ready_seconds: float = 3) -> Generator[ServedProfile]:
    """Enrol one profile under a fresh storage root and serve it until the scope ends."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        observation = LoginObservation(owner_id())
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: observation,
            secret_store=lambda: subject.native,
            workers=workers,
            ready_seconds=ready_seconds,
        ) as served:
            yield ServedProfile(served=served, root=root, endpoint=endpoint, subject=subject, profile_id=profile_id)

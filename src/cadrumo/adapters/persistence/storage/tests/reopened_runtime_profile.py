"""Re-open an already-provisioned test bucket without paying for its registration again.

:func:`secure_sql.isolated_runtime_profile` holds process-global settings and an
active session for its whole lifetime, so a module-scoped use leaks that bucket
into every later test of the module. A module fixture can instead provision and
seed once, let that context close, and keep only the durable root; each test
then re-enters settings and a session over the same root. Opening a session
derives the test key directly, so the registration key-derivation is not repeated.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .....application.user_profile.profile_record_repository import close_active_profile_record_session
from .....core.config import load_settings, override_settings
from ..bucket.directory_layout import bucket_paths
from ..master_key.active_session import activate_session
from ..master_key.bucket_session import BucketSession
from ..runtime import inspect_storage_runtime
from ..runtime_repository import secure_object_repository_for_active_bucket
from ..sql.engine import dispose_engine
from ..sql.secure_objects import SecureObjectRepository
from .profile_capsule_runtime import derive_test_bucket_key
from .secure_sql import TestRuntimeProfile, reap_profile_session_keys


@dataclass(frozen=True, slots=True)
class DurableRuntimeProfile:
    """The on-disk part of a provisioned test bucket, with no live global context."""

    storage_root: Path
    bucket_id: str


@contextmanager
def reopened_runtime_profile(
    durable: DurableRuntimeProfile,
    *,
    prepare: Callable[[SecureObjectRepository], None] | None = None,
) -> Generator[TestRuntimeProfile]:
    """Enter settings and an active session over ``durable`` for the span of one test.

    ``prepare`` runs once the repository is live, to return the store to a known state.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password
    opened_at = datetime.now(UTC).replace(microsecond=0)
    with override_settings(
        cadrumo_storage_root=durable.storage_root,
        cadrumo_active_profile=durable.bucket_id,
        cadrumo_profile_kdf_measure_calibration=False,
        cadrumo_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        session = BucketSession.open_resumed(
            bucket_id=durable.bucket_id,
            dek=derive_test_bucket_key(durable.bucket_id, purpose="dek"),
            idle_minutes=15,
            opened_at=opened_at,
            idle_deadline=opened_at + timedelta(minutes=15),
            absolute_deadline=opened_at + timedelta(minutes=240),
            storage_root=durable.storage_root,
        )
        with activate_session(session):
            runtime = inspect_storage_runtime(settings)
            repository = secure_object_repository_for_active_bucket()
            try:
                if prepare is not None:
                    prepare(repository)
                yield TestRuntimeProfile(
                    storage_root=durable.storage_root,
                    bucket_id=durable.bucket_id,
                    paths=bucket_paths(durable.storage_root, durable.bucket_id),
                    settings=settings,
                    runtime=runtime,
                    repository=repository,
                )
            finally:
                close_active_profile_record_session()
                session.close()
                reap_profile_session_keys(durable.storage_root)

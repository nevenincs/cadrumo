"""Shared secure SQL isolation helpers for tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from ..adapters.persistence.storage import EphemeralMasterKeyProvider
from ..adapters.persistence.storage.bucket._layout import BucketPaths, provision_bucket_directory
from ..adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus, BucketManifest
from ..adapters.persistence.storage.bucket._manifest_io import write_manifest
from ..adapters.persistence.storage.master_key._active_session import activate_session
from ..adapters.persistence.storage.master_key._bucket_session import BucketSession
from ..adapters.persistence.storage.master_key._kdf_params import KdfParams
from ..adapters.persistence.storage.runtime import StorageRuntime, inspect_storage_runtime
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ..adapters.persistence.storage.sql.engine import dispose_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..core.config import Settings, load_settings, override_settings

_TEST_KEK = b"t" * 32
_TEST_DEK = b"r" * 32
# Distinct test KEK/DEK for the secondary bucket in the
# multi-bucket fixture. Authored per
# ``2026-06-03-multi-bucket-test-fixture-adr`` so an accidental
# cross-bucket key reuse in production code surfaces as a test
# failure rather than a same-key collision.
_TEST_KEK_SECONDARY = b"u" * 32
_TEST_DEK_SECONDARY = b"s" * 32


@dataclass(frozen=True)
class TestRuntimeProfile:
    """Real active-profile storage runtime created for tests."""

    __test__: ClassVar[bool] = False

    storage_root: Path
    bucket_id: str
    paths: BucketPaths
    settings: Settings
    runtime: StorageRuntime
    repository: SecureObjectRepository


def dev_test_database_password(settings: Settings | None = None) -> str:
    """Return the shared dev/test password for database-backed storage tests."""

    source = settings or load_settings()
    return source.aeat_dev_test_database_password.get_secret_value()


@contextmanager
def isolated_ephemeral_secure_sql(
    *,
    tmp_path: Path,
    database_name: str = "aeat.db",
) -> Iterator[None]:
    """Run test code with a temp SQL database and real ephemeral master key."""

    database_url = f"sqlite:///{(tmp_path / database_name).as_posix()}"
    with override_settings(
        aeat_database_url=database_url,
        aeat_secret_passphrase=load_settings().aeat_dev_test_database_password,
    ) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider():
            try:
                yield
            finally:
                dispose_engine(settings)


@contextmanager
def isolated_sessionless_storage_root(*, tmp_path: Path) -> Iterator[Path]:
    """Run tests against an empty storage root with no active bucket session.

    Unlike :func:`isolated_profile_storage_root`, this helper does not
    start an :class:`EphemeralMasterKeyProvider` session. It is for tests
    that assert ``has_active_bucket_session() is False`` — the bootstrap-
    exempt repair verbs, cold-start refusal tests, and fast-path surfaces
    that must all operate without an active session.
    """

    storage_root = tmp_path / "aeat-storage"
    with override_settings(aeat_local_storage_root=storage_root, aeat_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield storage_root
        finally:
            dispose_engine(settings)


@contextmanager
def isolated_profile_storage_root(*, tmp_path: Path) -> Iterator[Path]:
    """Run profile-bootstrap tests against an empty real storage root.

    Unlike :func:`isolated_runtime_profile`, this helper does not
    provision a bucket or activate an ``aeat_active_profile`` route.
    It is for tests that exercise the profile creation path itself,
    where the system under test must create the bucket directory,
    manifest, pointer, and per-bucket database.

    The file backend is configured with the dev-test passphrase so
    ``get_master_key_provider()`` calls inside ``profile create`` and
    related verbs resolve a working provider without needing
    ``AEAT_SECRET_STORE_BACKEND=unsecured``.
    """

    storage_root = tmp_path / "aeat-storage"
    secret_store_dir = tmp_path / "secrets"
    passphrase = load_settings().aeat_dev_test_database_password
    with override_settings(
        aeat_local_storage_root=storage_root,
        aeat_active_profile=None,
        aeat_secret_store_backend="file",
        aeat_secret_store_dir=secret_store_dir,
        aeat_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        try:
            yield storage_root
        finally:
            dispose_engine(settings)


@contextmanager
def isolated_runtime_profile(
    *,
    tmp_path: Path,
    bucket_id: str = "test-runtime-profile",
    label: str = "Test runtime profile",
) -> Iterator[TestRuntimeProfile]:
    """Create a real active-profile bucket runtime for tests.

    The helper provisions the same durable surfaces used by production:
    a bucket directory, plaintext manifest, active-profile settings route,
    active bucket session, and runtime-owned secure-object repository.
    """

    storage_root = tmp_path / "aeat-storage"
    opened_at = datetime.now(UTC).replace(microsecond=0)
    paths = provision_bucket_directory(storage_root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=opened_at,
            last_unlocked_at=opened_at,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=_TEST_KEK,
        dek=_TEST_DEK,
        idle_minutes=15,
        opened_at=opened_at,
    )

    with override_settings(aeat_local_storage_root=storage_root, aeat_active_profile=bucket_id) as settings:
        dispose_engine(settings)
        with activate_session(session):
            runtime = inspect_storage_runtime(settings)
            repository = secure_object_repository_for_active_bucket()
            try:
                yield TestRuntimeProfile(
                    storage_root=storage_root,
                    bucket_id=bucket_id,
                    paths=paths,
                    settings=settings,
                    runtime=runtime,
                    repository=repository,
                )
            finally:
                dispose_engine(settings)


@dataclass(frozen=True)
class MultiBucketTestRuntime:
    """Two co-existing test runtime profiles for active-vs-target scenarios.

    ``primary`` is ``aeat_active_profile`` when the fixture yields.
    ``secondary`` is provisioned with its own bucket directory,
    manifest, keystore, and secure-object repository but its
    session is held in this dataclass for the
    :meth:`switch_to_secondary` context manager to activate
    on demand. Authority: ``2026-06-03-multi-bucket-test-fixture-adr``.
    """

    __test__: ClassVar[bool] = False

    primary: TestRuntimeProfile
    secondary: TestRuntimeProfile
    _secondary_session: BucketSession

    @contextmanager
    def switch_to_secondary(self) -> Iterator[None]:
        """Swap the active profile to ``secondary`` for the block's duration.

        Restores ``primary`` as active on exit so the outer test
        scope sees the same active profile it started with. Tests
        that operate against the secondary via
        ``BucketMaintenanceService`` do NOT need this — the service
        opens its own scoped session through
        ``profile_storage_session``; this helper is for tests that
        need direct repository access against the secondary.
        """
        with (
            override_settings(aeat_active_profile=self.secondary.bucket_id),
            activate_session(self._secondary_session),
        ):
            yield


@contextmanager
def isolated_two_bucket_runtime(
    *,
    tmp_path: Path,
    primary_bucket_id: str = "primary-test-runtime",
    secondary_bucket_id: str = "secondary-test-runtime",
    primary_label: str = "Primary test runtime",
    secondary_label: str = "Secondary test runtime",
) -> Iterator[MultiBucketTestRuntime]:
    """Provision two buckets sharing a storage root; primary is active.

    The fixture is the operator-active-vs-target distinction that
    :class:`BucketMaintenanceService.delete` requires (the service's
    active-bucket guard refuses self-deletion by design), and the
    cross-host-migration distinction that the sealed-archive
    export/import round-trip requires. See
    ``2026-06-03-multi-bucket-test-fixture-adr`` for the design
    rationale.

    Both buckets carry distinct test KEK/DEK material
    (``_TEST_KEK`` / ``_TEST_KEK_SECONDARY``) so an accidental
    cross-bucket key reuse in production code surfaces as a test
    failure rather than a same-key collision.
    """
    storage_root = tmp_path / "aeat-storage"
    opened_at = datetime.now(UTC).replace(microsecond=0)

    primary_paths = provision_bucket_directory(storage_root, primary_bucket_id)
    write_manifest(
        primary_paths,
        BucketManifest(
            bucket_id=primary_bucket_id,
            label=primary_label,
            created_at=opened_at,
            last_unlocked_at=opened_at,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    primary_session = BucketSession.open(
        bucket_id=primary_bucket_id,
        kek=_TEST_KEK,
        dek=_TEST_DEK,
        idle_minutes=15,
        opened_at=opened_at,
    )

    secondary_paths = provision_bucket_directory(storage_root, secondary_bucket_id)
    write_manifest(
        secondary_paths,
        BucketManifest(
            bucket_id=secondary_bucket_id,
            label=secondary_label,
            created_at=opened_at,
            last_unlocked_at=opened_at,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    secondary_session = BucketSession.open(
        bucket_id=secondary_bucket_id,
        kek=_TEST_KEK_SECONDARY,
        dek=_TEST_DEK_SECONDARY,
        idle_minutes=15,
        opened_at=opened_at,
    )

    with override_settings(
        aeat_local_storage_root=storage_root,
        aeat_active_profile=primary_bucket_id,
    ) as settings:
        dispose_engine(settings)
        with activate_session(primary_session):
            runtime = inspect_storage_runtime(settings)
            primary_repository = secure_object_repository_for_active_bucket()
            primary_profile = TestRuntimeProfile(
                storage_root=storage_root,
                bucket_id=primary_bucket_id,
                paths=primary_paths,
                settings=settings,
                runtime=runtime,
                repository=primary_repository,
            )
            # Resolve the secondary's repository under its session so
            # tests can hold a direct handle without re-activating.
            with override_settings(aeat_active_profile=secondary_bucket_id) as secondary_settings:
                dispose_engine(secondary_settings)
                with activate_session(secondary_session):
                    secondary_runtime = inspect_storage_runtime(secondary_settings)
                    secondary_repository = secure_object_repository_for_active_bucket()
            secondary_profile = TestRuntimeProfile(
                storage_root=storage_root,
                bucket_id=secondary_bucket_id,
                paths=secondary_paths,
                settings=settings,
                runtime=secondary_runtime,
                repository=secondary_repository,
            )
            try:
                yield MultiBucketTestRuntime(
                    primary=primary_profile,
                    secondary=secondary_profile,
                    _secondary_session=secondary_session,
                )
            finally:
                dispose_engine(settings)


@contextmanager
def isolated_cli_runtime_profile(
    *,
    tmp_path: Path,
    bucket_id: str = "test-runtime-profile",
    label: str = "Test runtime profile",
) -> Iterator[TestRuntimeProfile]:
    """Create a real runtime profile with CLI-adjacent directories isolated.

    CLI work-unit tests need the active bucket database plus the
    filesystem directories read from settings for runs, drafts, tokens,
    financial transactions, and invoices. Keep that setup on the central
    settings surface instead of per-test environment mutation.
    """

    with (
        override_settings(
            aeat_runs_dir=tmp_path / "runs",
            aeat_drafts_dir=tmp_path / "drafts",
            aeat_token_dir=tmp_path / "tokens",
            aeat_financial_txs_dir=tmp_path / "txs",
            aeat_invoices_dir=tmp_path / "invoices",
        ),
        isolated_runtime_profile(
            tmp_path=tmp_path,
            bucket_id=bucket_id,
            label=label,
        ) as profile,
    ):
        dispose_engine(profile.settings)
        yield profile


__all__ = [
    "MultiBucketTestRuntime",
    "TestRuntimeProfile",
    "dev_test_database_password",
    "isolated_cli_runtime_profile",
    "isolated_ephemeral_secure_sql",
    "isolated_profile_storage_root",
    "isolated_runtime_profile",
    "isolated_sessionless_storage_root",
    "isolated_two_bucket_runtime",
]

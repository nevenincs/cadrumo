"""Shared secure SQL isolation helpers for tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from ..adapters.persistence.storage import EphemeralMasterKeyProvider
from ..adapters.persistence.storage.bucket import (
    BucketKeySchedule,
    BucketLifecycleStatus,
    BucketManifest,
    write_manifest,
)
from ..adapters.persistence.storage.bucket._layout import BucketPaths, provision_bucket_directory
from ..adapters.persistence.storage.master_key import (
    KdfParams,
    activate_session,
    get_master_key_provider,
)
from ..adapters.persistence.storage.master_key._bucket_session import BucketSession
from ..adapters.persistence.storage.master_key._master_key_bucket_dek import load_or_mint_bucket_dek
from ..adapters.persistence.storage.runtime import StorageRuntime, inspect_storage_runtime
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ..adapters.persistence.storage.sql.engine import dispose_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..core.config import Settings, load_settings, override_settings

_DEFAULT_RUNTIME_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_DEFAULT_PRIMARY_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_DEFAULT_SECONDARY_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


def _provision_bucket_dek_v1_session(
    *,
    bucket_id: str,
    label: str,
    storage_root: Path,
    opened_at: datetime,
) -> tuple[BucketSession, BucketPaths]:
    """Provision a genuine ``bucket-dek-v1`` bucket and open its session.

    Mirrors the production mint sequence (``ProfileRepository.create``
    inside ``profile_create_storage_span``): resolve the configured
    master-key provider, mint the per-bucket wrapped DEK under that
    provider's resolved key-encryption key (KEK), write the manifest in
    the ``BUCKET_DEK_V1`` schedule, then open a session keyed by the same
    KEK and the minted DEK.

    The caller MUST have already entered an ``override_settings`` block
    that configures the file backend, secret-store directory, and
    dev-test passphrase (as :func:`isolated_profile_storage_root` does),
    so the provider this helper resolves is the same one a nested
    :func:`profile_storage_session` re-resolves on the read path. That
    consistency is what lets the wrapped DEK unwrap under the
    provider-resolved KEK rather than a divergent raw test key.
    """
    from ..adapters.persistence.storage.errors import MasterKeyMaterialMissingError, SecretAlreadyExistsError

    paths = provision_bucket_directory(storage_root, bucket_id)
    provider = get_master_key_provider()
    try:
        master_key = provider.get_master_key()
    except MasterKeyMaterialMissingError:
        try:
            master_key = provider.provision_master_key()
        except SecretAlreadyExistsError:
            master_key = provider.get_master_key()
    # Mint the wrapped DEK before the manifest exists so the bootstrap
    # branch of ``load_or_mint_bucket_dek`` writes the keystore file and
    # returns a fresh DEK, exactly as the production create span does.
    dek = load_or_mint_bucket_dek(
        kek=master_key,
        storage_root=storage_root,
        bucket_id=bucket_id,
        allow_bootstrap_mint=True,
    )
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=opened_at,
            last_unlocked_at=opened_at,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
            schema_version=2,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=master_key,
        dek=dek,
        idle_minutes=15,
        opened_at=opened_at,
    )
    return session, paths


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


def read_db_at_rest_bytes(db_path: Path) -> bytes:
    """Return the full on-disk SQLite footprint for an at-rest plaintext scan.

    The bucket databases run in WAL mode (``PRAGMA journal_mode=WAL``), so a
    just-committed row lives in the ``<db>-wal`` sidecar until a checkpoint
    folds it into the main database file. An at-rest plaintext scan that reads
    only the main ``.db`` file would miss those rows and pass *tautologically* —
    "no plaintext leaked" would hold simply because the data is not in the file
    being scanned. Concatenating the main file with its ``-wal`` sidecar makes
    the scan cover every committed byte regardless of checkpoint state, which
    strengthens (never weakens) the leak assertion.

    The ``-shm`` shared-memory index carries no row payload and is omitted.
    """
    data = db_path.read_bytes()
    wal_path = db_path.with_name(db_path.name + "-wal")
    if wal_path.exists():
        data += wal_path.read_bytes()
    return data


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
    bucket_id: str = _DEFAULT_RUNTIME_BUCKET_ID,
    label: str = "Test runtime profile",
) -> Iterator[TestRuntimeProfile]:
    """Create a real active-profile bucket runtime for tests.

    The helper provisions the same durable surfaces used by production:
    a bucket directory, plaintext manifest, separated per-bucket wrapped
    DEK, active-profile settings route, active bucket session, and
    runtime-owned secure-object repository.

    The bucket is a genuine ``BUCKET_DEK_V1`` bucket: the file backend is
    configured with the dev-test passphrase (as
    :func:`isolated_profile_storage_root` does) so the wrapped DEK is
    minted under, and unwraps under, the same master-key provider a
    nested :func:`profile_storage_session` re-resolves on the read path.
    """

    storage_root = tmp_path / "aeat-storage"
    secret_store_dir = tmp_path / "secrets"
    passphrase = load_settings().aeat_dev_test_database_password
    opened_at = datetime.now(UTC).replace(microsecond=0)

    with override_settings(
        aeat_local_storage_root=storage_root,
        aeat_active_profile=bucket_id,
        aeat_secret_store_backend="file",
        aeat_secret_store_dir=secret_store_dir,
        aeat_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        session, paths = _provision_bucket_dek_v1_session(
            bucket_id=bucket_id,
            label=label,
            storage_root=storage_root,
            opened_at=opened_at,
        )
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
    primary_bucket_id: str = _DEFAULT_PRIMARY_BUCKET_ID,
    secondary_bucket_id: str = _DEFAULT_SECONDARY_BUCKET_ID,
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

    Both buckets are genuine ``BUCKET_DEK_V1`` buckets that share the
    storage root's single file-backend master key (the key-encryption
    key, KEK) but mint their own separated per-bucket data-encryption
    key (DEK) — the production custody shape, where many buckets under
    one storage root share one ``master.key`` and each keeps its own
    wrapped DEK. The per-bucket DEK distinctness means an accidental
    cross-bucket DEK reuse in production code still surfaces as a test
    failure. See ``2026-06-03-multi-bucket-test-fixture-adr``.
    """
    storage_root = tmp_path / "aeat-storage"
    secret_store_dir = tmp_path / "secrets"
    passphrase = load_settings().aeat_dev_test_database_password
    opened_at = datetime.now(UTC).replace(microsecond=0)

    with override_settings(
        aeat_local_storage_root=storage_root,
        aeat_active_profile=primary_bucket_id,
        aeat_secret_store_backend="file",
        aeat_secret_store_dir=secret_store_dir,
        aeat_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        primary_session, primary_paths = _provision_bucket_dek_v1_session(
            bucket_id=primary_bucket_id,
            label=primary_label,
            storage_root=storage_root,
            opened_at=opened_at,
        )
        secondary_session, secondary_paths = _provision_bucket_dek_v1_session(
            bucket_id=secondary_bucket_id,
            label=secondary_label,
            storage_root=storage_root,
            opened_at=opened_at,
        )
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
    bucket_id: str = _DEFAULT_RUNTIME_BUCKET_ID,
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

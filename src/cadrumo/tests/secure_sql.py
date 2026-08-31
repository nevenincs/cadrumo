"""Shared secure SQL isolation helpers for tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from uuid import UUID

import pytest
from sqlalchemy import Engine, Select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text

from ..adapters.persistence.storage.bucket.directory_layout import BucketPaths
from ..adapters.persistence.storage.crypto.encrypted_columns import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ..adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from ..adapters.persistence.storage.master_key.active_session import activate_session
from ..adapters.persistence.storage.master_key.bucket_session import BucketSession
from ..adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..adapters.persistence.storage.runtime import StorageRuntime, inspect_storage_runtime
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ..adapters.persistence.storage.sql._orm import Base, SecureObjectRow
from ..adapters.persistence.storage.sql.engine import create_engine_from_settings, dispose_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..adapters.persistence.storage.sql.session import session_scope
from ..adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME, KEYSTORE_DIRNAME
from ..adapters.persistence.storage.tests.profile_capsule_runtime import provision_test_profile_bucket_session
from ..core.config import Settings, load_settings, override_settings
from ..core.directory_scan import DirectoryEntryKind, scan_directory
from ..core.errors.hierarchy import CadrumoError
from ..core.storage_taxonomy import StorageCategory
from .master_key import EphemeralMasterKeyProvider
from .storage_scope import storage_overrides

_DEFAULT_RUNTIME_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_DEFAULT_PRIMARY_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_DEFAULT_SECONDARY_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


def reap_profile_session_keys(storage_root: Path) -> None:
    """Revoke every current session receipt discoverable under ``storage_root``.

    A login mints a random session key into the OS keychain under the
    service ``cadrumo:profile-session:v2``, paired with its random session
    UUID; production reaps it on logout and on profile destruction. A test's storage root is
    a temporary directory that is simply discarded, so nothing there ever
    reaches a reap path — and because every run mints a FRESH bucket uuid,
    each such test leaves one more permanent orphan behind in the
    operator's real credential store. Enough of them saturate the store
    and ``CredWrite`` starts failing host-wide, which breaks login for the
    developer running the suite.

    Profile UUID candidates are recovered from the two durable directories a
    capsule owns under the root.  The product deletion operation then reads
    the strict receipt and addresses only its named ``profile_id/session_id``
    entry; teardown never recreates the retired global-account API.

    Best-effort by construction: a missing entry is already a no-op in
    :func:`delete_profile_session`, a root that was never populated
    enumerates to nothing, and a directory whose name is not a bucket
    identity is skipped. Teardown must never fail a passing test nor mask
    a failing one.

    Args:
        storage_root: The Cadrumo storage root whose buckets to reap.
    """
    bucket_ids: set[str] = set()
    for parent in (storage_root / BUCKETS_DIRNAME, storage_root / KEYSTORE_DIRNAME):
        try:
            entries = scan_directory(parent, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        except OSError:
            continue
        bucket_ids.update(entry.name for entry in entries)
    for bucket_id in bucket_ids:
        try:
            delete_profile_session(storage_root=storage_root, profile_id=UUID(bucket_id))
        except (CadrumoError, ValueError):
            # A directory name that is not a canonical profile UUID never
            # names a current receipt, so there is nothing to revoke.
            continue


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
    """Return the shared test password for database-backed storage tests."""

    source = settings or load_settings()
    return source.cadrumo_dev_test_database_password.get_secret_value()


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


def mutate_encrypted_secure_object_json(
    engine: Engine,
    *,
    row_statement: Select[tuple[SecureObjectRow]],
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Mutate one real secure-object JSON document while preserving its AEAD binding.

    Callers retain the SQL row selection and the domain-specific document
    mutation. This test-support seam only performs the mechanical boundary
    operation required for an honest persisted-payload proof: decrypt the
    selected row using its actual identity-bound associated data, mutate the
    decoded JSON document, and re-encrypt it under that unchanged binding.
    """
    with session_scope(engine) as session:
        row = session.execute(row_statement).scalar_one()
        associated_data = secure_object_payload_aad(
            row.namespace,
            bytes(row.object_key),
            row.schema_version,
        )
        document = json.loads(
            decrypt_secure_object_payload(
                bytes(row.payload),
                associated_data=associated_data,
            ).decode("utf-8"),
        )
        assert isinstance(document, dict), "encrypted secure-object payload must decode to a JSON object"
        mutate(document)
        row.payload = encrypt_secure_object_payload(
            json.dumps(document).encode("utf-8"),
            associated_data=associated_data,
        )


def reset_secure_object_store(repository: SecureObjectRepository) -> None:
    """Truncate every per-test row from a shared bucket's secure-object store.

    This is the load-bearing teardown that lets a MODULE-scoped
    :func:`isolated_runtime_profile` be reused across the tests in a module
    without on-disk state bleed. The expensive bucket provisioning — Argon2id
    key-encryption-key derivation, wrapped-DEK mint, session open, engine and
    table create — is paid once per module; this cheap whole-table DELETE
    restores a clean ``secure_objects`` table before each test.

    Only the SQLite catalogue rows accumulate per test: the bucket directory,
    plaintext manifest, and separated wrapped DEK are provisioned-once static
    artefacts that carry no per-test mutable state, so they are deliberately left
    intact (clearing the keystore would strand the module-shared session's DEK).
    Every domain catalogue the ledger and filing tests persist — transactions,
    bucket-event history, invoices, work units, calculation revisions, and
    attachment evidence bytes — lands as ``secure_objects`` rows keyed by
    namespace and object-key digest, so a single whole-table DELETE resets the
    entire persisted surface, including rows a test wrote under a second
    ``bucket_id`` sharing the same store.

    A naive module-scope fixture flip WITHOUT this reset ships a false-green: the
    row accumulation makes idempotency and anti-tautology assertions stop biting
    (a prior test's persisted row makes a fresh add resolve to an existing-row
    no-op). Calling this before each test restores per-test isolation so those
    assertions bite again.
    """
    engine = repository._engine
    with engine.begin() as connection:
        connection.execute(sa_text("DELETE FROM secure_objects"))
        if sa_inspect(engine).has_table("secure_objects_quarantine"):
            connection.execute(sa_text("DELETE FROM secure_objects_quarantine"))


@contextmanager
def isolated_injected_secure_object_repository(
    *,
    tmp_path: Path,
    bucket_id: str,
    database_name: str,
) -> Iterator[SecureObjectRepository]:
    """Yield a second real secure-object store under the active bucket session.

    The repository uses its own SQLite engine and production schema while row
    encryption remains bound to the caller's genuine active bucket session.
    This supports source-injection proofs that must keep the injected catalogue
    physically distinct from the ambient runtime catalogue.
    """

    settings = Settings(cadrumo_database_url=f"sqlite:///{(tmp_path / database_name).as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    try:
        yield SecureObjectRepository(
            engine=engine,
            namespace_registry=STORAGE_NAMESPACE_REGISTRY,
            active_session_bucket_id=bucket_id,
            require_secure_active_session=True,
        )
    finally:
        dispose_engine(settings)


@contextmanager
def isolated_ephemeral_secure_sql(
    *,
    tmp_path: Path,
    database_name: str = "cadrumo.db",
) -> Iterator[None]:
    """Run test code with a temp SQL database and real ephemeral master key."""

    database_url = f"sqlite:///{(tmp_path / database_name).as_posix()}"
    with override_settings(
        cadrumo_database_url=database_url,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
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

    storage_root = tmp_path / "cadrumo-storage"
    with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield storage_root
        finally:
            reap_profile_session_keys(storage_root)
            dispose_engine(settings)


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path: Path) -> Iterator[None]:
    """Run tests against a flat, session-less real storage root at ``tmp_path`` itself.

    Unlike :func:`isolated_sessionless_storage_root` (which nests the root
    under ``tmp_path / "cadrumo-storage"``), this fixture points
    ``cadrumo_local_storage_root`` directly at ``tmp_path`` — the shape a
    cluster of lower-level repository and runtime test modules already relied
    on before this fixture was promoted as their single canonical source.
    Several of those modules also write ancillary fixture bytes (e.g. a
    synthetic PDF) directly under ``tmp_path`` alongside the storage root, so
    the two paths must stay coincident rather than nesting one under the
    other.

    ``autouse=True`` for the same reason as :func:`isolated_cli_backend`:
    every current call site wants it active for every test in the importing
    module. Import it directly rather than re-declaring the override block
    locally, e.g.::

        from ....tests.secure_sql import isolated_storage_root as _isolated_storage
    """

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            reap_profile_session_keys(tmp_path)
            dispose_engine(settings)


@contextmanager
def isolated_profile_storage_root(*, tmp_path: Path) -> Iterator[Path]:
    """Run profile-bootstrap tests against an empty real storage root.

    Unlike :func:`isolated_runtime_profile`, this helper does not
    provision a bucket or activate an ``cadrumo_active_profile`` route.
    It is for tests that exercise the profile creation path itself,
    where the system under test must create the bucket directory,
    manifest, pointer, and per-bucket database.

    The dev-test passphrase is configured so the profile-creation verbs
    resolve a working credential. It no longer selects a process-wide key
    store: the shared-master backends are deleted, and the key a bucket
    opens under is its own, minted per profile by the custody package.
    """

    tmp_path.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "cadrumo-storage"
    passphrase = load_settings().cadrumo_dev_test_database_password
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
        cadrumo_secret_store_backend="auto",
        cadrumo_secret_passphrase=passphrase,
        # Enrolment calibrates the KDF grid by MEASURING real supervised
        # derivations -- one child process per warmup and per sample. That is
        # the right price once, on an operator's machine, and the wrong one on
        # a host that enrols a profile per test: measured at 15.5s of a 17.4s
        # registration. Declining to measure adopts the fixed point the
        # calibrator already falls back to, which is STRONGER than the measured
        # band's floor, so the wrap does not weaken and every derivation is
        # still a real Argon2id through the same supervised worker.
        cadrumo_profile_kdf_measure_calibration=False,
        # Anchored on ``tmp_path``, not on the storage root, so the secret
        # substrate stays a sibling of the bucket tree rather than nesting
        # inside it -- the production custody split.
        **storage_overrides(tmp_path, StorageCategory.SECRETS),
    ) as settings:
        dispose_engine(settings)
        try:
            yield storage_root
        finally:
            reap_profile_session_keys(storage_root)
            dispose_engine(settings)


def default_test_profile_label(bucket_id: str) -> str:
    """Return the default label for a test profile on ``bucket_id``.

    Derived from the bucket rather than constant: the custody service refuses
    a second committed capsule carrying a label an existing one already holds,
    so a shared constant made two profiles under one storage root collide on
    the label instead of on whatever the test was exercising. A caller that
    passes its own label is unaffected.
    """
    # The FULL identity, not a prefix: test bucket ids are commonly minted
    # from a shared prefix with only the last octets varying, so a truncated
    # slice collides exactly where two buckets are most likely to coexist.
    return f"Test runtime profile {bucket_id}"


@contextmanager
def isolated_runtime_profile(
    *,
    tmp_path: Path,
    bucket_id: str = _DEFAULT_RUNTIME_BUCKET_ID,
    label: str | None = None,
) -> Iterator[TestRuntimeProfile]:
    """Create a real active-profile bucket runtime for tests.

    The helper provisions the same durable surfaces used by production:
    a bucket directory, plaintext manifest, separated per-bucket wrapped
    DEK, active-profile settings route, active bucket session, and
    runtime-owned secure-object repository.

    The handed ``tmp_path`` is materialised here rather than assumed. Custody
    anchors every component of a directory it is about to write into and
    refuses an absent one -- a deliberate refusal, since anchoring identity
    before writing is what closes the check-then-create window -- so a caller
    passing a subdirectory that does not exist yet failed on setup with an
    identity-anchoring refusal that named nothing about the real cause. That
    trap caught five call sites across three modules before it was closed here.
    A helper that yields a LOCATION its callers must separately remember to
    create is a footgun, and the fix belongs at the helper rather than in a
    comment repeated at each call site.

    The bucket is a genuine ``BUCKET_DEK_V1`` bucket: the file backend is
    configured with the dev-test passphrase (as
    :func:`isolated_profile_storage_root` does) so the wrapped DEK is
    minted under, and unwraps under, the same master-key provider a
    nested :func:`open_test_profile_session` re-resolves on the read path.
    """

    tmp_path.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "cadrumo-storage"
    passphrase = load_settings().cadrumo_dev_test_database_password
    opened_at = datetime.now(UTC).replace(microsecond=0)

    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=bucket_id,
        cadrumo_secret_store_backend="auto",
        # Enrolment calibrates the KDF grid by MEASURING real supervised
        # derivations, one child process per warmup and per sample. See
        # `isolated_profile_storage_root` for the measured cost; the fixed
        # fallback adopted instead is stronger than the measured band's
        # floor, so no wrap weakens and the derivation stays real.
        cadrumo_profile_kdf_measure_calibration=False,
        cadrumo_secret_passphrase=passphrase,
        **storage_overrides(tmp_path, StorageCategory.SECRETS),
    ) as settings:
        dispose_engine(settings)
        session, paths = provision_test_profile_bucket_session(
            bucket_id=bucket_id,
            label=label if label is not None else default_test_profile_label(bucket_id),
            storage_root=storage_root,
            opened_at=opened_at,
        )
        with activate_session(session):
            runtime = inspect_storage_runtime(settings)
            # Building the repository through the runtime acquires and
            # registers the bucket engine on ``session``; closing the
            # session in the teardown below disposes it via the unified
            # lifecycle, so no separate ``dispose_engine`` teardown is needed.
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
                session.close()
                reap_profile_session_keys(storage_root)


@dataclass(frozen=True)
class MultiBucketTestRuntime:
    """Two co-existing test runtime profiles for active-vs-target scenarios.

    ``primary`` is ``cadrumo_active_profile`` when the fixture yields.
    ``secondary`` is provisioned with its own bucket directory,
    manifest, keystore, and secure-object repository but its
    session is held in this dataclass for the
    :meth:`switch_to_secondary` context manager to activate
    on demand.
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
        ``open_test_profile_session``; this helper is for tests that
        need direct repository access against the secondary.
        """
        with (
            override_settings(cadrumo_active_profile=self.secondary.bucket_id),
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
    export/import round-trip requires.

    Both buckets are genuine ``BUCKET_DEK_V1`` buckets that share the
    storage root's single file-backend master key (the key-encryption
    key, KEK) but mint their own separated per-bucket data-encryption
    key (DEK) — the production custody shape, where many buckets under
    one storage root share one ``master.key`` and each keeps its own
    wrapped DEK. The per-bucket DEK distinctness means an accidental
    cross-bucket DEK reuse in production code still surfaces as a test
    failure.
    """
    storage_root = tmp_path / "cadrumo-storage"
    passphrase = load_settings().cadrumo_dev_test_database_password
    opened_at = datetime.now(UTC).replace(microsecond=0)

    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=primary_bucket_id,
        cadrumo_secret_store_backend="auto",
        # Enrolment calibrates the KDF grid by MEASURING real supervised
        # derivations, one child process per warmup and per sample. See
        # `isolated_profile_storage_root` for the measured cost; the fixed
        # fallback adopted instead is stronger than the measured band's
        # floor, so no wrap weakens and the derivation stays real.
        cadrumo_profile_kdf_measure_calibration=False,
        cadrumo_secret_passphrase=passphrase,
        # One secret substrate for both buckets: the production shape is many
        # buckets under one root sharing one master key, each with its own
        # wrapped DEK.
        **storage_overrides(tmp_path, StorageCategory.SECRETS),
    ) as settings:
        dispose_engine(settings)
        primary_session, primary_paths = provision_test_profile_bucket_session(
            bucket_id=primary_bucket_id,
            label=primary_label,
            storage_root=storage_root,
            opened_at=opened_at,
        )
        secondary_session, secondary_paths = provision_test_profile_bucket_session(
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
            with override_settings(cadrumo_active_profile=secondary_bucket_id) as secondary_settings:
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
                # Each session owns and disposes its bucket engine on close;
                # closing both sweeps the two buckets' engines via the
                # unified lifecycle.
                secondary_session.close()
                primary_session.close()
                reap_profile_session_keys(storage_root)


@contextmanager
def isolated_cli_runtime_profile(
    *,
    tmp_path: Path,
    bucket_id: str = _DEFAULT_RUNTIME_BUCKET_ID,
    label: str | None = None,
) -> Iterator[TestRuntimeProfile]:
    """Create a real runtime profile with CLI-adjacent directories isolated.

    CLI work-unit tests need the active bucket database plus the
    filesystem directories read from settings for runs, drafts, tokens,
    financial transactions, and invoices. Keep that setup on the central
    settings surface instead of per-test environment mutation.

    The five are named by category, so the settings field and the leaf
    directory both come from the taxonomy. Spelled by hand, they had already
    drifted: this block pinned ``cadrumo_financial_txs_dir`` to ``txs`` while
    the declared subpath is ``financial/transactions``, and nothing caught it,
    because a fixture that only round-trips its own override agrees with any
    name it is given.
    """

    with (
        override_settings(
            **storage_overrides(
                tmp_path,
                StorageCategory.RUNS,
                StorageCategory.DRAFTS,
                StorageCategory.TOKENS,
                StorageCategory.FINANCIAL_TRANSACTIONS,
                StorageCategory.INVOICES,
            ),
        ),
        isolated_runtime_profile(
            tmp_path=tmp_path,
            bucket_id=bucket_id,
            label=label if label is not None else default_test_profile_label(bucket_id),
        ) as profile,
    ):
        # The active session opened by ``isolated_runtime_profile`` already
        # owns a valid engine for this bucket; disposing it here would strand
        # the session's registered handle. The added directory overrides do
        # not change the database route, so the engine stays valid for the
        # CLI test and is disposed on the session's close.
        yield profile


@pytest.fixture(autouse=True)
def isolated_profile_storage(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(autouse=True)
def isolated_cli_backend(tmp_path: Path) -> Iterator[Path]:
    """Canonical isolated storage root for CLI end-to-end tests.

    Unlike :func:`isolated_cli_runtime_profile`, this fixture does not
    pre-provision a bucket: :func:`isolated_profile_storage_root` leaves the
    storage root empty so the real ``config profile create`` CLI command can
    run end to end, which is what most CLI-driven scenarios need.

    Every generated-output directory settings field derives its default from
    ``cadrumo_local_storage_root`` (every root-derived member of
    :data:`~core.STORAGE_TAXONOMY`), so isolating the root through
    :func:`isolated_profile_storage_root` alone relocates the whole family —
    tokens, drafts, runs, financial catalogues, and every sibling directory —
    without a per-field override block. ``cadrumo_output_language`` is pinned
    to English so operator-facing text assertions stay locale-stable across
    CLI test suites.

    ``autouse=True`` because every current call site wants the isolated
    backend active for every test in the importing module — matching the
    convention the ~22 sites this fixture replaces already established.
    Import it directly into a test module rather than re-declaring the
    override block locally, e.g.::

        from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend

    The re-bound name still carries ``autouse=True`` in the importing module
    because pytest resolves fixtures by the name bound in the requesting
    module's namespace, not by the module that originally defined the
    function; this is the same pattern the entrypoints CLI test suite
    already uses for its intra-package ``_isolated_cli_backend`` re-export.
    A caller that wants the storage-root isolation WITHOUT autouse should
    call :func:`isolated_profile_storage_root` directly instead of importing
    this fixture — pytest does not support re-decorating an already-wrapped
    fixture function to change its ``autouse`` value.
    """
    dispose_engine()
    with (
        override_settings(cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
    ):
        try:
            yield storage_root
        finally:
            dispose_engine()


__all__ = [
    "MultiBucketTestRuntime",
    "TestRuntimeProfile",
    "dev_test_database_password",
    "isolated_cli_backend",
    "isolated_cli_runtime_profile",
    "isolated_ephemeral_secure_sql",
    "isolated_profile_storage",
    "isolated_profile_storage_root",
    "isolated_runtime_profile",
    "isolated_sessionless_storage_root",
    "isolated_storage_root",
    "isolated_two_bucket_runtime",
    "mutate_encrypted_secure_object_json",
    "reap_profile_session_keys",
    "reset_secure_object_store",
]

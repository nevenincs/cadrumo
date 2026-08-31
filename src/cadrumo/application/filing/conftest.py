"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.

The expensive bucket runtime (Argon2id KEK derivation, wrapped-DEK mint,
session open, engine + table create) is provisioned once per test module by
``_active_bucket_runtime``. Per-test isolation is restored by the autouse
``_reset_filing_store`` teardown, which truncates the module-shared
``secure_objects`` table before each test. This is the real per-test
on-disk reset, not a ``Session().begin_nested()`` savepoint (a savepoint
cannot roll back on-disk keystore/manifest state, and the catalogue rows
are the only thing that actually accumulates). Tests that scan the at-rest
database bytes read the module runtime's ``storage_root`` rather than their
own per-test ``tmp_path``.

See Also:
    :func:`aeat-tests.secure_sql.isolated_runtime_profile`
        Shared helper that provisions the real active-profile bucket runtime
        used by this fixture.
    :func:`aeat-tests.secure_sql.reset_secure_object_store`
        Per-test teardown that truncates the module-shared secure-object store.
    :class:`aeat-tests.secure_sql.TestRuntimeProfile`
        Frozen record yielded by the helper so tests can inspect the isolated
        storage root, bucket id, runtime, and repository.
    :mod:`cadrumo.adapters.persistence.storage.sql.conftest`
        Module-scoped storage fixture shape used only where transactional
        rollback isolates per-test state.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text

from ...adapters.persistence.storage.secure_object_namespaces import USER_PROFILE_VALUE_NAMESPACE
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

# Capsule publication mints the bucket's identity through ``UUID(str(profile_id))``
# (:func:`~cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime.publish_test_profile_capsule`),
# so this
# constant must stay UUID-shaped -- a human-readable label was never valid here,
# it simply predates that requirement.
_BUCKET_ID = "66666666-6666-4666-8666-666666666666"


@pytest.fixture(scope="module")
def _active_bucket_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the active filing bucket runtime once per test module."""
    tmp_path = tmp_path_factory.mktemp("filing-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture(autouse=True)
def _reset_filing_store(_active_bucket_runtime: TestRuntimeProfile) -> Iterator[None]:
    """Truncate the module-shared secure-object store before each test.

    Load-bearing per-test isolation: without it the module-shared runtime bleeds
    persisted records across tests (a prior test's filing records appear in a
    later test's list/iter assertions) and the anti-tautology at-rest scans stop
    biting. The reset is cheap (a whole-table DELETE); the costly bucket
    provisioning is paid once by ``_active_bucket_runtime``.
    """
    _reset_preserving_the_profile_record(_active_bucket_runtime.repository)
    yield


def _reset_preserving_the_profile_record(repository: SecureObjectRepository) -> None:
    """Truncate per-test rows while leaving the capsule's one record row intact.

    The shared reset deletes every ``secure_objects`` row, and the profile
    record is one of them -- so it also destroyed capsule identity. A committed
    capsule ALWAYS holds exactly one current record row (creation writes it
    before the stage commit marker, and replacement is compare-and-swap, never
    delete-then-write), so a capsule holding none is a state no production path
    can reach, and the loader is right to call it corruption. Every test in this
    package inherited that state, and any production path self-loading the
    profile record refused inside it.

    The row belongs with the bucket directory, manifest and wrapped DEK that the
    shared reset already preserves deliberately: provisioned once, carrying no
    per-test mutable state. A test that MUTATES the record still has to restore
    it, exactly as it would for those.
    """
    engine = repository.engine
    with engine.begin() as connection:
        connection.execute(
            sa_text("DELETE FROM secure_objects WHERE namespace != :keep"),
            {"keep": USER_PROFILE_VALUE_NAMESPACE.namespace},
        )
        if sa_inspect(engine).has_table("secure_objects_quarantine"):
            connection.execute(sa_text("DELETE FROM secure_objects_quarantine"))


__all__ = ["_active_bucket_runtime", "_reset_filing_store"]

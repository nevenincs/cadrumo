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

from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, reset_secure_object_store

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
    reset_secure_object_store(_active_bucket_runtime.repository)
    yield


__all__ = ["_active_bucket_runtime", "_reset_filing_store"]

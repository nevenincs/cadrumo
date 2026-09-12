"""Pytest fixtures for ledger application tests."""

from collections.abc import Iterator

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    reset_secure_object_store,
)
from .action_fixtures import _BUCKET_ID


@pytest.fixture(scope="module")
def _ledger_module_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the expensive ledger bucket runtime once per test module."""
    tmp_path = tmp_path_factory.mktemp("ledger-action-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def secure_objects(_ledger_module_runtime: TestRuntimeProfile) -> Iterator[SecureObjectRepository]:
    """Reset the shared secure-object store before each ledger action test."""
    reset_secure_object_store(_ledger_module_runtime.repository)
    yield _ledger_module_runtime.repository


__all__ = ["_ledger_module_runtime", "secure_objects"]

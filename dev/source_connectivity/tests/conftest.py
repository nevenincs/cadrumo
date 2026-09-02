"""Fixtures shared by this directory, mirroring the src-tree application conftest.

`test_source_connectivity_authority.py` moved here from
`cadrumo.application.registry.tests`, whose package conftest supplied both the
`registry_authority` fixture (via the shared two-tree factory in
`cadrumo.tests.registry_authority_fixture`, the same pattern
`dev/registry/tests/conftest.py` already applies) and the `secure_objects` /
`_isolated_aeat_root` fixtures defined directly on
`cadrumo.application.conftest`. Neither src-tree conftest applies to this
directory, so both are reproduced here for the tests that still need them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.tests.env import temporary_env
from cadrumo.tests.registry_authority_fixture import bundled_registry_authority_fixture
from cadrumo.tests.secure_sql import isolated_runtime_profile

registry_authority = bundled_registry_authority_fixture(name="registry_authority")


@runtime_checkable
class _MarkerNode(Protocol):
    def get_closest_marker(self, name: str) -> object | None: ...


class _RequestWithModule(Protocol):
    module: object


@pytest.fixture(autouse=True, name="_isolated_aeat_root")
def isolated_aeat_root(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[None]:
    """Point :class:`~cadrumo.core.config.Settings` storage roots at the test's ``tmp_path``."""
    request_node: object = getattr(request, "node", None)
    if not isinstance(request_node, _MarkerNode):
        raise TypeError("pytest request node does not expose marker lookup")
    if request_node.get_closest_marker("aeat_live") is not None:
        yield
        return
    with temporary_env(CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path)):
        yield


@pytest.fixture
def secure_objects(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[SecureObjectRepository]:
    """Yield the real encrypted-SQLite object repository for a module bucket."""
    request_with_module = cast(_RequestWithModule, request)
    bucket_id = getattr(request_with_module.module, "_BUCKET_ID", None)
    if not isinstance(bucket_id, str) or not bucket_id:
        raise RuntimeError("secure_objects requires a non-empty module _BUCKET_ID")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        yield profile.repository

"""Pytest fixtures shared across ``application/`` tests.

The autouse ``_isolated_aeat_root`` fixture redirects the
``cadrumo_local_storage_root`` field on :class:`~cadrumo.core.config.Settings` to a
function-scoped ``tmp_path`` for unit tests under this package, so the
:class:`~cadrumo.core.bucket_pointer.BucketPointer` file materialised by profile custody
operations lands inside the test sandbox and never bleeds into the project's
real ``var/storage/`` directory.

Opt-in live tests are intentionally excluded. They need the operator's
real active-profile pointer and encrypted bucket so Cl@ve-backed reads
exercise the same state the CLI uses.

Isolation uses a scoped environment-variable context (not
:func:`~cadrumo.core.config.override_settings`) on purpose: ``BaseSettings``
re-reads variables on every :class:`~cadrumo.core.config.Settings` instantiation,
so later nested fixtures that mutate other ``AEAT_*`` variables compose
correctly. An ``override_settings`` context manager would snapshot the
settings at this fixture's setup time and mask any subsequent env changes from
the per-test fixture chain.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import pytest

from ..tests.env import temporary_env
from ..tests.secure_sql import isolated_runtime_profile

if TYPE_CHECKING:
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository


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

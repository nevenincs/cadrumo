"""Canonical isolated-storage-plus-active-profile fixture for test suites.

Seeded through a detached ``WorkflowState``, never a repository read: the
capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
which a workflow-state repository construction would otherwise materialise
first and collide with.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from .profile_capsule import open_test_profile_session
from .secure_sql import isolated_profile_storage_root
from .user_profile import register_minimal_profile

#: The bucket id most callers of this fixture share.
DEFAULT_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


def active_profile_isolated_backend_fixture(
    *,
    bucket_id: str = DEFAULT_BUCKET_ID,
    autouse: bool = True,
    name: str = "_isolated_backend",
) -> Callable[[Path], Iterator[None]]:
    """Build a fixture isolating storage and opening a seeded profile session.

    The same body was written independently at several sites -- some autouse,
    some explicitly requested, most sharing the default bucket id but at
    least one pinned to its own -- so ``bucket_id``, ``autouse`` and ``name``
    stay per-caller while only the body is shared.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _active_profile_isolated_backend(tmp_path: Path) -> Iterator[None]:
        with (
            isolated_profile_storage_root(tmp_path=tmp_path),
            open_test_profile_session(bucket_id),
        ):
            register_minimal_profile(profile_id=bucket_id)
            yield

    return _active_profile_isolated_backend


__all__ = ["DEFAULT_BUCKET_ID", "active_profile_isolated_backend_fixture"]

"""Canonical isolated runtime fixtures for persistence adapter tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

__all__ = ["_runtime_profile", "bucket_scoped_runtime_profile_fixture"]


@pytest.fixture(name="_runtime_profile", autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Install and tear down the real default-bucket runtime for one test."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def bucket_scoped_runtime_profile_fixture(
    bucket_id: str,
    *,
    autouse: bool = True,
    name: str = "_runtime_profile",
) -> Callable[[Path], Iterator[TestRuntimeProfile]]:
    """Build a ``_runtime_profile``-shaped fixture pinned to ``bucket_id``.

    A distinct ``bucket_id`` per test module keeps the bucket-scoped
    master-key session from colliding with other modules sharing a bucket in
    the same run. Assign the return value to a module-level name matching
    ``name`` -- ``_runtime_profile`` by default -- so pytest discovers it
    under that name; the module keeps declaring its own binding, so reach is
    never centralised, only the body.

    ``autouse`` and ``name`` default to the shape every existing caller
    relies on (autouse, bound as ``_runtime_profile``), so those callers are
    unaffected by this signature. A caller whose test functions REQUEST the
    fixture explicitly by a name of their own -- rather than relying on
    autouse -- passes ``autouse=False`` and its own ``name``, matching every
    request site already written against that name.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _bucket_scoped_runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
            yield profile

    return _bucket_scoped_runtime_profile

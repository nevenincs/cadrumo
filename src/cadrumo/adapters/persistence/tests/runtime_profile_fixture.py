"""Canonical isolated runtime fixtures for persistence adapter tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..profile.transactions import TransactionCatalogueRepository

__all__ = [
    "_runtime_profile",
    "bucket_scoped_runtime_profile_fixture",
    "bucket_scoped_transaction_catalogue_fixture",
    "default_bucket_runtime_profile_fixture",
]


def bucket_scoped_runtime_profile_fixture(
    bucket_id: str,
    *,
    autouse: bool = True,
    name: str = "_runtime_profile",
) -> Callable[..., Iterator[TestRuntimeProfile]]:
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


def default_bucket_runtime_profile_fixture(
    *,
    autouse: bool = True,
    name: str = "_runtime_profile",
) -> Callable[..., Iterator[TestRuntimeProfile]]:
    """Build a runtime-profile fixture on the DEFAULT bucket.

    The sibling above pins a bucket; this one deliberately does not, which is a
    different contract rather than a missing argument. Modules sharing the
    default bucket are the ones whose isolation comes from ``tmp_path`` alone,
    and giving them a synthesised bucket id to satisfy a signature would change
    what they exercise.

    It exists because the same three-line body was written twice under two
    names -- once autouse as ``_runtime_profile``, once explicitly requested as
    ``secure_engine`` -- and a body copied under a second name is invisible to
    every name-keyed search. ``autouse`` and ``name`` stay per-caller so reach
    is still declared where it applies; only the body is shared.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _default_bucket_runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            yield profile

    return _default_bucket_runtime_profile


def bucket_scoped_transaction_catalogue_fixture(
    bucket_id: str,
    *,
    name: str,
) -> Callable[..., Iterator[TransactionCatalogueRepository]]:
    """Build a fixture yielding a :class:`TransactionCatalogueRepository`.

    The repository is opened on an isolated runtime profile pinned to
    ``bucket_id``, which is the shape two suites had each written out for
    themselves under names of their own.

    ``bucket_id`` is a required argument rather than a default precisely
    because the two callers pass different values, and that difference is
    load-bearing: a distinct bucket per module keeps the bucket-scoped
    master-key session from colliding with another module in the same run.
    Two bodies that look identical because each closes over its own module
    constant are NOT interchangeable, and folding them onto one shared bucket
    would have unified two suites onto one key session while every test still
    passed. ``name`` is likewise required -- the two callers request this
    fixture under names of their own and neither is the obvious default.

    Args:
        bucket_id: The bucket this caller's repository and runtime are pinned to.
        name: The fixture name pytest discovers, matching the caller's request sites.

    Returns:
        A fixture function to bind at module level under ``name``.
    """

    @pytest.fixture(name=name)
    def _bucket_scoped_transaction_catalogue(tmp_path: Path) -> Iterator[TransactionCatalogueRepository]:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
            yield TransactionCatalogueRepository(bucket_id=bucket_id, objects=profile.repository)

    return _bucket_scoped_transaction_catalogue


#: The default-bucket autouse runtime every persistence adapter suite installs.
#: Bound through the factory rather than written out, so the body has one home.
_runtime_profile = default_bucket_runtime_profile_fixture()

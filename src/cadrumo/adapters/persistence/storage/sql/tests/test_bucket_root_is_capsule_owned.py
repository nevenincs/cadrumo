"""The engine factory never brings a bucket root into existence.

A bucket root under ``buckets/`` is created exactly once, by the no-replace
rename that publishes its profile capsule. Resolving a database path is a
read of that layout, not a second way to enrol a bucket: an engine opened
against an unpublished bucket must refuse rather than leave an empty
directory that the real publication then finds occupied.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from ......core.config import Settings
from ...errors import StorageError
from ...storage_path_definitions import BUCKET_DATABASE_FILENAME, BUCKET_DB_DIRNAME, BUCKETS_DIRNAME
from .. import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


def _bucket_root(root: Path) -> Path:
    return root / BUCKETS_DIRNAME / _BUCKET_ID


def _bucket_database_url(root: Path) -> str:
    return f"sqlite:///{_bucket_root(root) / BUCKET_DB_DIRNAME / BUCKET_DATABASE_FILENAME}"


def test_engine_refuses_an_unpublished_bucket_and_creates_nothing(tmp_path: Path) -> None:
    settings = Settings(cadrumo_database_url=_bucket_database_url(tmp_path))

    with pytest.raises(StorageError) as refusal:
        create_engine_from_settings(settings)

    context = refusal.value.context or {}
    assert str(context["bucket_directory"]) == str(_bucket_root(tmp_path))
    assert not _bucket_root(tmp_path).exists()
    assert not (tmp_path / BUCKETS_DIRNAME).exists()


def test_engine_opens_and_creates_the_database_directory_inside_a_published_bucket(tmp_path: Path) -> None:
    _bucket_root(tmp_path).mkdir(parents=True)
    settings = Settings(cadrumo_database_url=_bucket_database_url(tmp_path))

    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
    finally:
        engine.dispose()
        dispose_engine(settings)

    assert (_bucket_root(tmp_path) / BUCKET_DB_DIRNAME).is_dir()


def test_engine_still_creates_parents_for_a_route_outside_the_buckets_container(tmp_path: Path) -> None:
    """A non-bucket route keeps its ordinary parent creation."""
    database = tmp_path / "state" / "nested" / "cadrumo.db"
    settings = Settings(cadrumo_database_url=f"sqlite:///{database}")

    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
    finally:
        engine.dispose()
        dispose_engine(settings)

    assert database.parent.is_dir()

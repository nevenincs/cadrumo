"""Tests for primary SQL storage route classification.

The ``cadrumo.db`` literals throughout are deliberate, not unmigrated -- and so
are the ``buckets``/``db`` segments joined alongside them in the same chained
expressions (e.g. ``tmp_path / "buckets" / "bucket-a" / "db" / "cadrumo.db"``):
the whole on-disk shape is the defended literal, not only its trailing
filename. Two distinct reasons hold across the file's cases, and neither is
served by routing the expected side through ``bucket_paths(...).database_file``:

- The ``route.database_path`` assertions confirm an end-to-end round trip --
  ``Settings`` deriving ``cadrumo_database_url`` (itself pinned against a raw
  literal in ``test_the_database_url_resolves_to_its_pre_migration_shape``)
  and ``classify_storage_route`` echoing that URL back as a path -- against
  the real on-disk shape, independent of the taxonomy accessor either step
  internally consumes. Re-deriving the expected side from that same accessor
  would make the assertion pass unconditionally on a Settings/classifier
  defect that drifted the two in lockstep.
- The ``not (... / "cadrumo.db").exists()`` refusals prove the former-product
  guard creates nothing at the canonical path when it refuses to touch a
  legacy ``aeat.db``. An accessor aimed at the wrong location would leave
  that assertion trivially satisfied -- the exact silent-pass shape a refusal
  test must not risk.

The explicit-database-URL parametrize cases (one of which is the unrelated
``explicit.db``) exercise arbitrary caller-supplied URLs, not the canonical
filename, so they stay literal for the same reason.

The ``"active-profile"`` write in
``test_corrupt_pointer_refuses_root_fallback`` is the same shape as the
round-trip cases above: it plants a malformed pointer file at the real
location ``Settings`` reads to prove the corrupt-pointer refusal fires, so it
must target where the accessor's own consumer actually reads, not the
accessor re-applied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from .._config_state_root import FormerProductStateError
from ..bucket_pointer import BucketPointer, write_pointer
from ..config import (
    Settings,
    StorageRouteKind,
    classify_storage_route,
    settings_for_active_profile_bucket,
)
from ..errors.hierarchy import ActiveProfilePointerError, CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cadrumo.db", "buckets", "db", "active-profile"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def test_constructor_database_url_classifies_as_explicit(tmp_path: Path) -> None:
    for db_path_parts in (
        ("explicit.db",),
        ("state", "buckets", "bucket-a", "db", "cadrumo.db"),
        ("state", "cadrumo.db"),
    ):
        db_path = tmp_path.joinpath(*db_path_parts)
        settings = Settings(
            cadrumo_local_storage_root=tmp_path / "state",
            cadrumo_database_url=f"sqlite:///{db_path.as_posix()}",
        )

        route = classify_storage_route(settings)

        assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL, db_path_parts
        assert route.database_path == db_path, db_path_parts
        assert route.bucket_id is None, db_path_parts


def test_active_bucket_database_route_is_detected(tmp_path: Path) -> None:
    settings = Settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_active_profile="bucket-a",
    )

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "bucket-a"
    assert route.database_path == tmp_path / "buckets" / "bucket-a" / "db" / "cadrumo.db"


def test_pointer_resolved_bucket_database_route_is_detected(tmp_path: Path) -> None:
    write_pointer(tmp_path, BucketPointer.selected(bucket_id="pointer-bucket", transition_revision=1))
    settings = Settings(cadrumo_local_storage_root=tmp_path)

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "pointer-bucket"


def test_corrupt_pointer_refuses_root_fallback(tmp_path: Path) -> None:
    pointer_file = tmp_path / "active-profile"
    pointer_file.write_text("not = valid = toml", encoding="utf-8")

    with pytest.raises(ActiveProfilePointerError) as exc_info:
        Settings(cadrumo_local_storage_root=tmp_path)

    error = exc_info.value
    assert error.args == ("errors.integrity.integrity_active_profile_pointer",)
    assert error.context == {
        "path": str(pointer_file),
        "pointer_corrupt": True,
        "root_fallback_refused": True,
    }
    assert error.__cause__ is not None


def test_no_active_profile_classifies_root_fallback_database(tmp_path: Path) -> None:
    settings = Settings(cadrumo_local_storage_root=tmp_path)

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert route.database_path == tmp_path / "cadrumo.db"
    assert route.bucket_id is None


def test_root_route_refuses_existing_former_database_without_touching_bytes(tmp_path: Path) -> None:
    former_db = tmp_path / "aeat.db"
    former_bytes = b"former-root-database"
    former_db.write_bytes(former_bytes)

    with pytest.raises(FormerProductStateError, match="will not read, move, copy, delete, migrate, or adopt"):
        Settings(cadrumo_local_storage_root=tmp_path)

    assert former_db.read_bytes() == former_bytes
    assert not (tmp_path / "cadrumo.db").exists()


def test_bucket_route_refuses_existing_former_database_without_touching_bytes(tmp_path: Path) -> None:
    former_db = tmp_path / "buckets" / "operator" / "db" / "aeat.db"
    former_db.parent.mkdir(parents=True)
    former_bytes = b"former-bucket-database"
    former_db.write_bytes(former_bytes)

    with pytest.raises(FormerProductStateError, match="will not read, move, copy, delete, migrate, or adopt"):
        Settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile="operator")

    assert former_db.read_bytes() == former_bytes
    assert not (former_db.parent / "cadrumo.db").exists()


def test_settings_for_active_profile_bucket_derives_non_explicit_bucket_route(tmp_path: Path) -> None:
    source = Settings(cadrumo_local_storage_root=tmp_path / "state")

    derived = settings_for_active_profile_bucket("operator", source)
    route = classify_storage_route(derived)

    assert derived.cadrumo_active_profile == "operator"
    assert "cadrumo_database_url" not in derived.model_fields_set
    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "operator"
    assert route.database_path == tmp_path / "state" / "buckets" / "operator" / "db" / "cadrumo.db"


def test_settings_for_active_profile_bucket_rejects_explicit_database_url(tmp_path: Path) -> None:
    source = Settings(
        cadrumo_local_storage_root=tmp_path / "state",
        cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
    )

    with pytest.raises(CoreValidationError, match="explicit database URL"):
        settings_for_active_profile_bucket("operator", source)


def test_settings_for_active_profile_bucket_rejects_blank_bucket_id(tmp_path: Path) -> None:
    source = Settings(cadrumo_local_storage_root=tmp_path)

    with pytest.raises(CoreValidationError, match="bucket_id must not be blank"):
        settings_for_active_profile_bucket("   ", source)

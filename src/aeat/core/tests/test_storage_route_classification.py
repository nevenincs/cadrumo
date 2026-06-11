"""Tests for primary SQL storage route classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import BucketPointer, write_pointer
from ..config import (
    Settings,
    StorageRouteKind,
    classify_storage_route,
    settings_for_active_profile_bucket,
)
from ..errors import ActiveProfilePointerError, CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_constructor_database_url_classifies_as_explicit(tmp_path: Path) -> None:
    db_path = tmp_path / "explicit.db"
    settings = Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_database_url=f"sqlite:///{db_path.as_posix()}",
    )

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert route.database_path == db_path
    assert route.bucket_id == ""


def test_explicit_url_inside_bucket_layout_still_classifies_as_explicit(tmp_path: Path) -> None:
    db_path = tmp_path / "state" / "buckets" / "bucket-a" / "db" / "aeat.db"
    settings = Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_database_url=f"sqlite:///{db_path.as_posix()}",
    )

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert route.database_path == db_path
    assert route.bucket_id == ""


def test_explicit_url_inside_root_fallback_shape_still_classifies_as_explicit(tmp_path: Path) -> None:
    db_path = tmp_path / "state" / "aeat.db"
    settings = Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_database_url=f"sqlite:///{db_path.as_posix()}",
    )

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert route.database_path == db_path


def test_active_bucket_database_route_is_detected(tmp_path: Path) -> None:
    settings = Settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile="bucket-a",
    )

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "bucket-a"
    assert route.database_path == tmp_path / "buckets" / "bucket-a" / "db" / "aeat.db"


def test_pointer_resolved_bucket_database_route_is_detected(tmp_path: Path) -> None:
    write_pointer(tmp_path, BucketPointer(bucket_id="pointer-bucket", schema_version=1))
    settings = Settings(aeat_local_storage_root=tmp_path)

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "pointer-bucket"


def test_corrupt_pointer_refuses_root_fallback(tmp_path: Path) -> None:
    (tmp_path / "active-profile").write_text("not = valid = toml", encoding="utf-8")

    with pytest.raises(ActiveProfilePointerError) as exc_info:
        Settings(aeat_local_storage_root=tmp_path)

    assert "invalid active-profile pointer" in str(exc_info.value)
    assert "refusing root storage fallback" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_no_active_profile_classifies_root_fallback_database(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path)

    route = classify_storage_route(settings)

    assert route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert route.database_path == tmp_path / "aeat.db"
    assert route.bucket_id == ""


def test_settings_for_active_profile_bucket_derives_non_explicit_bucket_route(tmp_path: Path) -> None:
    source = Settings(aeat_local_storage_root=tmp_path / "state")

    derived = settings_for_active_profile_bucket("operator", source)
    route = classify_storage_route(derived)

    assert derived.aeat_active_profile == "operator"
    assert "aeat_database_url" not in derived.model_fields_set
    assert route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert route.bucket_id == "operator"
    assert route.database_path == tmp_path / "state" / "buckets" / "operator" / "db" / "aeat.db"


def test_settings_for_active_profile_bucket_rejects_explicit_database_url(tmp_path: Path) -> None:
    source = Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
    )

    with pytest.raises(CoreValidationError, match="explicit database URL"):
        settings_for_active_profile_bucket("operator", source)


def test_settings_for_active_profile_bucket_rejects_blank_bucket_id(tmp_path: Path) -> None:
    source = Settings(aeat_local_storage_root=tmp_path)

    with pytest.raises(CoreValidationError, match="bucket_id must not be blank"):
        settings_for_active_profile_bucket("   ", source)

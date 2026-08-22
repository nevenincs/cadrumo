"""Callback-route storage write-policy tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core import STORAGE_ROOT_SETTINGS_FIELD, BucketPointer, write_pointer
from ...core.config import Settings, StorageRouteKind
from ...core.external_constants import OutputLanguage
from ..storage_write_policy import StorageWritePolicyCode, inspect_storage_write_policy

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("write_route", "expected_code", "profile_bound", "bootstrap"),
    (
        ("none", StorageWritePolicyCode.NON_PROFILE_BOUND_VERB, False, False),
        ("bootstrap-root", StorageWritePolicyCode.BOOTSTRAP_EXEMPT, False, True),
    ),
)
def test_non_profile_routes_do_not_inspect_storage(
    tmp_path: Path,
    write_route: str,
    expected_code: StorageWritePolicyCode,
    profile_bound: bool,
    bootstrap: bool,
) -> None:
    decision = inspect_storage_write_policy(
        write_route,
        settings=Settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
    )
    assert decision.allowed is True
    assert decision.code is expected_code
    assert decision.profile_bound_write is profile_bound
    assert decision.bootstrap_exempt is bootstrap
    assert decision.route_kind is None


def test_unknown_write_route_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown command write-route scope"):
        inspect_storage_write_policy("future-route", settings=Settings(cadrumo_local_storage_root=tmp_path))


def test_profile_bound_route_refuses_root_fallback(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "profile-bound",
        settings=Settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=OutputLanguage.EN),
    )
    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert decision.verdict is not None
    assert decision.verdict.failed_condition_id == "profile.active"
    assert "No active profile" in decision.render_refusal_message(locale="en")


def test_profile_bound_route_refuses_explicit_database(tmp_path: Path) -> None:
    settings = Settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
    )
    decision = inspect_storage_write_policy("profile-bound", settings=settings)
    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_EXPLICIT_DATABASE_URL
    assert decision.route_kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert decision.verdict is not None
    evidence = decision.verdict.evidence[0].values
    assert evidence["explicit_route_setting"] == "CADRUMO_DATABASE_URL"
    assert evidence["storage_root_setting"] == "CADRUMO_LOCAL_STORAGE_ROOT"
    assert settings.model_fields_set >= {"cadrumo_database_url", STORAGE_ROOT_SETTINGS_FIELD}


def test_profile_bound_route_allows_active_bucket(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "profile-bound",
        settings=Settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile="operator"),
    )
    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE


def test_profile_bound_route_uses_pointer_from_stale_settings(tmp_path: Path) -> None:
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=OutputLanguage.EN)
    write_pointer(tmp_path, BucketPointer(bucket_id="operator", schema_version=1))
    decision = inspect_storage_write_policy("profile-bound", settings=settings)
    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET
    assert decision.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE

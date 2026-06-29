"""Storage write-policy backend tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core import BucketPointer, write_pointer
from ...core.config import Settings, StorageRouteKind
from ...core.external_constants import OutputLanguage
from ..storage_write_policy import (
    StorageWritePolicyCode,
    inspect_storage_write_policy,
    is_profile_bound_write_verb_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_profile_bound_write_refuses_root_fallback_route(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "app ledger add",
        bootstrap_exempt=False,
        settings=Settings(aeat_local_storage_root=tmp_path, aeat_output_language=OutputLanguage.EN),
    )

    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert "No active profile" in decision.render_refusal_message(locale="en")


def test_profile_bound_write_refuses_explicit_database_route(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "config google login",
        bootstrap_exempt=False,
        settings=Settings(
            aeat_local_storage_root=tmp_path,
            aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
            aeat_output_language=OutputLanguage.EN,
        ),
    )

    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_EXPLICIT_DATABASE_URL
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    rendered = decision.render_refusal_message(locale="en")
    assert "Storage runtime is not ready" in rendered
    assert "database route is not attached to an active profile bucket" in rendered
    context = decision.refusal_context()
    assert context is not None
    assert "AEAT_DATABASE_URL" in context["recovery"]
    assert "AEAT_LOCAL_STORAGE_ROOT" in context["recovery"]


def test_profile_bound_write_allows_active_bucket_route(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "app modelo work calculate work-1",
        bootstrap_exempt=False,
        settings=Settings(aeat_local_storage_root=tmp_path, aeat_active_profile="operator"),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE


def test_profile_bound_write_allows_pointer_route_from_stale_settings(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path, aeat_output_language=OutputLanguage.EN)
    write_pointer(tmp_path, BucketPointer(bucket_id="operator", schema_version=1))

    decision = inspect_storage_write_policy(
        "app ledger add",
        bootstrap_exempt=False,
        settings=settings,
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET
    assert decision.profile_bound_write is True
    assert decision.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE


def test_stub_only_work_create_delegates_to_leaf_refusal_before_root_route_guard(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path, aeat_output_language=OutputLanguage.EN)

    decision = inspect_storage_write_policy(
        "app modelo work create",
        bootstrap_exempt=False,
        settings=settings,
        argv_tokens=("app", "modelo", "work", "create", "--modelo", "210", "--year", "2025", "--period", "1T"),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.LEAF_REFUSAL_DELEGATED
    assert decision.profile_bound_write is True

    supported = inspect_storage_write_policy(
        "app modelo work create",
        bootstrap_exempt=False,
        settings=settings,
        argv_tokens=("app", "modelo", "work", "create", "--modelo", "303", "--year", "2025", "--period", "1T"),
    )
    assert supported.allowed is False
    assert supported.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK


def test_stub_only_work_create_delegates_when_real_argv_reconstruction_appends_values(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path, aeat_output_language=OutputLanguage.EN)

    decision = inspect_storage_write_policy(
        "app modelo work create 210 2025 evento 2025",
        bootstrap_exempt=False,
        settings=settings,
        argv_tokens=(
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "210",
            "--year",
            "2025",
            "--period",
            "evento",
            "--revision",
            "2025",
        ),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.LEAF_REFUSAL_DELEGATED
    assert decision.profile_bound_write is True


def test_m210_live_engine_work_create_stays_under_root_write_guard(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "app modelo work create",
        bootstrap_exempt=False,
        settings=Settings(
            aeat_local_storage_root=tmp_path,
            aeat_output_language=OutputLanguage.EN,
            aeat_m210_engine_live=True,
        ),
        argv_tokens=("app", "modelo", "work", "create", "--modelo=210", "--year", "2025", "--period", "1T"),
    )

    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK


def test_bootstrap_exemption_short_circuits_route_policy(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "config profile create operator",
        bootstrap_exempt=True,
        settings=Settings(
            aeat_local_storage_root=tmp_path,
            aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.BOOTSTRAP_EXEMPT
    assert decision.route_kind is None


def test_read_only_and_recovery_verbs_do_not_trigger_write_policy(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "config switch does-not-exist",
        bootstrap_exempt=False,
        settings=Settings(aeat_local_storage_root=tmp_path),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.NON_PROFILE_BOUND_VERB
    assert decision.profile_bound_write is False
    assert decision.route_kind is None


@pytest.mark.parametrize(
    ("verb_path", "expected"),
    (
        ("app ledger link tx --invoice-id inv", True),
        ("app ledger rule add --description-pattern fuel --classification expense", True),
        ("app ledger rule apply --dry-run", True),
        ("app modelo work file abc", True),
        ("config profile censo pull", True),
        ("config profile edit operator", False),
        ("config profile delete operator --yes", False),
        ("config profile duplicate operator operator-copy", False),
        ("config profile rename operator renamed", False),
        ("config switch operator", False),
        ("app ledger list", False),
        ("app registry legal view ley-37-1992:art-99", False),
    ),
)
def test_profile_bound_write_verb_catalogue_classifies_operator_paths(verb_path: str, expected: bool) -> None:
    assert is_profile_bound_write_verb_path(verb_path) is expected

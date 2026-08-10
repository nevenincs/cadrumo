"""Storage write-policy backend tests."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from ...core import STORAGE_ROOT_SETTINGS_FIELD, BucketPointer, write_pointer
from ...core.config import Settings, StorageRouteKind
from ...core.external_constants import OutputLanguage
from ..storage_write_policy import (
    PROFILE_BOUND_WRITE_VERB_PATHS,
    StorageWritePolicyCode,
    inspect_storage_write_policy,
    is_profile_bound_write_verb_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_BOUND_VERB_CASES = (
    ("app ledger link tx --invoice-id inv", True),
    ("app ledger rule add --description-pattern fuel --classification expense", True),
    ("app ledger rule apply --dry-run", True),
    ("app modelo work file abc", True),
    ("config profile edit operator", False),
    ("config profile delete operator --yes", False),
    ("config profile duplicate operator operator-copy", False),
    ("config profile rename operator renamed", False),
    ("config login operator", False),
    ("app ledger list", False),
    ("app registry legal view ley-37-1992:art-99", False),
)


def test_profile_bound_write_verb_catalogue_has_unique_entries() -> None:
    assert len(PROFILE_BOUND_WRITE_VERB_PATHS) == len(set(PROFILE_BOUND_WRITE_VERB_PATHS))
    assert "config reset" not in PROFILE_BOUND_WRITE_VERB_PATHS


_STORAGE_WRITE_POLICY_SCENARIOS = (
    (
        "bootstrap_exempt",
        "config profile create operator",
        True,
        "explicit",
        None,
        {
            "allowed": True,
            "code": "bootstrap_exempt",
            "profile_bound_write": False,
            "bootstrap_exempt": True,
            "route_kind": None,
            "message_key": "",
            "detail_message_key": "",
            "verdict": None,
        },
    ),
    (
        "no_verb_path",
        None,
        False,
        "root",
        None,
        {
            "allowed": True,
            "code": "no_verb_path",
            "profile_bound_write": False,
            "bootstrap_exempt": False,
            "route_kind": None,
            "message_key": "",
            "detail_message_key": "",
            "verdict": None,
        },
    ),
    (
        "non_profile_bound_verb",
        "config login does-not-exist",
        False,
        "root",
        None,
        {
            "allowed": True,
            "code": "non_profile_bound_verb",
            "profile_bound_write": False,
            "bootstrap_exempt": False,
            "route_kind": None,
            "message_key": "",
            "detail_message_key": "",
            "verdict": None,
        },
    ),
    (
        "leaf_refusal_delegated",
        "app modelo work create",
        False,
        "root",
        ("app", "modelo", "work", "create", "--modelo", "151", "--year", "2025", "--period", "ANNUAL"),
        {
            "allowed": True,
            "code": "leaf_refusal_delegated",
            "profile_bound_write": True,
            "bootstrap_exempt": False,
            "route_kind": None,
            "message_key": "",
            "detail_message_key": "",
            "verdict": None,
        },
    ),
    (
        "allowed_active_bucket",
        "app modelo work calculate work-1",
        False,
        "active",
        None,
        {
            "allowed": True,
            "code": "allowed_active_bucket",
            "profile_bound_write": True,
            "bootstrap_exempt": False,
            "route_kind": "active_bucket_database",
            "message_key": "",
            "detail_message_key": "",
            "verdict": None,
        },
    ),
    (
        "refused_root_fallback",
        "app ledger add",
        False,
        "root",
        None,
        {
            "allowed": False,
            "code": "refused_root_fallback",
            "profile_bound_write": True,
            "bootstrap_exempt": False,
            "route_kind": "root_fallback_database",
            "message_key": "cli.config.errors.no_active_profile",
            "detail_message_key": "",
            "verdict": {
                "failed_condition_id": "profile.active",
                "evidence": [
                    {
                        "condition_id": "profile.active",
                        "evidence_id": "profile.active.storage_route",
                        "provenance": "runtime_observation",
                        "values": {
                            "active_bucket_attached": False,
                            "active_profile_present": False,
                            "route_kind": "root_fallback_database",
                        },
                    },
                ],
                "action": {"action_id": "operator.profile.create"},
                "argument_bindings": [
                    {
                        "argument_name": "profile_name",
                        "status": "missing",
                        "value": None,
                        "source": None,
                        "source_key": None,
                        "source_evidence_id": None,
                    },
                ],
                "missing_argument_names": ["profile_name"],
                "conditionality": "requires_arguments",
                "no_recovery_outcome": None,
            },
        },
    ),
    (
        "refused_explicit_database_url",
        "config google login",
        False,
        "explicit",
        None,
        {
            "allowed": False,
            "code": "refused_explicit_database_url",
            "profile_bound_write": True,
            "bootstrap_exempt": False,
            "route_kind": "explicit_database_url",
            "message_key": "errors.storage.runtime.not_ready",
            "detail_message_key": "errors.storage.runtime.route_not_active_bucket",
            "verdict": {
                "failed_condition_id": "storage.route.active_bucket",
                "evidence": [
                    {
                        "condition_id": "storage.route.active_bucket",
                        "evidence_id": "storage.route.active_bucket.classification",
                        "provenance": "runtime_observation",
                        "values": {
                            "active_bucket_attached": False,
                            "database_url_explicit": True,
                            "explicit_route_setting": "CADRUMO_DATABASE_URL",
                            "route_kind": "explicit_database_url",
                            "storage_root_setting": "CADRUMO_LOCAL_STORAGE_ROOT",
                        },
                    },
                ],
                "action": None,
                "argument_bindings": [],
                "missing_argument_names": [],
                "conditionality": "not_applicable",
                "no_recovery_outcome": "operator_decision",
            },
        },
    ),
)


def test_storage_write_policy_scenario_keys_reconcile_live_classifications() -> None:
    scenario_keys = tuple(row[0] for row in _STORAGE_WRITE_POLICY_SCENARIOS)
    duplicate_keys = {key for key in scenario_keys if scenario_keys.count(key) > 1}

    assert not duplicate_keys
    assert set(scenario_keys) == {code.value for code in StorageWritePolicyCode}


@pytest.mark.parametrize(
    (
        "scenario_key",
        "verb_path",
        "bootstrap_exempt",
        "route_setup",
        "argv_tokens",
        "expected",
    ),
    _STORAGE_WRITE_POLICY_SCENARIOS,
    ids=[row[0] for row in _STORAGE_WRITE_POLICY_SCENARIOS],
)
def test_storage_write_policy_exact_scenario_matrix(
    tmp_path: Path,
    scenario_key: str,
    verb_path: str | None,
    bootstrap_exempt: bool,
    route_setup: Literal["root", "active", "explicit"],
    argv_tokens: tuple[str, ...] | None,
    expected: dict[str, object],
) -> None:
    if route_setup == "active":
        settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile="operator")
    elif route_setup == "explicit":
        settings = Settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        )
    else:
        settings = Settings(cadrumo_local_storage_root=tmp_path)

    decision = inspect_storage_write_policy(
        verb_path,
        bootstrap_exempt=bootstrap_exempt,
        settings=settings,
        argv_tokens=argv_tokens,
    )

    assert scenario_key == expected["code"]
    assert decision.model_dump(mode="json") == expected, scenario_key
    if decision.verdict is not None:
        assert (decision.verdict.action is not None) is not (decision.verdict.no_recovery_outcome is not None)

    if decision.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK:
        assert "No active profile" in decision.render_refusal_message(locale="en")
    elif decision.code is StorageWritePolicyCode.REFUSED_EXPLICIT_DATABASE_URL:
        rendered = decision.render_refusal_message(locale="en")
        assert "Storage runtime is not ready" in rendered
        assert "database route is not attached to an active profile bucket" in rendered
        assert settings.model_fields_set >= {"cadrumo_database_url", STORAGE_ROOT_SETTINGS_FIELD}
        assert {"CADRUMO_DATABASE_URL", "CADRUMO_LOCAL_STORAGE_ROOT"} <= Settings.env_var_names()
        assert decision.verdict is not None
        evidence = decision.verdict.evidence[0].values
        assert evidence["explicit_route_setting"] == "CADRUMO_DATABASE_URL"
        assert evidence["storage_root_setting"] == "CADRUMO_LOCAL_STORAGE_ROOT"


def test_profile_bound_write_allows_pointer_route_from_stale_settings(tmp_path: Path) -> None:
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=OutputLanguage.EN)
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
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=OutputLanguage.EN)

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
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=OutputLanguage.EN)

    decision = inspect_storage_write_policy(
        "app modelo work create 210 2025 EVENT-1 2025",
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
            "EVENT-1",
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
            cadrumo_local_storage_root=tmp_path,
            cadrumo_output_language=OutputLanguage.EN,
            cadrumo_m210_engine_live=True,
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
            cadrumo_local_storage_root=tmp_path,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.BOOTSTRAP_EXEMPT
    assert decision.route_kind is None


def test_read_only_and_recovery_verbs_do_not_trigger_write_policy(tmp_path: Path) -> None:
    decision = inspect_storage_write_policy(
        "config login does-not-exist",
        bootstrap_exempt=False,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )

    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.NON_PROFILE_BOUND_VERB
    assert decision.profile_bound_write is False
    assert decision.route_kind is None


def test_profile_bound_write_verb_catalogue_classifies_operator_paths() -> None:
    failures: list[str] = []
    for verb_path, expected in _PROFILE_BOUND_VERB_CASES:
        actual = is_profile_bound_write_verb_path(verb_path)
        if actual is not expected:
            failures.append(f"{verb_path!r}: expected {expected}, got {actual}")

    assert not failures, "\n".join(failures)

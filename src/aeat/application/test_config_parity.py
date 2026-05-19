"""Parity tests: aeat config profile create/show/status read one profile bucket.

Pins the contract that ``aeat config profile create``, ``aeat config
profile show`` and ``aeat config profile status`` share the active
profile bucket selected by ``WorkflowState``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'parity.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))


def _seed_active_profile(tax_id: str = "00000000T", activity: str = "design") -> None:
    """Seed an active profile through the profile application service."""

    from aeat.application.user_profile._orchestration import register_active_profile
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.user_profile import UserProfileFact

    repo = workflow_state_repository()
    facts = (
        UserProfileFact(path="identity.tax_id", value=tax_id),
        UserProfileFact(path="identity.name", value="operator"),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="activities.description", value=activity),
        UserProfileFact(path="provenance.source", value="manual_cli"),
    )
    repo.update(
        lambda state: register_active_profile(
            state,
            profile_id="default",
            display_name="operator",
            facts=facts,
        )
    )


def test_config_create_then_config_show_round_trips_iva_regime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written during profile create is readable via profile show."""

    _isolate(monkeypatch, tmp_path)
    created = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ]
    )
    assert created.exit_code == 0, created.output

    show_via_config = invoke_cached_cli(["--format", "json", "config", "profile", "show", "default"])
    assert show_via_config.exit_code == 0, show_via_config.output
    facts = {row["path"]: row["value"] for row in json.loads(show_via_config.output)["facts"]}
    assert facts["iva.regime"] == "GENERAL"

    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.user_profile import UserProfileLifecycleRepository
    from aeat.application.user_profile._orchestration import fact_value
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    with get_master_key_provider():
        workflow_state_repository().load()
        assert read_profile_bucket("default") is not None
        record = UserProfileLifecycleRepository(bucket_id="default").load("default")
        assert fact_value(record, "iva.regime") == "GENERAL"


def test_config_create_then_config_status_surfaces_assigned_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written during profile create surfaces in profile status."""

    _isolate(monkeypatch, tmp_path)
    created = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "design",
            "--iva-regime",
            "SIMPLIFICADO",
        ]
    )
    assert created.exit_code == 0, created.output

    status_result = invoke_cached_cli(["config", "profile", "status"])
    assert status_result.exit_code == 0, status_result.output
    assert "SIMPLIFICADO" in status_result.output


def test_retired_config_profile_set_is_not_registered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The retired point-mutation command must not re-enter the CLI tree."""

    _isolate(monkeypatch, tmp_path)

    result = invoke_cached_cli(["config", "profile", "set", "not.a.real.key", "value"])
    assert result.exit_code != 0
    assert "No such command" in result.output

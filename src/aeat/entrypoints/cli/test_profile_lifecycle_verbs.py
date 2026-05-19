"""CLI surface tests for `aeat config profile {switch, show, delete, duplicate}`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._config import profile_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.adapters.persistence.storage import get_master_key_provider

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'profile-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        with get_master_key_provider():
            yield
    finally:
        dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _seed(name: str = "default") -> None:
    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=name))


def _json_payload(result: Result) -> dict[str, object]:
    match = re.search(r"\{.*\}", result.output, re.DOTALL)
    assert match, result.output
    return json.loads(match.group(0))


def test_config_profile_switch_activates_existing_profile(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("spouse")
    result = cli_runner.invoke(profile_app, ["switch", "operator"])
    assert result.exit_code == 0, result.output
    assert "active_profile\toperator" in result.output


def test_config_profile_switch_refuses_unknown_profile(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(profile_app, ["switch", "ghost"])
    assert result.exit_code != 0


def test_config_profile_switch_emits_profile_activated_event(cli_runner: CliRunner) -> None:
    """`config profile switch` records a typed PROFILE_ACTIVATED event in the
    bucket-event-history catalogue so downstream auditors can replay
    the activation timeline. Distinct from PROFILE_SELECTED (which
    captures workflow-state-level selection).
    """

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _seed("operator")
    result = cli_runner.invoke(profile_app, ["switch", "operator"])
    assert result.exit_code == 0, result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.PROFILE_ACTIVATED
        and event.object_id == "operator"
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["profile_id"] == "operator"
    assert matching[-1].payload["active_profile"] == "operator"


def test_config_profile_show_emits_active_profile_facts(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["show"])
    assert result.exit_code == 0, result.output
    assert "profile_id\toperator" in result.output
    assert "identity.tax_id\t00000000T" in result.output


def test_config_profile_show_named_profile_includes_canonical_facts(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("spouse")
    result = cli_runner.invoke(profile_app, ["show", "spouse"])
    assert result.exit_code == 0, result.output
    assert "profile_id\tspouse" in result.output
    assert "identity.tax_id\t00000000T" in result.output
    assert "iva.regime\tGENERAL" in result.output
    assert "tax_residence.ccaa\tmadrid" in result.output


def test_config_profile_delete_requires_yes(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["delete", "operator"])
    assert result.exit_code != 0


def test_config_profile_delete_tombstones_with_yes(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["delete", "operator", "--yes"])
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    from aeat.application.workflow._models import resolve_active_bucket_id

    state = workflow_state_repository().load()
    assert resolve_active_bucket_id() is None


def test_config_profile_duplicate_copies_to_new_id(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(
        profile_app,
        ["duplicate", "operator", "operator-spouse", "--display-name", "Spouse"],
    )
    assert result.exit_code == 0, result.output
    assert "target_profile_id\toperator-spouse" in result.output
    assert "display_name\tSpouse" in result.output
    state = workflow_state_repository().load()
    assert "operator-spouse" in state.profiles


def test_config_profile_duplicate_refuses_existing_target(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("operator-spouse")
    result = cli_runner.invoke(profile_app, ["duplicate", "operator", "operator-spouse"])
    assert result.exit_code != 0


def test_config_profile_validate_emits_validation_report(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["validate"])
    assert result.exit_code == 0, result.output
    assert "profile_id\toperator" in result.output
    assert "valid\t" in result.output


def test_config_profile_validate_refuses_when_no_active_profile(cli_runner: CliRunner) -> None:
    # Clear the active-profile precedence chain (env + pointer) so the
    # resolver returns None and the validate verb refuses.
    from aeat.application.user_profile._orchestration import _clear_active_profile_pointer
    from aeat.core.config import override_settings

    _clear_active_profile_pointer()
    with override_settings(aeat_active_profile=None):
        result = cli_runner.invoke(profile_app, ["validate"])
    assert result.exit_code != 0


def test_config_profile_preflight_emits_report(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(
        profile_app,
        [
            "preflight",
            "--modelo",
            "303",
            "--revision-id",
            "rev1",
            "--year",
            "2026",
            "--period",
            "Q1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "modelo\t303" in result.output
    assert "ready\t" in result.output

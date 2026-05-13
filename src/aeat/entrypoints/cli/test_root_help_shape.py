"""Real CLI tests for workflow-oriented root help and bare invocation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.operator_surface import build_help_document
from aeat.application.profile import set_active_profile
from aeat.application.workflow import workflow_state_repository

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'help.db').as_posix()}")


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


def _command_path_for_help_probe(command: str) -> list[str] | None:
    if " -> " in command or "rejected" in command:
        return None
    tokens = command.split()
    assert tokens[0] == "aeat"
    return [token for token in tokens[1:] if token.upper() != token]


def test_root_help_uses_curated_two_root_shape() -> None:
    result = _invoke(["--help"])

    assert result.exit_code == 0, result.output
    assert "The CLI has exactly two roots: config and app." in result.output
    assert "Setup" in result.output
    assert "Daily ledger work" in result.output
    assert "Modelo lifecycle" in result.output
    assert "Common mistypes" in result.output
    assert "aeat config init" in result.output
    assert "aeat app overview status" in result.output
    assert "aeat app live" not in result.output
    assert "aeat config bucket" not in result.output


def test_config_and_app_help_use_curated_subtree_shape() -> None:
    config = _invoke(["config", "--help"])
    app_result = _invoke(["app", "--help"])

    assert config.exit_code == 0, config.output
    assert "aeat config - profile, auth, diagnostics" in config.output
    assert "aeat config profile set KEY VALUE" in config.output
    assert "Run aeat --help for the full overview." in config.output

    assert app_result.exit_code == 0, app_result.output
    assert "aeat app - operational tax work" in app_result.output
    assert "aeat app ledger import" in app_result.output
    assert "aeat app modelo bindings" in app_result.output
    assert "aeat app invoice" not in app_result.output
    assert "aeat app declaration" not in app_result.output


def test_curated_help_command_rows_resolve_in_real_typer_tree() -> None:
    for surface in ("root", "config", "app"):
        document = build_help_document(surface)
        for section in document.sections:
            for entry in section.entries:
                command_path = _command_path_for_help_probe(entry.command)
                if command_path is None:
                    continue
                result = _invoke([*command_path, "--help"])
                assert result.exit_code == 0, f"{entry.command}\n{result.output}"
                assert "No such command" not in result.output


def test_bare_invocation_reports_profile_state_without_cli_only_storage() -> None:
    missing = _invoke([])
    workflow_state_repository().update(lambda current: set_active_profile(current, "operator"))
    active = _invoke([])
    overview = _invoke(["app", "overview", "status"])

    assert missing.exit_code == 0, missing.output
    assert "No active profile." in missing.output
    assert "Next: aeat config init" in missing.output

    assert active.exit_code == 0, active.output
    assert overview.exit_code == 0, overview.output
    assert active.output == overview.output
    assert "profile\toperator" in active.output


def test_root_help_and_bare_invocation_use_root_format_json() -> None:
    help_result = _invoke(["--format", "json", "--help"])

    assert help_result.exit_code == 0, help_result.output
    help_payload = json.loads(help_result.output)
    assert help_payload["surface"] == "root"
    assert help_payload["heading"].startswith("aeat - local-first")

    workflow_state_repository().update(lambda current: set_active_profile(current, "operator"))
    active = _invoke(["--format", "json"])

    assert active.exit_code == 0, active.output
    active_payload = json.loads(active.output)
    assert active_payload["active_profile"] == "operator"
    assert active_payload["transactions"] == 0

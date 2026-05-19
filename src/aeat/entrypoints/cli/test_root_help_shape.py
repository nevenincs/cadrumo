"""Real CLI tests for workflow-oriented root help and bare invocation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.operator_surface import build_help_document
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow import workflow_state_repository
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'help.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    with EphemeralMasterKeyProvider():
        yield
    dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _console_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "AEAT_SECRET_STORE_BACKEND": "unsecured",
            "AEAT_ALLOW_UNENCRYPTED": "1",
            "AEAT_DATABASE_URL": f"sqlite:///{(tmp_path / 'console.db').as_posix()}",
            "AEAT_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "AEAT_TOKEN_DIR": str(tmp_path / "tokens"),
            "AEAT_RUNS_DIR": str(tmp_path / "runs"),
            "AEAT_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
            "AEAT_INVOICES_DIR": str(tmp_path / "invoices"),
            "AEAT_DRAFTS_DIR": str(tmp_path / "drafts"),
        }
    )
    return env


def _command_path_for_help_probe(command: str) -> list[str] | None:
    if " -> " in command or "rejected" in command:
        return None
    tokens = command.split()
    assert tokens[0] == "aeat"
    return [token for token in tokens[1:] if token.upper() != token]


def test_root_help_uses_curated_two_root_shape() -> None:
    result = _invoke(["--help"])
    retired_init = "aeat config " + "init"

    assert result.exit_code == 0, result.output
    assert "The CLI has exactly two roots: config and app." in result.output
    assert "Setup" in result.output
    assert "Daily ledger work" in result.output
    assert "Modelo lifecycle" in result.output
    assert "Common mistypes" not in result.output
    assert "aeat config profile create NAME" in result.output
    assert retired_init not in result.output
    assert "aeat app overview status" in result.output
    assert "aeat app live filed list" in result.output
    assert "aeat config bucket" not in result.output


def test_config_and_app_help_use_curated_subtree_shape() -> None:
    config = _invoke(["config", "--help"])
    app_result = _invoke(["app", "--help"])
    retired_init = "aeat config " + "init"

    assert config.exit_code == 0, config.output
    assert "aeat config - profile, auth, diagnostics" in config.output
    assert "aeat config profile create NAME" in config.output
    assert "aeat config profile show [NAME]" in config.output
    assert ("aeat config profile " + "view [NAME]") not in config.output
    assert retired_init not in config.output
    assert "Run aeat --help for the full overview." in config.output

    assert app_result.exit_code == 0, app_result.output
    assert "aeat app - operational tax work" in app_result.output
    assert "aeat app ledger import" in app_result.output
    assert "aeat app live filed capture" in app_result.output
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
    workflow_state_repository().update(lambda current: register_minimal_profile(current, profile_id="operator"))
    active = _invoke([])
    overview = _invoke(["app", "overview", "status"])

    assert missing.exit_code == 0, missing.output
    assert "aeat config profile create NAME" in missing.output
    assert ("aeat config " + "init") not in missing.output
    assert "aeat app overview status" in missing.output
    assert "aeat app ledger import" in missing.output

    assert active.exit_code == 0, active.output
    assert overview.exit_code == 0, overview.output
    assert active.output != overview.output
    assert "aeat app overview status" in active.output
    assert "aeat app ledger import" in active.output
    assert "`operator`" in overview.output
    assert "profile\t" not in overview.output.lower()
    assert "integrity-warning" not in overview.output
    assert "unreadable_rows" not in overview.output


def test_installed_console_base_command_starts_clean_workspace(tmp_path: Path) -> None:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None

    result = subprocess.run(
        [aeat_exe],
        cwd=Path.cwd(),
        env=_console_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined_output
    assert "aeat config profile create NAME" in result.stdout
    assert ("aeat config " + "init") not in result.stdout
    assert "aeat app overview status" in result.stdout
    assert "aeat app ledger import" in result.stdout
    assert "aeat config repair" in result.stdout
    assert "Traceback" not in combined_output
    assert "ImportError" not in combined_output
    assert "integrity-warning" not in combined_output
    assert "unreadable_rows" not in combined_output


def test_installed_console_profile_create_fails_fast_without_prompt_host(tmp_path: Path) -> None:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None

    result = subprocess.run(
        [aeat_exe, "config", "profile", "create", "operator"],
        cwd=Path.cwd(),
        env=_console_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, combined_output
    assert "aeat config profile create NAME" in combined_output
    assert "aeat config repair" in combined_output
    assert "aeat config reset --scope profile --yes" in combined_output
    assert ("aeat config " + "init") not in combined_output
    assert "1/9" not in combined_output
    assert "REFUSED" not in combined_output
    assert "Traceback" not in combined_output


def test_root_help_and_bare_invocation_use_root_format_json() -> None:
    help_result = _invoke(["--format", "json", "--help"])

    assert help_result.exit_code == 0, help_result.output
    help_payload = json.loads(help_result.output)
    assert help_payload["surface"] == "root"
    assert help_payload["heading"].startswith("aeat - local-first")

    workflow_state_repository().update(lambda current: register_minimal_profile(current, profile_id="operator"))
    active = _invoke(["--format", "json"])

    assert active.exit_code == 0, active.output
    active_payload = json.loads(active.output)
    assert active_payload["active_profile"] == "operator"
    assert active_payload["transactions"] == 0

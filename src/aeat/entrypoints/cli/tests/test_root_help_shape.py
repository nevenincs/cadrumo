"""Real CLI tests for workflow-oriented root help and bare invocation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.operator_surface import build_help_document
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow import workflow_state_repository
from ....core.config import SecretStoreBackend, Settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root, isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    # Most tests in this file only invoke --help or subprocess-isolated
    # commands; they need storage isolation but no active session.
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _console_env(tmp_path: Path) -> dict[str, str]:
    base_settings = Settings.model_validate({})
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    setting_env = str.upper
    env.update(
        {
            setting_env("aeat_secret_store_backend"): SecretStoreBackend.FILE.value,
            setting_env("aeat_secret_passphrase"): (base_settings.aeat_dev_test_database_password.get_secret_value()),
            setting_env("aeat_secret_store_dir"): str(tmp_path / "storage" / "secrets"),
            setting_env("aeat_local_storage_root"): str(tmp_path / "storage"),
            setting_env("aeat_token_dir"): str(tmp_path / "tokens"),
            setting_env("aeat_runs_dir"): str(tmp_path / "runs"),
            setting_env("aeat_financial_txs_dir"): str(tmp_path / "txs"),
            setting_env("aeat_invoices_dir"): str(tmp_path / "invoices"),
            setting_env("aeat_drafts_dir"): str(tmp_path / "drafts"),
            setting_env("aeat_output_language"): "en",
        },
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
    assert "AEAT_LOCAL_STORAGE_ROOT" in result.output
    assert "AEAT_SECRET_STORE_DIR" in result.output
    assert "AEAT_SECRET_PASSPHRASE" in result.output
    assert "aeat config bucket" not in result.output


def test_config_and_app_help_use_curated_subtree_shape() -> None:
    config = _invoke(["config", "--help"])
    app_result = _invoke(["app", "--help"])
    retired_init = "aeat config " + "init"

    assert config.exit_code == 0, config.output
    assert "aeat config - profile, auth, diagnostics" in config.output
    assert "aeat config profile create NAME" in config.output
    assert "AEAT_LOCAL_STORAGE_ROOT" in config.output
    assert "AEAT_SECRET_STORE_BACKEND=file" in config.output
    assert "aeat config profile show [NAME]" in config.output
    assert ("aeat config profile " + "view [NAME]") not in config.output
    assert retired_init not in config.output
    assert "Run aeat --help for the full overview." in config.output

    assert app_result.exit_code == 0, app_result.output
    assert "aeat app - operational tax work" in app_result.output
    assert "aeat app ledger import" in app_result.output
    assert "aeat app live filed pull" in app_result.output
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


def test_installed_console_profile_create_honors_isolated_storage_env(tmp_path: Path) -> None:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None
    env = _console_env(tmp_path)

    create = subprocess.run(
        [
            aeat_exe,
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Storage",
            "--irpf-income-categories",
            "actividad_economica",
            "--activity",
            "Design consulting",
            "--address-postcode",
            "28015",
            "--activity-start-date",
            "2025-01-01",
            "--tax-residence-ccaa",
            "madrid",
            "--iva-regime",
            "general",
            "--irpf-estimation-regime",
            "directa_simplificada",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    combined_create = f"{create.stdout}\n{create.stderr}"
    assert create.returncode == 0, combined_create

    logs = subprocess.run(
        [aeat_exe, "config", "repair", "logs"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    combined_logs = f"{logs.stdout}\n{logs.stderr}"
    assert logs.returncode == 0, combined_logs
    assert str(tmp_path / "storage" / "logs") in combined_logs

    listed = subprocess.run(
        [aeat_exe, "config", "profile", "list"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    combined_list = f"{listed.stdout}\n{listed.stderr}"
    assert listed.returncode == 0, combined_list
    assert "operator" in listed.stdout


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
    # The no-console refusal names both recovery paths a first-timer can
    # act on: re-run from an interactive terminal, or supply the
    # required details as flags in one step.
    assert "aeat config profile create NAME" in combined_output
    assert "--quiet --tax-id NIF/CIF/DNI/NIE" in combined_output
    # The refusal must not push corruption-recovery commands at an
    # operator whose only problem is the absence of an interactive
    # terminal; that wording wrongly implies the profile state is bad.
    assert "aeat config repair" not in combined_output
    assert "aeat config reset" not in combined_output
    assert ("aeat config " + "init") not in combined_output
    assert "1/9" not in combined_output
    assert "REFUSED" not in combined_output
    assert "Traceback" not in combined_output


class TestBareInvocationWithActiveProfile:
    """Tests that call register_minimal_profile need a file-backed storage root.

    register_minimal_profile goes through build_lifecycle_service →
    _secure_objects_for_bucket → runtime.require_ready(), which needs an
    active bucket session. profile_create_storage_span initialises the key
    material and activates the session for the target profile_id so the
    call succeeds without a pre-provisioned test bucket in the profile list.
    """

    @pytest.fixture(autouse=True)
    def _isolated_state(self, tmp_path: Path) -> Iterator[None]:
        # Overrides the module-level _isolated_state. Uses profile_storage_root
        # (not sessionless) so profile_create_storage_span can resolve a
        # file-backed master-key provider and provision key material.
        with isolated_profile_storage_root(tmp_path=tmp_path):
            yield

    def test_bare_invocation_reports_profile_state_without_cli_only_storage(self) -> None:
        missing = _invoke([])
        with profile_create_storage_span("operator"):
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

    def test_root_help_and_bare_invocation_use_root_format_json(self) -> None:
        help_result = _invoke(["--format", "json", "--help"])

        assert help_result.exit_code == 0, help_result.output
        help_envelope = json.loads(help_result.output)
        help_payload = help_envelope.get("result", help_envelope)
        assert help_payload["surface"] == "root"
        assert help_payload["heading"]  # locale-driven; presence is the structural assertion

        with profile_create_storage_span("operator"):
            workflow_state_repository().update(lambda current: register_minimal_profile(current, profile_id="operator"))
        active = _invoke(["--format", "json"])

        assert active.exit_code == 0, active.output
        active_envelope = json.loads(active.output)
        active_payload = active_envelope.get("result", active_envelope)
        assert active_payload["active_profile"] == "operator"
        # The RootLandingReport model carries (active_profile, command, message);
        # `transactions` is not part of the bare-invocation payload contract.
        assert "command" in active_payload
        assert "message" in active_payload

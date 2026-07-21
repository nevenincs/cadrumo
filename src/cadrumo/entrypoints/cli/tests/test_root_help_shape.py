"""Real CLI tests for workflow-oriented root help and bare invocation."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from .... import __version__
from ....application.operator_surface import build_help_document
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core import PRODUCT_IDENTITY
from ....core.config import SecretStoreBackend, Settings
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root, isolated_sessionless_storage_root
from ....tests.user_profile import register_minimal_profile

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
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("AEAT_", "CADRUMO_"))}
    setting_env = str.upper
    env.update(
        {
            setting_env("cadrumo_secret_store_backend"): SecretStoreBackend.FILE.value,
            setting_env("cadrumo_secret_passphrase"): (
                base_settings.cadrumo_dev_test_database_password.get_secret_value()
            ),
            setting_env("cadrumo_secret_store_dir"): str(tmp_path / "storage" / "secrets"),
            setting_env("cadrumo_local_storage_root"): str(tmp_path / "storage"),
            setting_env("cadrumo_token_dir"): str(tmp_path / "tokens"),
            setting_env("cadrumo_runs_dir"): str(tmp_path / "runs"),
            setting_env("cadrumo_financial_txs_dir"): str(tmp_path / "txs"),
            setting_env("cadrumo_invoices_dir"): str(tmp_path / "invoices"),
            setting_env("cadrumo_drafts_dir"): str(tmp_path / "drafts"),
            setting_env("cadrumo_output_language"): "en",
        },
    )
    scripts_dir = str(Path(sys.executable).parent)
    env["PATH"] = os.pathsep.join((scripts_dir, env.get("PATH", "")))
    return env


def _installed_cli_executable() -> Path:
    """Return the CLI script installed beside the active test interpreter."""
    suffix = ".exe" if os.name == "nt" else ""
    executable = Path(sys.executable).with_name(f"{PRODUCT_IDENTITY.cli_executable}{suffix}")
    assert executable.is_file(), (
        f"the {PRODUCT_IDENTITY.cli_executable} console script must be installed at {executable}"
    )
    return executable


def _command_path_for_help_probe(command: str) -> list[str] | None:
    if " -> " in command or "rejected" in command:
        return None
    tokens = command.split()
    assert tokens[0] == PRODUCT_IDENTITY.cli_executable
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
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in result.output
    assert "CADRUMO_SECRET_STORE_DIR" in result.output
    assert "CADRUMO_SECRET_PASSPHRASE" in result.output
    assert "aeat config bucket" not in result.output


def test_config_and_app_help_use_curated_subtree_shape() -> None:
    config = _invoke(["config", "--help"])
    config_json = _invoke(["--format", "json", "config", "--help"])
    app_result = _invoke(["app", "--help"])
    retired_init = "aeat config " + "init"

    assert config.exit_code == 0, config.output
    assert config_json.exit_code == 0, config_json.output
    assert "aeat config - profile, auth, diagnostics" in config.output
    assert "aeat config profile create NAME" in config.output
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in config.output
    assert "CADRUMO_SECRET_STORE_BACKEND=file" in config.output
    assert "aeat config profile show [NAME]" in config.output
    assert ("aeat config profile " + "view [NAME]") not in config.output
    assert retired_init not in config.output
    assert "Run aeat --help for the full overview." in config.output
    config_envelope = json.loads(config_json.output)
    assert config_envelope["command"] == "root.config"
    assert config_envelope["result"]["surface"] == "config"

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
    cli_executable = _installed_cli_executable()

    result = subprocess.run(
        [cli_executable],
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


def test_installed_console_exposes_contextual_product_identity(tmp_path: Path) -> None:
    """The sole human executable exposes the binding Cadrumo identity tuple."""
    cli_executable = _installed_cli_executable()
    env = _console_env(tmp_path)

    version = subprocess.run(
        [cli_executable, "--version"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    help_result = subprocess.run(
        [cli_executable, "--language", "en", "--help"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert version.returncode == 0, version.stderr
    assert version.stdout == f"{PRODUCT_IDENTITY.display_name} {__version__}\n"
    assert __version__ == "0.2.1"
    assert help_result.returncode == 0, help_result.stderr
    assert help_result.stdout.startswith(f"{PRODUCT_IDENTITY.display_name} -")
    assert f"{PRODUCT_IDENTITY.cli_executable} config" in help_result.stdout
    assert "AEAT" in help_result.stdout
    assert f"{PRODUCT_IDENTITY.python_package} config" not in help_result.stdout

    suffix = ".exe" if os.name == "nt" else ""
    human_alias = Path(sys.executable).with_name(f"{PRODUCT_IDENTITY.python_package}{suffix}")
    assert not human_alias.exists(), f"unexpected human CLI alias installed at {human_alias}"


def test_uv_no_sync_console_help_starts_from_repo_root(tmp_path: Path) -> None:
    uv_exe = shutil.which("uv")
    assert uv_exe is not None

    result = subprocess.run(
        [uv_exe, "run", "--no-sync", PRODUCT_IDENTITY.cli_executable, "--help"],
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
    assert "aeat app overview status" in result.stdout
    assert "aeat app ledger import" in result.stdout
    assert "Failed to spawn" not in combined_output
    assert "program not found" not in combined_output


@pytest.mark.parametrize(
    "arguments",
    [
        ("--help",),
        ("app", "--help"),
        ("config", "--help"),
        ("config", "profile", "--help"),
    ],
)
def test_installed_console_help_does_not_adopt_former_product_state(tmp_path: Path, arguments: tuple[str, ...]) -> None:
    """Help remains available when Cadrumo correctly refuses legacy state."""
    cli_executable = _installed_cli_executable()
    former_root = tmp_path / "former-product-state"
    former_root.mkdir()
    with sqlite3.connect(former_root / "aeat.db"):
        pass
    env = _console_env(tmp_path)
    env["CADRUMO_LOCAL_STORAGE_ROOT"] = str(former_root)

    result = subprocess.run(
        [cli_executable, *arguments],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined_output
    assert "FormerProductStateError" not in combined_output
    assert PRODUCT_IDENTITY.cli_executable in result.stdout


def test_installed_console_refuses_former_product_state_without_a_traceback(tmp_path: Path) -> None:
    """A normal command routes the hard state refusal through the CLI boundary."""
    cli_executable = _installed_cli_executable()
    former_root = tmp_path / "former-product-state"
    former_root.mkdir()
    with sqlite3.connect(former_root / "aeat.db"):
        pass
    env = _console_env(tmp_path)
    env["CADRUMO_LOCAL_STORAGE_ROOT"] = str(former_root)

    result = subprocess.run(
        [cli_executable, "config", "profile", "list"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "Traceback" not in combined_output
    assert "incompatible retired `aeat` database named 'aeat.db'" in combined_output


def test_installed_console_profile_create_honors_isolated_storage_env(tmp_path: Path) -> None:
    cli_executable = _installed_cli_executable()
    env = _console_env(tmp_path)

    create = subprocess.run(
        [
            cli_executable,
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
        [cli_executable, "config", "repair", "logs"],
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
        [cli_executable, "config", "profile", "list"],
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
    cli_executable = _installed_cli_executable()

    result = subprocess.run(
        [cli_executable, "config", "profile", "create", "operator"],
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
        with profile_create_storage_span("11111111-1111-4111-8111-111111111111"):
            workflow_state_repository().update(
                lambda current: register_minimal_profile(
                    current,
                    profile_id="11111111-1111-4111-8111-111111111111",
                    display_name="operator",
                )
            )
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

        with profile_create_storage_span("11111111-1111-4111-8111-111111111111"):
            workflow_state_repository().update(
                lambda current: register_minimal_profile(
                    current,
                    profile_id="11111111-1111-4111-8111-111111111111",
                    display_name="operator",
                )
            )
        active = _invoke(["--format", "json"])

        assert active.exit_code == 0, active.output
        active_envelope = json.loads(active.output)
        active_payload = active_envelope.get("result", active_envelope)
        # The root landing report carries the raw active bucket id, which the
        # output redaction funnel replaces with the profile-id placeholder
        # before it reaches the operator (see ``core.redaction``).
        assert active_payload["active_profile"] == CLI_PROFILE_ID_PLACEHOLDER
        # The RootLandingReport model carries (active_profile, command, message);
        # `transactions` is not part of the bare-invocation payload contract.
        assert "command" in active_payload
        assert "message" in active_payload

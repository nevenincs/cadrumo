"""Real CLI tests for workflow-oriented root help and bare invocation.

The ``"logs"`` literal in
``test_installed_console_profile_create_honors_isolated_storage_env`` is
deliberate: ``_console_env`` sets ``cadrumo_local_storage_root`` to
``tmp_path / "storage"`` with no log-directory override, so
``tmp_path / "storage" / "logs"`` is the real DEFAULT-derived location the
``config repair logs`` command's own output must report -- not an injected
value. That function does not use ``isolated_profile_storage_root``
(used elsewhere in this file); it is self-contained on ``_console_env``.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Final

import pytest

from ....tests.profile_capsule import open_test_profile_session
from ._profile_storage_fixtures import isolated_profile_storage

__all__ = ["isolated_profile_storage"]

from .... import __version__
from ....application.operator_surface import build_help_document
from ....core import PRODUCT_IDENTITY, BucketPointer, OutputLanguage, write_pointer
from ....core.config import SecretStoreBackend, Settings, load_settings
from ....core.i18n import tr
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.user_profile import register_minimal_profile
from ._isolated_profile_storage_fixtures import _isolated_state

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_isolated_state"]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"logs"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def _invoke(args: list[str], *, pin_language: str | None = "en"):
    """Invoke the CLI, pinning the rendered language for curated-help assertions.

    The tests below assert the ENGLISH curated help prose, while the configured
    output language defaults to Spanish -- the same reason ``_console_env``
    already pins ``en`` for the installed-console probes. Pass
    ``pin_language=None`` where the invocation supplies its own ``--language``,
    so the flag decides rather than a settings override outranking it.
    """
    from ....core.config import override_settings

    if pin_language is None:
        return invoke_cached_cli(args)
    with override_settings(cadrumo_output_language=pin_language):
        return invoke_cached_cli(args)


def _option_row_count(output: str, option: str) -> int:
    """Return how many times ``option`` heads a row of the rendered options table."""
    return sum(1 for line in output.splitlines() if line.strip().startswith(option))


def _console_env(tmp_path: Path) -> dict[str, str]:
    base_settings = Settings.model_validate({})
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("AEAT_", "CADRUMO_"))}
    setting_env = str.upper
    env.update(
        {
            setting_env("cadrumo_secret_store_backend"): SecretStoreBackend.AUTO.value,
            setting_env("cadrumo_secret_passphrase"): (
                base_settings.cadrumo_dev_test_database_password.get_secret_value()
            ),
            setting_env("cadrumo_secret_store_dir"): str(tmp_path / "storage" / "fallback-store"),
            setting_env("cadrumo_local_storage_root"): str(tmp_path / "storage"),
            setting_env("cadrumo_token_dir"): str(tmp_path / "probe-tokens"),
            setting_env("cadrumo_runs_dir"): str(tmp_path / "probe-runs"),
            setting_env("cadrumo_financial_txs_dir"): str(tmp_path / "txs"),
            setting_env("cadrumo_invoices_dir"): str(tmp_path / "invoices"),
            setting_env("cadrumo_drafts_dir"): str(tmp_path / "probe-drafts"),
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
    assert "exactly two command roots" in result.output
    assert "Start or resume" in result.output
    assert "Core workflow" in result.output
    assert "Resume or recover" in result.output
    assert "Profile labels stay visible" in result.output
    assert "Common mistypes" not in result.output
    assert "aeat config profile create NAME" in result.output
    assert retired_init not in result.output
    assert "aeat app overview status" in result.output
    assert "aeat app modelo verification-report list" in result.output
    assert "aeat --format json config repair" in result.output
    assert "github.com/nevenincs/cadrumo/issues" in result.output
    assert "aeat config bucket" not in result.output


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_root_help_projects_both_graph_owned_profile_secret_options_once(language: OutputLanguage) -> None:
    result = _invoke(["--language", language.value, "--help"], pin_language=None)

    assert result.exit_code == 0, result.output
    # Count OPTION ROWS, not raw occurrences: the root help prose also names both
    # flags when telling the operator how to pass secrets, and that guidance is
    # not a second projection. The invariant is that the graph projects each
    # option exactly once into the options table.
    assert _option_row_count(result.output, "--profile-secrets-stdin") == 1
    assert _option_row_count(result.output, "--profile-secrets-fd") == 1
    assert tr("cli.config.custody.profile_secrets_stdin_help", locale=language) in result.output
    assert tr("cli.config.custody.profile_secrets_fd_help", locale=language) in result.output


def test_root_help_does_not_consume_or_close_a_selected_profile_secret_descriptor() -> None:
    read_descriptor, write_descriptor = os.pipe()
    payload = b"help-must-not-read-this"
    try:
        os.write(write_descriptor, payload)
        os.close(write_descriptor)
        write_descriptor = -1

        result = _invoke(["--profile-secrets-fd", str(read_descriptor), "--help"])

        assert result.exit_code == 0, result.output
        assert os.read(read_descriptor, len(payload)) == payload
    finally:
        if write_descriptor >= 0:
            os.close(write_descriptor)
        with suppress(OSError):
            os.close(read_descriptor)


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
    assert "CADRUMO_SECRET_STORE_DIR" in config.output
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


def test_bare_invocation_preserves_selected_profile_with_missing_manifest() -> None:
    """A valid active pointer with no manifest is degraded state, not blank state."""
    write_pointer(
        load_settings().cadrumo_local_storage_root,
        BucketPointer(bucket_id="11111111-1111-4111-8111-111111111111", schema_version=1),
    )

    text_result = _invoke([])
    json_result = _invoke(["--format", "json"])

    assert text_result.exit_code == 0, text_result.output
    assert "An active profile is selected, but its display label is unavailable." in text_result.output
    assert "aeat config repair profile" in text_result.output
    assert "aeat config profile create NAME" not in text_result.output
    assert CLI_PROFILE_ID_PLACEHOLDER not in text_result.output

    assert json_result.exit_code == 0, json_result.output
    document = json.loads(json_result.output)
    assert document["active_profile"] is None
    assert document["result"]["profile_selected"] is True
    assert document["result"]["active_profile"] is None
    assert document["result"]["command"] == "aeat config repair profile"
    assert CLI_PROFILE_ID_PLACEHOLDER not in json_result.output


# The custody and audit families the curated help MUST cite, keyed by the live
# command prefix that identifies each. The sibling resolve gate above proves a
# cited command exists; it is blind to a family the help simply OMITS. Each
# prefix is a live family: certificate credential custody and Modelo audit.
_REQUIRED_HELP_FAMILIES: dict[str, str] = {
    "certificate custody": "aeat config auth certificate",
    "modelo audit": "aeat app modelo audit",
}


def _curated_help_commands() -> list[str]:
    return [
        entry.command
        for surface in ("root", "config", "app")
        for section in build_help_document(surface).sections
        for entry in section.entries
    ]


def test_curated_help_covers_required_families() -> None:
    """The curated help must cite the required families, not just resolve what it cites.

    A surface omission is silent to the resolve and suggestion-conformance gates:
    they check that every cited command exists, never that a required family is
    cited at all. This gate closes that hole for the named families below.

    A prefix matches a citation when the citation is the family verb itself or a
    child of it (``prefix`` or ``prefix`` + a space).
    """
    commands = _curated_help_commands()
    assert len(commands) >= 40, (
        f"curated help cited only {len(commands)} commands; the documents look empty or collapsed"
    )

    missing = sorted(
        name
        for name, prefix in _REQUIRED_HELP_FAMILIES.items()
        if not any(command == prefix or command.startswith(prefix + " ") for command in commands)
    )
    assert not missing, (
        f"the curated help omits required families entirely: {missing}. A family the operator cannot "
        "discover from the curated surface is the silent-omission failure this gate exists to catch"
    )


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


def test_installed_console_honors_isolated_storage_env(tmp_path: Path) -> None:
    """The installed console script routes storage at the environment's root.

    The profile is registered in-process against the same root, because
    credential registration is the only creation door and no CLI verb can
    mint a profile. The claim under test -- that the installed script reads
    and writes the environment's storage root rather than the operator's real
    one -- is measured by the two subprocess runs below.
    """
    cli_executable = _installed_cli_executable()
    env = _console_env(tmp_path)

    from ....core.config import SecretStoreBackend, load_settings, override_settings
    from ....tests.user_profile import register_cli_profile

    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        register_cli_profile(
            label="operator",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Operator",
                "identity.surnames": "Storage",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "activities.description": "Design consulting",
                "contact.postcode": "28015",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.ccaa": "madrid",
                "iva.regime": "GENERAL",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
                "irpf.estimation_regime": "directa_simplificada",
            },
        )

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


@pytest.mark.usefixtures("isolated_profile_storage")
class TestBareInvocationWithActiveProfile:
    """Tests that call register_minimal_profile need a file-backed storage root.

    register_minimal_profile goes through build_lifecycle_service →
    _secure_objects_for_bucket → runtime.require_ready(), which needs an
    active bucket session. open_test_profile_session initialises the key
    material and activates the session for the target profile_id so the
    call succeeds without a pre-provisioned test bucket in the profile list.
    """

    def test_bare_invocation_reports_profile_state_without_cli_only_storage(self) -> None:
        missing = _invoke([])
        with open_test_profile_session("11111111-1111-4111-8111-111111111111"):
            register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111", display_name="operator")
        active = _invoke([])
        overview = _invoke(["app", "overview", "status"])

        assert missing.exit_code == 0, missing.output
        assert "aeat config profile create NAME" in missing.output
        assert ("aeat config " + "init") not in missing.output
        assert "aeat app overview status" in missing.output
        assert "aeat app ledger import" in missing.output

        assert active.exit_code == 0, active.output
        assert "Active profile: `operator`." in active.output
        assert CLI_PROFILE_ID_PLACEHOLDER not in active.output
        assert overview.exit_code == 0, overview.output
        assert active.output != overview.output
        assert "aeat app overview status" in active.output
        assert "aeat app ledger import" in active.output
        assert "`operator`" in overview.output
        assert "profile\t" not in overview.output.lower()
        assert "integrity-warning" not in overview.output
        assert "unreadable_rows" not in overview.output

    def test_bare_invocation_after_logout_points_to_login_not_create(self) -> None:
        """A registered profile without a selection is a login state, not first run."""

        with open_test_profile_session("11111111-1111-4111-8111-111111111111"):
            register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111", display_name="operator")
        logged_out = _invoke(["config", "logout"])
        landing = _invoke([])

        assert logged_out.exit_code == 0, logged_out.output
        assert "logged_out_profile\toperator" in logged_out.output
        assert landing.exit_code == 0, landing.output
        assert "aeat config login NAME" in landing.output
        assert "aeat config profile create NAME" not in landing.output

    def test_root_help_and_bare_invocation_use_root_format_json(self) -> None:
        help_result = _invoke(["--format", "json", "--help"])

        assert help_result.exit_code == 0, help_result.output
        help_envelope = json.loads(help_result.output)
        help_payload = help_envelope.get("result", help_envelope)
        assert help_payload["surface"] == "root"
        assert help_payload["heading"]  # locale-driven; presence is the structural assertion

        with open_test_profile_session("11111111-1111-4111-8111-111111111111"):
            register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111", display_name="operator")
        active = _invoke(["--format", "json"])

        assert active.exit_code == 0, active.output
        active_envelope = json.loads(active.output)
        active_payload = active_envelope.get("result", active_envelope)
        # The root landing report carries the operator-facing display label.
        # The outer envelope resolves the same label independently; neither
        # surface should receive the UUID and rely on redaction to turn a
        # storage identifier into a pretend operator identity.
        assert active_payload["active_profile"] == "operator"
        assert active_envelope["active_profile"] == "operator"
        assert CLI_PROFILE_ID_PLACEHOLDER not in active.output
        # The RootLandingReport model carries (active_profile, command, message);
        # `transactions` is not part of the bare-invocation payload contract.
        assert "command" in active_payload
        assert "message" in active_payload

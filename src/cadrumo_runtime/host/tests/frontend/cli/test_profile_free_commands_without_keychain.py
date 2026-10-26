"""Real-entrypoint coverage for signed-in commands on a host with no usable keychain.

A profile session is resumed from the OS keychain. On a host without one, a
command that needs the profile refuses unless the passphrase reaches it.
Component checks run the native components role, which reaches nothing a
profile holds, so they need no session. The child runs the real console script with a failing
keyring backend and no console, so no passphrase prompt can be reached.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.core.config import load_settings, override_settings

from .config.tests.isolated_storage_fixture import native_profile_view_server
from .fresh_process import run_fresh_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NO_KEYCHAIN = {"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"}


def _passphrase() -> str:
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _run(
    storage_root: Path, *args: str, stdin_payload: str | None = None, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    # Profile-bound leaves submit to the keychainless runtime that serves the root.
    with native_profile_view_server(storage_root, keychain_backend=_NO_KEYCHAIN["PYTHON_KEYRING_BACKEND"]):
        return run_fresh_cli(
            args,
            settings={
                "cadrumo_local_storage_root": str(storage_root),
                "cadrumo_secret_passphrase": _passphrase(),
                "cadrumo_output_language": "en",
            },
            env_strip_prefixes=("AEAT_", "PYTEST_"),
            extra_env={**_NO_KEYCHAIN, **(extra_env or {})},
            stdin_payload=stdin_payload,
        ).completed


@pytest.fixture
def active_profile_root(tmp_path: Path) -> Path:
    """Register a profile and leave it selected, as an operator's last login would."""
    with override_settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        profile_id = register_cli_profile(label="keychainless", log_in=False)
        from cadrumo.adapters.persistence.storage.sql.engine import dispose_engines_for_bucket

        dispose_engines_for_bucket(profile_id)
    return tmp_path


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


@pytest.mark.parametrize(
    ("arguments", "status"),
    [(("config", "provision", "status"), 0), (("config", "provision", "verify", "--item", "browser"), 2)],
)
def test_a_component_check_runs_without_sign_in_or_a_keychain(
    active_profile_root: Path, arguments: tuple[str, ...], status: int
) -> None:
    """The components role reaches nothing the profile holds, so a check needs no session; without a built
    binary every item reads as not in this build."""
    result = _run(active_profile_root, "--format", "json", *arguments, extra_env={DEVELOPMENT_ROLE_IMAGE_VARIABLE: ""})

    assert result.returncode == status, _combined(result)
    items = json.loads(result.stdout)["result"]["items"]
    assert {(item["state"], item["blocked_reason"]) for item in items} == {("blocked", "not_in_this_build")}
    assert "profile.session.logged_in" not in result.stderr


def test_a_profile_bound_command_still_refuses_without_a_keychain_or_a_console(active_profile_root: Path) -> None:
    """An encrypted profile read refuses through the same sign-in boundary."""
    result = _run(active_profile_root, "--format", "json", "config", "profile", "view", "keychainless")

    assert result.returncode != 0, _combined(result)
    envelope = json.loads(result.stderr)
    # The profile was never unlocked in a process that could keep its session,
    # so the gate answers with the login action rather than reading anything.
    assert envelope["error"]["code"] == "REFUSED_CLI_BOUNDARY", result.stderr
    assert envelope["error"]["action"]["failed_condition_id"] == "profile.session.logged_in"


def test_a_profile_bound_command_runs_when_the_passphrase_is_supplied(active_profile_root: Path) -> None:
    """Positive control for the refusal above: the same leaf authenticates for this invocation."""
    result = _run(
        active_profile_root,
        "--profile-secrets-stdin",
        "config",
        "profile",
        "view",
        "keychainless",
        stdin_payload=json.dumps({"profile_passphrase": _passphrase()}),
    )

    assert result.returncode == 0, _combined(result)
    assert "display_name\tkeychainless" in result.stdout
    assert _passphrase() not in _combined(result)

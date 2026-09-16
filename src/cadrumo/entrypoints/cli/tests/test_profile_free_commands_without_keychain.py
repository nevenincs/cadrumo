"""Real-entrypoint coverage for profile-free commands on a host with no usable keychain.

A profile session is resumed from the OS keychain. On a host without one, a
command that needs the profile refuses unless the passphrase reaches it; a
command that declares nothing a profile holds must run regardless, even with an
active profile selected. The child runs the real console script with a failing
keyring backend and no console, so no passphrase prompt can be reached.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....core.config import load_settings, override_settings
from ....core.profile_session import ProfileSessionRefusalReason
from .._profile_session_gate import _interactive_authentication
from ..config.secure_input import terminal_can_prompt_for_secrets
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NO_KEYCHAIN = {"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"}
_CLOSED_RUNTIME = "http://127.0.0.1:1/api/chat"


def _passphrase() -> str:
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _run(storage_root: Path, *args: str, stdin_payload: str | None = None) -> subprocess.CompletedProcess[str]:
    return run_cadrumo_subprocess(
        args,
        settings={
            "cadrumo_local_storage_root": storage_root,
            "cadrumo_secret_store_dir": storage_root / "fallback-store",
            "cadrumo_secret_passphrase": _passphrase(),
            "cadrumo_output_language": "en",
            "cadrumo_llm_ollama_chat_url": _CLOSED_RUNTIME,
        },
        env_strip_prefixes=("AEAT_", "PYTEST_"),
        extra_env=_NO_KEYCHAIN,
        stdin_payload=stdin_payload,
        timeout=60.0,
    )


@pytest.fixture
def active_profile_root(tmp_path: Path) -> Path:
    """Register a profile and leave it selected, as an operator's last login would."""
    with override_settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        profile_id = register_cli_profile(label="keychainless", log_in=False)
        from ....adapters.persistence.storage.sql.engine import dispose_engines_for_bucket

        dispose_engines_for_bucket(profile_id)
    return tmp_path


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def test_provision_status_runs_with_an_active_profile_and_no_keychain(active_profile_root: Path) -> None:
    result = _run(active_profile_root, "--format", "json", "config", "provision", "status")

    assert result.returncode == 0, _combined(result)
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "success"
    assert envelope["result"]["runtime"]["reachable"] is False
    assert envelope["result"]["extraction_ready"] is False
    assert envelope["result"]["document_readiness"] == "text_layer_only"
    assert envelope["result"]["probed"] is False


def test_provision_verify_runs_with_an_active_profile_and_no_keychain(active_profile_root: Path) -> None:
    result = _run(active_profile_root, "--format", "json", "config", "provision", "verify", "--role", "text_extraction")

    # The runtime is closed, so verify reports not ready -- and gets that far
    # without the profile session it never needed.
    assert result.returncode == 2, _combined(result)
    envelope = json.loads(result.stdout)
    assert envelope["result"]["ready"] is False
    assert "KEYRING" not in _combined(result)


def test_a_profile_bound_command_still_refuses_without_a_keychain_or_a_console(active_profile_root: Path) -> None:
    """Detector teeth: scoping frees only profile-free leaves, not the gate itself."""
    result = _run(active_profile_root, "--format", "json", "config", "profile", "view", "keychainless")

    assert result.returncode != 0, _combined(result)
    envelope = json.loads(result.stderr)
    assert envelope["error"]["code"] == "AUTH_STORAGE_KEYRING_UNAVAILABLE"


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


@pytest.mark.parametrize(
    "refusal",
    [reason for reason in ProfileSessionRefusalReason if reason is not ProfileSessionRefusalReason.KEYRING_UNAVAILABLE],
)
def test_a_resumable_host_never_prompts_a_parsed_invocation(refusal: ProfileSessionRefusalReason) -> None:
    context = typer.Context(typer.main.get_command(typer.Typer()))
    assert _interactive_authentication(context, bucket_id="unused", refusal=refusal) is False


def test_a_keychainless_refusal_without_a_console_does_not_prompt() -> None:
    assert terminal_can_prompt_for_secrets() is False, "the test process must not own a console"
    context = typer.Context(typer.main.get_command(typer.Typer()))
    refusal = ProfileSessionRefusalReason.KEYRING_UNAVAILABLE
    assert _interactive_authentication(context, bucket_id="unused", refusal=refusal) is False

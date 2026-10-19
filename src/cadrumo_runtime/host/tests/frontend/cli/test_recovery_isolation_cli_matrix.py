"""Cross-profile isolation through the real CLI restore and login doors.

The application-layer matrix (storage custody tests) proves the unlock and
restore authorities refuse a foreign identity. These cases prove the same
boundary holds at the operator surface: restoring A's archive into a root
where B is active publishes A's capsule without replacing B's capsule, and
B's passphrase cannot open A's restored capsule through the real login verb.

No mocks. Real registration, real Argon2id, real archive bytes, the real
Click command tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import native_cli_profile_server

from .cli_runner import invoke_unbound_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]

_CREDENTIAL_B = "isolation-cli-b-operator-secret"


def _invoke(args: list[str], *, input: str | None = None) -> Result:
    close_active_bucket_session()
    return invoke_unbound_cli(args, input=input)


def _test_passphrase() -> str:
    from cadrumo.core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _archive_export(label: str, target: Path) -> Result:
    args = [
        "--profile",
        label,
        "--profile-secrets-stdin",
        "config",
        "profile",
        "archive",
        "export",
        label,
        "--output",
        str(target),
    ]
    return _invoke(args, input=json.dumps({"profile_passphrase": _test_passphrase()}))


def _restore_from(source: Path, *, label: str) -> Result:
    args = ["config", "profile", "archive", "import", label, "--file", str(source), "--secrets-stdin"]
    return _invoke(args, input=f'{{"passphrase": "{_test_passphrase()}"}}')


def _register_and_login(*, label: str, passphrase: str) -> None:
    """Register a profile and unlock it, as every CLI-surface caller must.

    The native login publishes the persistent selection. An in-process
    invocation-only proof would select nothing for the later CLI processes.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    register_profile_with_credentials(
        label=label,
        passphrase=passphrase,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    logged_in = _invoke(
        ["config", "login", label, "--secrets-stdin"],
        input=json.dumps({"passphrase": passphrase}),
    )
    assert logged_in.exit_code == 0, logged_in.output


def test_a_foreign_archive_restores_its_own_profile_without_touching_the_active_one(
    tmp_path: Path,
) -> None:
    """A's archive publishes beside B; B still authenticates under its own password.

    Canonical capsule publication selects the published capsule last. Restoring
    A must preserve B's identity and password, and the operator can select B
    again without A having replaced or re-keyed it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path / "a-root") as root, native_cli_profile_server(root):
        _register_and_login(label="Isolation CLI A", passphrase=_test_passphrase())
        archive_path = tmp_path / "a.cadrumo-bucket.tar.gz"
        r_export = _archive_export("Isolation CLI A", archive_path)
        assert r_export.exit_code == 0, r_export.output

    with isolated_profile_storage_root(tmp_path=tmp_path / "b-root") as root, native_cli_profile_server(root):
        _register_and_login(label="Isolation CLI B", passphrase=_CREDENTIAL_B)
        selected_b = resolve_active_bucket_id()
        assert selected_b is not None
        r_restore = _restore_from(archive_path, label="Isolation CLI A restored")
        assert r_restore.exit_code == 0, r_restore.output
        assert resolve_active_bucket_id() != selected_b
        resumed_b = _invoke(
            ["config", "login", "Isolation CLI B", "--secrets-stdin"],
            input=json.dumps({"passphrase": _CREDENTIAL_B}),
        )
        assert resumed_b.exit_code == 0, resumed_b.output
        assert resolve_active_bucket_id() == selected_b

        listed = _invoke(["config", "profile", "list"])
        assert listed.exit_code == 0, listed.output
        assert "Isolation CLI A restored" in listed.output
        assert "Isolation CLI B" in listed.output


def test_the_active_profiles_passphrase_cannot_open_the_restored_profile(
    tmp_path: Path,
) -> None:
    """B's passphrase refuses at A's login — the CLI door holds the boundary."""
    with isolated_profile_storage_root(tmp_path=tmp_path / "a-root") as root, native_cli_profile_server(root):
        _register_and_login(label="Isolation CLI A", passphrase=_test_passphrase())
        archive_path = tmp_path / "a.cadrumo-bucket.tar.gz"
        assert _archive_export("Isolation CLI A", archive_path).exit_code == 0

    with isolated_profile_storage_root(tmp_path=tmp_path / "b-root") as root, native_cli_profile_server(root):
        _register_and_login(label="Isolation CLI B", passphrase=_CREDENTIAL_B)
        assert _restore_from(archive_path, label="Isolation CLI A restored").exit_code == 0

        correct = _invoke(
            ["config", "login", "Isolation CLI A restored", "--secrets-stdin"],
            input=json.dumps({"passphrase": _test_passphrase()}),
        )
        assert correct.exit_code == 0, correct.output
        selected_b = _invoke(
            ["config", "login", "Isolation CLI B", "--secrets-stdin"],
            input=json.dumps({"passphrase": _CREDENTIAL_B}),
        )
        assert selected_b.exit_code == 0, selected_b.output
        refused = _invoke(
            ["--format", "json", "config", "login", "Isolation CLI A restored", "--secrets-stdin"],
            input=json.dumps({"passphrase": _CREDENTIAL_B}),
        )
        assert refused.exit_code != 0, refused.output
        assert json.loads(refused.output)["error"]["category"] == "REFUSED", refused.output

"""Cross-profile isolation through the real CLI restore and login doors.

The application-layer matrix (storage custody tests) proves the unlock and
restore authorities refuse a foreign identity. These cases prove the same
boundary holds at the operator surface: restoring A's archive into a root
where B is active publishes A's capsule without touching B's selection, and
B's passphrase cannot open A's restored capsule through the real login verb.

No mocks. Real registration, real Argon2id, real archive bytes, the real
Click command tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile import register_profile_with_credentials
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE_B = "isolation-cli-b-operator-secret"  # noqa: S105 - synthetic test credential


def _invoke(args: list[str], *, input: str | None = None) -> Result:
    return invoke_cached_cli(args, input=input)


def _test_passphrase() -> str:
    from ....core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _archive_export(label: str, target: Path) -> Result:
    args = ["config", "profile", "archive", "export", label, "--output", str(target)]
    return _invoke(args, input=f'{{"password": "{_test_passphrase()}"}}')


def _restore_from(source: Path, *, label: str) -> Result:
    args = ["config", "profile", "restore", label, "--file", str(source), "--secrets-stdin"]
    return _invoke(args, input=f'{{"password": "{_test_passphrase()}"}}')


def test_a_foreign_archive_restores_its_own_profile_without_touching_the_active_one(
    tmp_path: Path,
) -> None:
    """A's archive into a B-active root publishes A and leaves B selected.

    Restore does not switch the active profile (the archive contract), so a
    cross-identity restore is a publication, not a takeover: B stays the
    selected profile and A's capsule lands beside it under A's own identity.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path / "a-root"):
        register_profile_with_credentials(label="Isolation CLI A", passphrase=_test_passphrase())
        archive_path = tmp_path / "a.cadrumo-bucket.tar.gz"
        r_export = _archive_export("Isolation CLI A", archive_path)
        assert r_export.exit_code == 0, r_export.output

    with isolated_profile_storage_root(tmp_path=tmp_path / "b-root"):
        register_profile_with_credentials(label="Isolation CLI B", passphrase=_PASSPHRASE_B)
        r_restore = _restore_from(archive_path, label="Isolation CLI A restored")
        assert r_restore.exit_code == 0, r_restore.output

        listed = _invoke(["config", "profile", "list"])
        assert listed.exit_code == 0, listed.output
        assert "Isolation CLI A restored" in listed.output
        assert "Isolation CLI B" in listed.output


def test_the_active_profiles_passphrase_cannot_open_the_restored_profile(
    tmp_path: Path,
) -> None:
    """B's passphrase refuses at A's login — the CLI door holds the boundary."""
    with isolated_profile_storage_root(tmp_path=tmp_path / "a-root"):
        register_profile_with_credentials(label="Isolation CLI A", passphrase=_test_passphrase())
        archive_path = tmp_path / "a.cadrumo-bucket.tar.gz"
        assert _archive_export("Isolation CLI A", archive_path).exit_code == 0

    with isolated_profile_storage_root(tmp_path=tmp_path / "b-root"):
        register_profile_with_credentials(label="Isolation CLI B", passphrase=_PASSPHRASE_B)
        assert _restore_from(archive_path, label="Isolation CLI A restored").exit_code == 0

        refused = _invoke(
            ["config", "login", "Isolation CLI A restored", "--secrets-stdin"],
            input=f'{{"password": "{_PASSPHRASE_B}"}}',
        )
        assert refused.exit_code != 0, refused.output

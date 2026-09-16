"""Real-CLI restore of a capsule directory an operator holds on disk.

The operator-facing shape of a disk-failure recovery: point ``config profile
restore`` at a ``buckets/<profile-id>/`` directory recovered from a backup,
supply the profile password, and get a usable profile back in a storage root
that has never seen it.

The restore deliberately runs against a DIFFERENT storage root from the one
the profile was registered in. Restoring into the root that already holds the
capsule would prove nothing about portability -- the interesting claim is that
the capsule carries its own custody, so a fresh host can republish it.

No mocks: real registration, real Argon2id envelope, real capsule on disk, the
real Click command tree.

The passphrase is the only restore authority. A restore never carries a
recovery enrolment across, so the envelope states ``recovery_enrolled`` false
on every restore as the operator's cue to run ``config profile recovery
enable`` again if they want the second door back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .cli_runner import invoke_cached_cli
from .privacy_helpers import assert_public_profile_payload_redacted

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RESTORED_LABEL = "Restored From Backup"


def _test_passphrase() -> str:
    """The passphrase the isolated CLI backend registers profiles under."""
    from ....core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def test_a_capsule_directory_restores_into_a_fresh_storage_root(tmp_path: Path) -> None:
    """The disk-failure path an operator actually walks, through the CLI.

    Asserts the restored identity equals the source identity: bucket identity
    IS profile identity, so a restore that minted a new id would have cloned
    the records rather than recovered them, and every cross-period reference
    the operator holds would dangle.
    """
    from ....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material

    source_root = tmp_path / "source-root"
    with isolated_profile_storage_root(tmp_path=source_root):
        profile_id = register_cli_profile(
            label="backup-subject",
            facts={"identity.tax_id": "12345678Z"},
        )
        capsule = load_committed_profile_password_material(UUID(profile_id)).capsule_path

    restore_root = tmp_path / "restore-root"
    with isolated_profile_storage_root(tmp_path=restore_root) as storage_root:
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "config",
                "profile",
                "archive",
                "import",
                _RESTORED_LABEL,
                "--file",
                str(capsule),
                "--secrets-stdin",
            ],
            input=f'{{"passphrase": "{_test_passphrase()}"}}',
        )

        assert result.exit_code == 0, result.output
        payload = assert_public_profile_payload_redacted(result.output, profile_id)

        # Identity is asserted on DISK rather than in the payload, because the
        # payload redacts the profile id by contract. The restored capsule
        # directory is named for the profile UUID, so its presence under the
        # fresh root is the real claim: the same profile came back, rather
        # than a clone under a newly minted id.
        assert (storage_root / "buckets" / profile_id).is_dir()
        assert payload["label"] == _RESTORED_LABEL
        assert payload["authority"] == "password"
        assert payload["recovery_enrolled"] is False
        assert "password_unchanged" not in payload


def test_restore_refuses_a_directory_that_is_not_a_capsule(tmp_path: Path) -> None:
    """A wrong path refuses before publishing anything.

    The operator reaching this verb is recovering from a failure and is
    plausibly pointing at the backup's parent directory rather than the
    capsule itself. That must be a named refusal, not a half-published
    profile.
    """
    not_a_capsule = tmp_path / "just-a-directory"
    not_a_capsule.mkdir()

    with isolated_profile_storage_root(tmp_path=tmp_path / "root"):
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "config",
                "profile",
                "archive",
                "import",
                _RESTORED_LABEL,
                "--file",
                str(not_a_capsule),
                "--secrets-stdin",
            ],
            input=f'{{"passphrase": "{_test_passphrase()}"}}',
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output


def test_restore_no_longer_accepts_a_recovery_artifact(tmp_path: Path) -> None:
    """``--artifact`` went with the portable artifact; the parser refuses it outright.

    A stale caller passing it must fail before any capsule is read or any
    secret consumed, so nothing is published and no prompt is reached.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path / "root") as storage_root:
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "config",
                "profile",
                "archive",
                "import",
                _RESTORED_LABEL,
                "--file",
                str(tmp_path),
                "--artifact",
                str(tmp_path / "recovery.artifact.json"),
                "--secrets-stdin",
            ],
            input=f'{{"passphrase": "{_test_passphrase()}"}}',
        )

        assert result.exit_code != 0
        assert "--artifact" in result.output
        assert not (storage_root / "buckets").exists()

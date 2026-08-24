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

Both doors are covered here. The recovery-artifact door was previously left
out, on the reasoning that minting an artifact needed a replayed recovery key
with no sanctioned test-support door -- and that obstacle was real, just not
insurmountable. The recovery key lives in a wipeable buffer that the creation
flow zeroises once the handover callback returns, so an enrollment stored and
read afterwards yields NUL bytes; the application-layer test copies only the
phrase and rebuilds a key with a private helper. Copying the phrase INSIDE the
handover, while the key is still live, mints the artifact through the
operator's own public door and needs no helper at all.

That matters because the password-door assertion below -- that a password
restore carries no advisory -- would pass identically if the advisory never
fired at all. It is a control, and it is now paired with the positive
assertion that gives it meaning.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from .privacy_helpers import assert_public_profile_payload_redacted

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RESTORED_LABEL = "Restored From Backup"
_ADVISORY_CODE = "config.profile.restore.password_unchanged"


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
    from ....adapters.persistence.storage.custody import load_committed_profile_password_material

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
                "restore",
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
        assert payload["password_unchanged"] is False

        # Control on the password door only; see the module docstring for why
        # this is not evidence about the recovery door's advisory.
        codes = {notice["code"] for notice in unwrap_envelope_notices(result.output)}
        assert _ADVISORY_CODE not in codes


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
                "restore",
                _RESTORED_LABEL,
                "--file",
                str(not_a_capsule),
                "--secrets-stdin",
            ],
            input=f'{{"passphrase": "{_test_passphrase()}"}}',
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output


def test_an_artifact_restore_warns_that_the_credential_did_not_come_back(tmp_path: Path) -> None:
    """DISCRIMINATING: the advisory the recovery door exists to raise.

    An operator reaching for the artifact has LOST the password. The records
    come back; the credential does not. Without this advisory they learn that
    at the next login prompt instead of here, where they can act on it.

    Nothing held this before: the password-door test asserts the advisory is
    ABSENT, which passes identically whether the advisory is correct or gone
    altogether. Absence was proven and presence was not.
    """
    from uuid import UUID as _UUID

    from ....adapters.persistence.storage.custody import load_committed_profile_password_material
    from ....application.user_profile import (
        ProfileRecoveryEnrollment,
        export_profile_recovery_artifact,
        register_profile_with_credentials,
    )

    source_root = tmp_path / "source-root"
    artifact = tmp_path / "exports" / "recovery.artifact.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)

    with isolated_profile_storage_root(tmp_path=source_root):
        # The phrase is copied INSIDE the handover, while the key is still
        # live. The creation flow wipes that buffer once the callback returns,
        # so an enrollment kept and read afterwards yields NUL bytes -- which
        # is the correct behaviour for a secret and the reason this cannot be
        # done by simply storing the object. Capturing the string here mints
        # the artifact through the operator's own door, with no replay helper.
        captured: list[ProfileRecoveryEnrollment] = []
        phrases: list[str] = []

        def _hand_over(enrollment: ProfileRecoveryEnrollment) -> str:
            mnemonic = str(enrollment.recovery_key.mnemonic)
            phrases.append(mnemonic)
            captured.append(enrollment)
            return mnemonic

        outcome = register_profile_with_credentials(
            label="artifact-subject",
            passphrase=_test_passphrase(),
            recovery_handover=_hand_over,
        )
        assert len(phrases[0].split()) == 24, "the phrase was read after its buffer was wiped"
        material = load_committed_profile_password_material(_UUID(outcome.profile_id))
        export_profile_recovery_artifact(
            captured[0],
            current_password=_test_passphrase(),
            password_envelope=material.envelope,
            sentinel=material.sentinel,
            target=artifact,
        )
        capsule = material.capsule_path
        recovery_secret = phrases[0]

    restore_root = tmp_path / "restore-root"
    with isolated_profile_storage_root(tmp_path=restore_root):
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "config",
                "profile",
                "restore",
                _RESTORED_LABEL,
                "--file",
                str(capsule),
                "--artifact",
                str(artifact),
                "--secrets-stdin",
            ],
            input=json.dumps({"recovery_secret": recovery_secret}),
        )

        assert result.exit_code == 0, result.output
        payload = assert_public_profile_payload_redacted(result.output, outcome.profile_id)

        assert payload["authority"] == "recovery_artifact"
        assert payload["password_unchanged"] is True

        codes = {notice["code"] for notice in unwrap_envelope_notices(result.output)}
        assert _ADVISORY_CODE in codes, (
            f"the recovery door must warn that the credential did not return; got {sorted(codes)}"
        )

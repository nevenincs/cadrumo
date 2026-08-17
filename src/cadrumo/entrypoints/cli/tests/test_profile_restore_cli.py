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

The recovery-artifact door is exercised at the application layer, in
``application/user_profile/tests/test_capsule_restore.py``. It is NOT covered
here, and that is stated rather than left to be inferred from an absent test:
minting an artifact needs a replayed recovery key that has no sanctioned
test-support door yet, and reaching into another package's private test
helpers to fake one would be worse than the honest gap. What that leaves
untested at THIS layer is the notices branch below -- the assertion here that
a password restore carries no advisory would pass identically if the advisory
never fired at all, so it is written as a control on the password door, not as
evidence about the recovery door.
"""

from __future__ import annotations

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
            input=f'{{"password": "{_test_passphrase()}"}}',
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
            input=f'{{"password": "{_test_passphrase()}"}}',
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output

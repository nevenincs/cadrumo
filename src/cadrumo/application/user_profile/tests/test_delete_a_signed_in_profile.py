"""Deleting the profile the operator is signed into must actually complete.

The configuration reset path runs prepare, confirm and delete back to back
with no session close in between, so "signed in" is the ordinary state a
deletion starts from rather than an edge case. Two independent things have
to hold for that to work: the
legal-hold arm must have a recorded fact to read, and the transaction must
not invalidate its own preflight when execution revokes the live session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import load_committed_profile_password_material
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    CommittedProfileRepository,
    ProfileCapsuleLifecycle,
    ProfileRecordRepository,
    login_profile,
    register_profile_with_credentials,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Signed In Deletion Subject"
_PASSPHRASE = "signed-in-profile-deletion-operator-secret"  # noqa: S105 - synthetic test credential


def test_a_freshly_registered_profile_passes_the_deletion_preflight(tmp_path: Path) -> None:
    """The legal arm has a recorded fact to read the moment a profile exists.

    The preflight joins a filing projection with a legal one, and the legal
    projection raises on absence rather than defaulting to cleared. A profile
    born without that fact recorded is undeletable by any route, so this is
    the narrowest proof that registration supplies it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )

        journal = ProfileCapsuleLifecycle().prepare_delete(profile_id=UUID(outcome.profile_id))

        assert journal.hold_assessment is not None
        assert journal.hold_assessment.permits_local_deletion


def test_the_profile_the_operator_is_signed_into_can_be_deleted(tmp_path: Path) -> None:
    """Execution revokes the live session; the preflight must survive that.

    Registration closes its own session, so the profile is logged into first:
    a signed-in operator holds the capsule database open, which parks the
    write-ahead and shared-memory sidecars beside it. Execution's first act
    revokes that session and checkpoints them away, so a preflight that
    counted them could never match its own re-inventory. The sequence below
    is the one the configuration reset path runs -- prepare, confirm, delete,
    with no session close in between.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)
        lifecycle = ProfileCapsuleLifecycle()

        # Read the record through the live session so the capsule database is
        # genuinely open at preflight. Without this the sidecars may be absent
        # and the test would pass for the wrong reason: the transaction would
        # never have had a checkpoint to survive.
        ProfileRecordRepository.for_current_session(outcome.profile_id).load(outcome.profile_id)
        capsule = load_committed_profile_password_material(UUID(outcome.profile_id)).capsule_path
        assert (capsule / "db" / "cadrumo.db-wal").exists()

        journal = lifecycle.prepare_delete(profile_id=UUID(outcome.profile_id))
        receipt = lifecycle.delete(lifecycle.confirm_delete(journal))

        assert receipt.profile_id == UUID(outcome.profile_id)
        assert not any(view.profile_id == outcome.profile_id for view in CommittedProfileRepository().list())

"""Changing a profile's password, end to end, through the real custody stack.

Real capsules on a real filesystem, real Argon2id envelopes, a real SQLite
substrate and the real recovery door. Nothing here is stubbed, and every
assertion is about state that survived a round trip rather than about a call
having been made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.application.user_profile import (
    profile_custody_recovery_envelope_path,
    profile_is_password_authentication_failure,
    unlock_profile_custody_password,
)

from ....adapters.persistence.storage.custody import (
    load_committed_profile_password_material,
    parse_profile_custody_recovery_envelope,
    unlock_profile_custody_recovery,
)
from ....domain.buckets import BucketEventType
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfilePassphraseRotationError,
    ProfileRecordRepository,
    login_profile,
    logout_active_profile,
    register_profile_with_credentials,
    rotate_profile_passphrase,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Passphrase Rotation Subject"
_CURRENT = "passphrase-rotation-current-operator-secret"
_REPLACEMENT = "passphrase-rotation-replacement-operator-secret"
_WRONG = "passphrase-rotation-not-the-current-operator-secret"
_TOO_SHORT = "short"


def _register(handed: list[str] | None = None):
    """Create the subject profile, optionally enrolling recovery."""
    return register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT,
        recovery_handover=None if handed is None else (lambda e: handed.append(e.recovery_key.mnemonic)),
    )


def test_the_new_passphrase_opens_the_profile_and_the_old_one_no_longer_does(tmp_path: Path) -> None:
    """The whole point of the verb, proved on both sides of the change."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)

        rotated = rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
        )

        assert rotated.password_generation == 2
        assert rotated.dek_epoch_preserved is True

        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=_REPLACEMENT).dek is not None
        with pytest.raises(Exception) as refused:
            unlock_profile_custody_password(material, password=_CURRENT)
        assert profile_is_password_authentication_failure(refused.value)


def test_the_profile_record_is_still_readable_after_the_change(tmp_path: Path) -> None:
    """A rotation that strands the record would be worse than no rotation.

    The row's witness folds the envelope identity, so a change that swapped
    the wrapper without re-heading the row would leave a profile that
    authenticates under the new password and then cannot read itself. This
    reads the record back through a real login on the new credential.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        # Registration closes its own session, so the profile is locked here;
        # reading the "before" record needs a real login exactly as an
        # operator's next command would.
        login_profile(name=_LABEL, passphrase_callback=lambda: _CURRENT)
        before = ProfileRecordRepository.for_current_session(outcome.profile_id).load(outcome.profile_id)
        logout_active_profile()

        rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
        )

        login_profile(name=_LABEL, passphrase_callback=lambda: _REPLACEMENT)
        after = ProfileRecordRepository.for_current_session(outcome.profile_id).load(outcome.profile_id)

        assert after.facts == before.facts
        assert after.setup_state == before.setup_state
        assert after.record_revision == before.record_revision + 1


def test_the_rotation_is_recorded_in_the_profile_history(tmp_path: Path) -> None:
    """A custody change the operator cannot see afterwards is not auditable."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        logout_active_profile()

        rotate_profile_passphrase(
            profile_id=UUID(outcome.profile_id),
            current_passphrase=_CURRENT,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
        )

        login_profile(name=_LABEL, passphrase_callback=lambda: _REPLACEMENT)
        from .._capsule_record import ProfileRecordStore
        from .._profile_record_repository import require_profile_record_session

        history = ProfileRecordStore(session=require_profile_record_session(outcome.profile_id)).history()

        assert any(event.event_type is BucketEventType.PROFILE_PASSPHRASE_ROTATED for event in history)


def test_an_outstanding_recovery_phrase_still_opens_the_profile_afterwards(tmp_path: Path) -> None:
    """Rotation must not strand the second door a taxpayer is keeping.

    A recovery phrase written down before the password change has to keep
    working, or changing a password silently destroys the only route back
    into the records for someone who later forgets the new one.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register(handed)
        profile_id = UUID(outcome.profile_id)

        rotated = rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
        )

        assert rotated.recovery_enrollment_retained is True

        material = load_committed_profile_password_material(profile_id)
        recovery = parse_profile_custody_recovery_envelope(
            profile_custody_recovery_envelope_path(material.capsule_path).read_bytes(),
        )
        proved = unlock_profile_custody_recovery(recovery, handed[0], sentinel=material.sentinel)

        assert proved.dek == unlock_profile_custody_password(material, password=_REPLACEMENT).dek


def test_a_wrong_current_passphrase_refuses_and_changes_nothing(tmp_path: Path) -> None:
    """Fail closed: the existing wrapper must survive a refused attempt intact."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        before = load_committed_profile_password_material(profile_id).envelope.canonical_json_bytes()

        with pytest.raises(ProfilePassphraseRotationError):
            rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=_WRONG,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
            )

        material = load_committed_profile_password_material(profile_id)
        assert material.envelope.canonical_json_bytes() == before
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None


def test_a_mismatched_confirmation_refuses_before_anything_is_read(tmp_path: Path) -> None:
    """The confirmation is checked here too, not only at the surface above."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        before = load_committed_profile_password_material(profile_id).envelope.canonical_json_bytes()

        with pytest.raises(ProfilePassphraseRotationError):
            rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=_CURRENT,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=f"{_REPLACEMENT}-typo",
            )

        assert load_committed_profile_password_material(profile_id).envelope.canonical_json_bytes() == before


def test_a_new_passphrase_below_the_verifier_minimum_refuses(tmp_path: Path) -> None:
    """A rotation must not be a way to install a credential creation would reject."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)

        with pytest.raises(ProfilePassphraseRotationError):
            rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=_CURRENT,
                new_passphrase=_TOO_SHORT,
                new_passphrase_confirmation=_TOO_SHORT,
            )

        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None

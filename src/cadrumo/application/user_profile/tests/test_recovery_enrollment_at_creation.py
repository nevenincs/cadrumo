"""Recovery enrollment happens at the creation door, or not at all.

A committed capsule has no in-place installation path for a second wrapper,
so the only moment a recovery envelope can be published with a profile is
while that profile is being created. These tests drive the real registration
door, the real custody mint, and the real recovery-only unlock: no fake
envelope, no synthetic mnemonic, and no assertion that would still hold if
the wrapper were never written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage import generate_recovery_key
from ....adapters.persistence.storage.custody import (
    PROFILE_CUSTODY_RECOVERY_FILENAME,
    ProfileCustodyPasswordError,
    load_committed_profile_password_material,
    parse_profile_custody_recovery_envelope,
    unlock_profile_custody_recovery,
)
from ....tests.secure_sql import isolated_profile_storage_root
from .. import CommittedProfileRepository, register_profile_with_credentials

if TYPE_CHECKING:
    from pathlib import Path

    from .._recovery_custody import ProfileRecoveryEnrollment

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Recovery Enrollment Subject"
_PASSPHRASE = "recovery-enrollment-at-creation-operator-secret"  # noqa: S105 - synthetic test credential

_BIP39_WORD_COUNT = 24


def _recovery_envelope_path(profile_id: str) -> Path:
    """Return the published capsule's optional recovery wrapper path."""
    material = load_committed_profile_password_material(UUID(profile_id))
    return material.capsule_path / "custody" / PROFILE_CUSTODY_RECOVERY_FILENAME


def test_a_registration_that_takes_the_handover_publishes_a_wrapper_its_words_open(tmp_path: Path) -> None:
    """The minted mnemonic really unwraps the DEK from the published capsule.

    This is the whole claim of the feature, so it is proved through the
    recovery-only door rather than by checking that a file exists: the unlock
    derives from the secret the operator was handed and verifies the result
    against the capsule's own committed sentinel.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label=_LABEL,
            passphrase=_PASSPHRASE,
            recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.mnemonic),
        )

        assert len(handed) == 1
        assert len(handed[0].split()) == _BIP39_WORD_COUNT

        material = load_committed_profile_password_material(UUID(outcome.profile_id))
        envelope_path = material.capsule_path / "custody" / PROFILE_CUSTODY_RECOVERY_FILENAME
        envelope = parse_profile_custody_recovery_envelope(envelope_path.read_bytes())

        unlock = unlock_profile_custody_recovery(envelope, handed[0], sentinel=material.sentinel)

    assert unlock.profile_id == UUID(outcome.profile_id)
    assert unlock.dek_epoch == material.envelope.dek_epoch
    assert len(unlock.dek) == 32


def test_a_different_minted_mnemonic_does_not_open_the_published_wrapper(tmp_path: Path) -> None:
    """Anti-tautology: the unlock is bound to the secret the operator was handed.

    The sibling test would read the same if the recovery door accepted any
    well-formed BIP-39 phrase, so a second real mint -- same shape, same
    entropy, different words -- must be refused against the same envelope.
    """
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label=_LABEL,
            passphrase=_PASSPHRASE,
            recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.mnemonic),
        )

        material = load_committed_profile_password_material(UUID(outcome.profile_id))
        envelope = parse_profile_custody_recovery_envelope(_recovery_envelope_path(outcome.profile_id).read_bytes())

        with generate_recovery_key() as impostor:
            assert impostor.mnemonic != handed[0]
            with pytest.raises(ProfileCustodyPasswordError):
                unlock_profile_custody_recovery(envelope, impostor.mnemonic, sentinel=material.sentinel)


def test_a_registration_that_takes_no_handover_publishes_no_wrapper(tmp_path: Path) -> None:
    """Converse control: enrollment is opt-in, and the default mints nothing.

    Without this the sibling test would pass identically if the door enrolled
    unconditionally, and an unconditional mint would publish a second door
    whose words nobody was ever shown.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)

        assert not _recovery_envelope_path(outcome.profile_id).exists()
        assert outcome.recovery_enrolled is False


def test_the_outcome_reports_whether_recovery_was_actually_enrolled(tmp_path: Path) -> None:
    """The absence must be legible to a surface, not inferable only from disk.

    Enrollment is available exactly once, while the capsule is published, so
    an operator who is not told it did not happen has silently lost the
    option. The flag is what lets a surface say so, and it must track the
    published wrapper rather than merely echo the caller's request.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label=f"{_LABEL} enrolled",
            passphrase=_PASSPHRASE,
            recovery_handover=lambda enrollment: None,
        )

        assert enrolled.recovery_enrolled is True
        assert _recovery_envelope_path(enrolled.profile_id).exists()


def test_the_handed_over_key_is_wiped_by_the_time_registration_returns(tmp_path: Path) -> None:
    """The caller gets the words for the duration of its callback and no longer.

    Retaining the enrollment past the handover has to be useless, or the
    wipe-as-early-as-the-flow-allows contract is only a docstring.
    """
    retained: list[ProfileRecoveryEnrollment] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            label=_LABEL,
            passphrase=_PASSPHRASE,
            recovery_handover=retained.append,
        )

    assert len(retained) == 1
    assert set(retained[0].recovery_key.raw) == {0}
    assert set(retained[0].recovery_key.mnemonic.encode("utf-8")) == {0}


def test_a_channel_that_cannot_deliver_the_words_creates_no_profile(tmp_path: Path) -> None:
    """A refused handover aborts creation instead of orphaning a wrapper.

    A delivery channel can fail at the moment of writing rather than when it
    is chosen: a detached process is handed a freshly allocated console, so
    the device opens and the write lands where nobody will see it. If the
    capsule were published first, that would leave a live profile carrying a
    recovery wrapper whose only key went nowhere — enrolled, reported
    enrolled, and permanently unopenable, because a committed capsule cannot
    be enrolled afterwards.

    Delivering before publication makes the failure fall the other way: no
    profile, no wrapper, and a refusal the caller can act on.
    """
    retained: list[ProfileRecoveryEnrollment] = []

    def _refuse(enrollment: ProfileRecoveryEnrollment) -> None:
        retained.append(enrollment)
        raise RuntimeError("no interactive terminal to display the recovery words on")

    with isolated_profile_storage_root(tmp_path=tmp_path):
        with pytest.raises(RuntimeError, match="no interactive terminal"):
            register_profile_with_credentials(
                label=_LABEL,
                passphrase=_PASSPHRASE,
                recovery_handover=_refuse,
            )

        assert len(retained) == 1
        assert set(retained[0].recovery_key.raw) == {0}
        # No capsule was published, so the profile the refused enrollment was
        # minted for does not exist and cannot be listed.
        assert not any(view.label == _LABEL for view in CommittedProfileRepository().list())

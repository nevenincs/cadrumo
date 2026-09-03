"""Changing a profile's password, end to end, through the real custody stack.

Real capsules on a real filesystem, real Argon2id envelopes, a real SQLite
substrate and the real recovery door. Nothing here is stubbed, and every
assertion is about state that survived a round trip rather than about a call
having been made.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from ....adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
from ....adapters.persistence.storage.custody.recovery import (
    parse_profile_custody_recovery_envelope,
    unlock_profile_custody_recovery,
)
from ....core.credentials import (
    PROFILE_PASSWORD_MAX_SCALARS,
    PROFILE_PASSWORD_MIN_SCALARS,
    ProfilePasswordRefusalReason,
)
from ....domain.buckets.event import BucketEventType
from ....tests.secure_sql import isolated_profile_storage_root
from ..custody_ports import (
    profile_custody_recovery_envelope_path,
    unlock_profile_custody_password,
)
from ..login_session import login_profile, logout_active_profile
from ..passphrase_rotation import (
    ProfilePassphraseRotationError,
    rotate_profile_passphrase,
)
from ..profile_record_repository import ProfileRecordRepository
from ..registration import register_profile_with_credentials

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Passphrase Rotation Subject"
_CURRENT = "passphrase-rotation-current-operator-secret"
_REPLACEMENT = "passphrase-rotation-replacement-operator-secret"
_WRONG = "passphrase-rotation-not-the-current-operator-secret"
_TOO_SHORT = "short"

_REFUSAL_MESSAGES = {
    ProfilePasswordRefusalReason.CONTAINS_SURROGATE: (
        "application.user_profile.errors.profile_password_contains_surrogate"
    ),
    ProfilePasswordRefusalReason.TOO_FEW_SCALARS: ("application.user_profile.errors.profile_password_too_few_scalars"),
    ProfilePasswordRefusalReason.TOO_MANY_SCALARS: (
        "application.user_profile.errors.profile_password_too_many_scalars"
    ),
    ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES: (
        "application.user_profile.errors.profile_password_too_many_utf8_bytes"
    ),
}


def _register(handed: list[str] | None = None):
    """Create the subject profile, optionally retaining its recovery words."""
    return register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT,
        recovery_handover=lambda enrollment: (
            (handed.append(enrollment.recovery_key.mnemonic) if handed is not None else None)
            or enrollment.recovery_key.mnemonic
        ),
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
        with pytest.raises(ProfileCustodyPasswordError) as refused:
            unlock_profile_custody_password(material, password=_CURRENT)
        assert isinstance(refused.value, ProfileCustodyPasswordError)


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
        from ..capsule_record import ProfileRecordStore
        from ..profile_record_repository import require_profile_record_session

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


@pytest.mark.parametrize("current_candidate", (_WRONG, "short"))
def test_a_rejected_current_passphrase_is_non_oracular_and_changes_nothing(
    tmp_path: Path,
    current_candidate: str,
) -> None:
    """Fail closed: the existing wrapper must survive a refused attempt intact."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        before = _storage_snapshot(storage_root)

        with pytest.raises(ProfilePassphraseRotationError) as refused:
            rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=current_candidate,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
            )

        material = load_committed_profile_password_material(profile_id)
        assert _storage_snapshot(storage_root) == before
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None
        assert refused.value.translated_message == "application.user_profile.errors.passphrase_current_rejected"
        assert refused.value.context is None
        assert current_candidate not in repr(refused.value)


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


@pytest.mark.parametrize(
    ("candidate", "reason"),
    (
        ("a" * 7, ProfilePasswordRefusalReason.TOO_FEW_SCALARS),
        ("a" * (PROFILE_PASSWORD_MAX_SCALARS + 1), ProfilePasswordRefusalReason.TOO_MANY_SCALARS),
        ("\U0001f600" * 256 + "a", ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES),
        ("\ud800" + "a" * 14, ProfilePasswordRefusalReason.CONTAINS_SURROGATE),
        ("\udfff" + "a" * 14, ProfilePasswordRefusalReason.CONTAINS_SURROGATE),
    ),
)
def test_every_replacement_password_refusal_is_typed_safe_and_changes_nothing(
    tmp_path: Path,
    candidate: str,
    reason: ProfilePasswordRefusalReason,
) -> None:
    """Prospective refusal precedes locks, unwrap, re-heading and publication."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        before = _storage_snapshot(storage_root)

        with pytest.raises(ProfilePassphraseRotationError) as refused:
            rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=_CURRENT,
                new_passphrase=candidate,
                new_passphrase_confirmation=candidate,
            )

        assert _storage_snapshot(storage_root) == before
        payload = refused.value.password_refusal
        assert payload is not None
        assert payload.reason is reason
        assert candidate not in repr(payload)
        assert type(payload.context) is MappingProxyType
        assert refused.value.context == dict(payload.context)
        assert payload.translated_message == _REFUSAL_MESSAGES[reason]
        assert refused.value.translated_message == _REFUSAL_MESSAGES[reason]
        expected_context: dict[str, object] = {"reason": reason.value, "scalar_count": len(candidate)}
        if reason is not ProfilePasswordRefusalReason.CONTAINS_SURROGATE:
            expected_context["utf8_byte_count"] = len(candidate.encode("utf-8"))
        if reason is ProfilePasswordRefusalReason.TOO_FEW_SCALARS:
            expected_context["minimum_scalars"] = 8
        elif reason is ProfilePasswordRefusalReason.TOO_MANY_SCALARS:
            expected_context["maximum_scalars"] = 256
        elif reason is ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES:
            expected_context["maximum_utf8_bytes"] = 1024
        assert dict(payload.context) == expected_context
        with pytest.raises(TypeError):
            payload.context["candidate"] = candidate  # type: ignore[index]  # ty: ignore[invalid-assignment]  # reason: writing to the immutable context IS the refusal under test


@pytest.mark.parametrize(
    "replacement",
    (
        "a" * PROFILE_PASSWORD_MIN_SCALARS,
        "a" * PROFILE_PASSWORD_MAX_SCALARS,
        "\U0001f600" * 256,
    ),
)
def test_rotation_accepts_scalar_and_byte_boundaries_exactly(tmp_path: Path, replacement: str) -> None:
    """Rotation accepts the two scalar boundaries and 1,024 strict UTF-8 bytes."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)

        rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=replacement,
            new_passphrase_confirmation=replacement,
        )

        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=replacement).dek is not None


@pytest.mark.parametrize(
    ("replacement", "equivalent"),
    (
        ("\u00e9" * PROFILE_PASSWORD_MIN_SCALARS, "e\u0301" * PROFILE_PASSWORD_MIN_SCALARS),
        ("e\u0301" * PROFILE_PASSWORD_MIN_SCALARS, "\u00e9" * PROFILE_PASSWORD_MIN_SCALARS),
    ),
)
def test_rotation_preserves_composed_and_decomposed_passwords_exactly(
    tmp_path: Path,
    replacement: str,
    equivalent: str,
) -> None:
    """Rotation never normalises a replacement credential."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = _register()
        profile_id = UUID(outcome.profile_id)
        rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=replacement,
            new_passphrase_confirmation=replacement,
        )

        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=replacement).dek is not None
        with pytest.raises(ProfileCustodyPasswordError) as refused:
            unlock_profile_custody_password(material, password=equivalent)
        assert isinstance(refused.value, ProfileCustodyPasswordError)


def _storage_snapshot(root: Path) -> dict[str, bytes | None]:
    """Capture capsule, inventory, session, record and envelope state exactly."""
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }

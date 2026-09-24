"""Optional recovery, end to end, through the real custody stack.

Real capsules on a real filesystem, real Argon2id wrappers for both doors, a
real SQLite substrate and the real enrol, revoke, status and reset doors.
Nothing is stubbed. Every assertion is about state that survived a round trip
through the committed capsule, never about a call having been made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
from cadrumo.adapters.persistence.storage.master_key.login_throttle import login_throttle_path
from cadrumo.adapters.persistence.storage.recovery_key import canonical_recovery_code
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.custody_ports import (
    profile_custody_recovery_envelope_path,
    unlock_profile_custody_password,
)
from cadrumo.application.user_profile.login_session import login_profile, logout_active_profile
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.recovery_custody import (
    ProfileRecoveryEnrollment,
    ProfileRecoveryError,
    enroll_profile_recovery,
    profile_recovery_status,
    reset_profile_passphrase_with_recovery,
    revoke_profile_recovery,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.credentials import ProfilePasswordRefusalReason

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_LABEL = "Recovery Enrollment Subject"
_CURRENT = "recovery-enrollment-current-operator-secret"
_REPLACEMENT = "recovery-enrollment-replacement-operator-secret"
_WRONG = "recovery-enrollment-not-the-current-operator-secret"
_TOO_SHORT = "short"


class _HandoverDeclinedError(Exception):
    """The operator walked away before copying the code down."""


def _register() -> UUID:
    """Create the subject profile; it is born without recovery."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    return UUID(outcome.profile_id)


def _enroll(profile_id: UUID, passphrase: str = _CURRENT) -> str:
    """Enrol through the real door and return the code it handed over."""
    handed: list[str] = []
    outcome = enroll_profile_recovery(
        profile_id=profile_id,
        current_passphrase=passphrase,
        recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
    )
    assert outcome.enrolled is True
    assert outcome.changed is True
    return handed[0]


def _wrapper_path(profile_id: UUID) -> Path:
    return profile_custody_recovery_envelope_path(load_committed_profile_password_material(profile_id).capsule_path)


def _storage_snapshot(root: Path) -> dict[str, bytes | None]:
    """Capture capsule, inventory, session, record and envelope state exactly."""
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }


# ── enrolment ────────────────────────────────────────────────────────────────


def test_a_profile_is_born_without_recovery_and_enrols_only_after_the_handover_proof_matches(
    tmp_path: Path,
) -> None:
    """The wrapper lands only once the operator has proved possession of the minted code."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        wrapper = _wrapper_path(profile_id)
        assert not wrapper.exists()
        assert profile_recovery_status(profile_id=profile_id).enrolled is False

        seen: list[ProfileRecoveryEnrollment] = []

        def handover(enrollment: ProfileRecoveryEnrollment) -> str:
            seen.append(enrollment)
            assert not wrapper.exists(), "the wrapper must not be installed before possession is proved"
            code = enrollment.recovery_key.code
            assert canonical_recovery_code(code) == code
            assert enrollment.envelope.profile_id == profile_id
            return code

        outcome = enroll_profile_recovery(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            recovery_handover=handover,
        )

        assert outcome.profile_id == str(profile_id)
        assert outcome.enrolled is True
        assert outcome.changed is True
        assert wrapper.is_file()
        assert wrapper.read_bytes() == seen[0].envelope.canonical_json_bytes()
        assert profile_recovery_status(profile_id=profile_id).enrolled is True
        # The key was wiped the moment the handover returned.
        assert set(seen[0].recovery_key.code) == {"\x00"}


def test_a_mismatching_handover_proof_installs_nothing(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        before = _storage_snapshot(storage_root)

        with pytest.raises(ProfileRecoveryError) as refused:
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=_CURRENT,
                recovery_handover=lambda enrollment: enrollment.recovery_key.code[:-1] + "Z",
            )

        assert refused.value.translated_message == "application.user_profile.errors.recovery_possession_mismatch"
        assert _storage_snapshot(storage_root) == before
        assert profile_recovery_status(profile_id=profile_id).enrolled is False


def test_a_handover_that_raises_aborts_the_enrolment_and_wipes_the_key(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        before = _storage_snapshot(storage_root)
        seen: list[ProfileRecoveryEnrollment] = []

        def decline(enrollment: ProfileRecoveryEnrollment) -> str:
            seen.append(enrollment)
            raise _HandoverDeclinedError

        with pytest.raises(_HandoverDeclinedError):
            enroll_profile_recovery(profile_id=profile_id, current_passphrase=_CURRENT, recovery_handover=decline)

        assert _storage_snapshot(storage_root) == before
        assert profile_recovery_status(profile_id=profile_id).enrolled is False
        assert set(seen[0].recovery_key.code) == {"\x00"}


@pytest.mark.parametrize("current_candidate", (_WRONG, _TOO_SHORT))
def test_a_rejected_current_passphrase_refuses_enrolment_without_minting_a_code(
    tmp_path: Path,
    current_candidate: str,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        before = _storage_snapshot(storage_root)
        handovers: list[ProfileRecoveryEnrollment] = []

        with pytest.raises(ProfileRecoveryError) as refused:
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=current_candidate,
                recovery_handover=lambda enrollment: handovers.append(enrollment) or enrollment.recovery_key.code,
            )

        assert refused.value.translated_message == "application.user_profile.errors.passphrase_current_rejected"
        assert current_candidate not in repr(refused.value)
        assert handovers == []
        assert _storage_snapshot(storage_root) == before


def test_enrolling_twice_refuses_and_keeps_the_first_wrapper(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        _enroll(profile_id)
        wrapper = _wrapper_path(profile_id)
        first = wrapper.read_bytes()
        handovers: list[ProfileRecoveryEnrollment] = []

        with pytest.raises(ProfileRecoveryError) as refused:
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=_CURRENT,
                recovery_handover=lambda enrollment: handovers.append(enrollment) or enrollment.recovery_key.code,
            )

        assert refused.value.translated_message == "application.user_profile.errors.recovery_already_enrolled"
        assert handovers == []
        assert wrapper.read_bytes() == first


# ── revocation and status ────────────────────────────────────────────────────


def test_revocation_removes_the_wrapper_and_is_idempotent(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        wrapper = _wrapper_path(profile_id)

        revoked = revoke_profile_recovery(profile_id=profile_id, current_passphrase=_CURRENT)

        assert revoked.enrolled is False
        assert revoked.changed is True
        assert not wrapper.exists()
        assert profile_recovery_status(profile_id=profile_id).enrolled is False

        again = revoke_profile_recovery(profile_id=profile_id, current_passphrase=_CURRENT)
        assert again.enrolled is False
        assert again.changed is False

        # A revoked code is dead: the reset door no longer has a wrapper to prove it against.
        _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
        with pytest.raises(ProfileRecoveryError) as refused:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=code,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
                profile_decode_context=_profile_decode_context_for_test,
            )
        assert refused.value.translated_message == "application.user_profile.errors.recovery_not_enrolled"

        # A fresh enrolment after revocation mints a different code.
        assert _enroll(profile_id) != code
        assert wrapper.is_file()


def test_revocation_proves_the_current_passphrase_before_disclosing_enrolment_state(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        _enroll(profile_id)
        wrapper = _wrapper_path(profile_id)
        first = wrapper.read_bytes()

        for candidate in (_WRONG, _TOO_SHORT):
            with pytest.raises(ProfileRecoveryError) as refused:
                revoke_profile_recovery(profile_id=profile_id, current_passphrase=candidate)
            assert refused.value.translated_message == "application.user_profile.errors.passphrase_current_rejected"
            assert wrapper.read_bytes() == first

        revoke_profile_recovery(profile_id=profile_id, current_passphrase=_CURRENT)
        with pytest.raises(ProfileRecoveryError) as refused:
            revoke_profile_recovery(profile_id=profile_id, current_passphrase=_WRONG)
        assert refused.value.translated_message == "application.user_profile.errors.passphrase_current_rejected"


def test_status_reflects_the_committed_wrapper_without_any_secret(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        assert profile_recovery_status(profile_id=profile_id) == profile_recovery_status(profile_id=profile_id)
        assert profile_recovery_status(profile_id=profile_id).enrolled is False
        _enroll(profile_id)
        status = profile_recovery_status(profile_id=profile_id)
        assert status.profile_id == str(profile_id)
        assert status.enrolled is True
        _wrapper_path(profile_id).unlink()
        assert profile_recovery_status(profile_id=profile_id).enrolled is False


# ── passphrase reset ─────────────────────────────────────────────────────────


def test_the_recovery_code_replaces_a_forgotten_passphrase_and_keeps_the_dek_epoch(tmp_path: Path) -> None:
    """The whole point of enrolment: the new passphrase opens the records, the old one no longer does."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        material_before = load_committed_profile_password_material(profile_id)
        wrapper = _wrapper_path(profile_id)
        wrapper_before = wrapper.read_bytes()

        reset = reset_profile_passphrase_with_recovery(
            profile_id=profile_id,
            recovery_code=code,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
            profile_decode_context=_profile_decode_context_for_test,
        )

        assert reset.profile_id == str(profile_id)
        assert reset.password_generation == material_before.envelope.password_generation + 1
        assert reset.dek_epoch_preserved is True
        assert reset.recovery_enrollment_retained is True
        assert wrapper.read_bytes() == wrapper_before

        material = load_committed_profile_password_material(profile_id)
        assert material.envelope.dek_epoch == material_before.envelope.dek_epoch
        assert material.envelope.password_generation == reset.password_generation
        assert material.sentinel == material_before.sentinel
        assert unlock_profile_custody_password(material, password=_REPLACEMENT).dek is not None
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody_password(material, password=_CURRENT)

        # The record is readable through a real login on the new credential,
        # so the reset re-headed the row rather than merely swapping the wrapper.
        login_profile(
            name=_LABEL,
            passphrase_callback=lambda: _REPLACEMENT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        try:
            record = ProfileRecordRepository.for_current_session(
                str(profile_id), profile_decode_context=_profile_decode_context_for_test
            ).load(str(profile_id))
            assert record.profile_id == str(profile_id)
        finally:
            logout_active_profile()


def test_the_same_code_resets_again_after_a_reset(tmp_path: Path) -> None:
    """Reset retains enrolment, so the code stays good for the next forgotten passphrase too."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    third = "recovery-enrollment-third-operator-secret"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        for replacement in (_REPLACEMENT, third):
            reset = reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=code,
                new_passphrase=replacement,
                new_passphrase_confirmation=replacement,
                profile_decode_context=_profile_decode_context_for_test,
            )
            assert reset.recovery_enrollment_retained is True
        material = load_committed_profile_password_material(profile_id)
        assert material.envelope.password_generation == 3
        assert unlock_profile_custody_password(material, password=third).dek is not None


def test_a_wrong_code_refuses_non_oracularly_and_leaves_the_envelope_untouched(tmp_path: Path) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        before = _storage_snapshot(storage_root)
        wrong = code[:-1] + ("Z" if code[-1] != "Z" else "Y")

        with pytest.raises(ProfileRecoveryError) as refused:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=wrong,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
                profile_decode_context=_profile_decode_context_for_test,
            )

        assert refused.value.translated_message == "application.user_profile.errors.recovery_code_rejected"
        assert refused.value.context is None
        assert wrong not in repr(refused.value)
        # The one write a refused code makes is the failed-attempt count, in
        # the profile's keystore beside the capsule rather than inside it.
        keystore = login_throttle_path(storage_root=storage_root, bucket_id=str(profile_id)).parent
        after = _storage_snapshot(storage_root)
        changed = {key for key in before.keys() | after.keys() if before.get(key, b"") != after.get(key, b"")}
        assert changed
        assert all((storage_root / key).is_relative_to(keystore) for key in changed)
        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None


def test_reset_refuses_a_profile_that_never_enrolled(tmp_path: Path) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        logout_active_profile()
        before = _storage_snapshot(storage_root)

        with pytest.raises(ProfileRecoveryError) as refused:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code="-".join(("ABCDE", "FGHJK", "LMNPQ", "RSTUV", "WXYZ2", "34567")),
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
                profile_decode_context=_profile_decode_context_for_test,
            )

        assert refused.value.translated_message == "application.user_profile.errors.recovery_not_enrolled"
        assert _storage_snapshot(storage_root) == before


def test_reset_checks_the_new_passphrase_and_its_confirmation_before_any_proof(tmp_path: Path) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        before = _storage_snapshot(storage_root)

        with pytest.raises(ProfileRecoveryError) as mismatched:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=code,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=f"{_REPLACEMENT}-typo",
                profile_decode_context=_profile_decode_context_for_test,
            )
        assert mismatched.value.translated_message == "application.user_profile.errors.passphrase_confirmation_mismatch"

        with pytest.raises(ProfileRecoveryError) as too_short:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=code,
                new_passphrase=_TOO_SHORT,
                new_passphrase_confirmation=_TOO_SHORT,
                profile_decode_context=_profile_decode_context_for_test,
            )
        payload = too_short.value.password_refusal
        assert payload is not None
        assert payload.reason is ProfilePasswordRefusalReason.TOO_FEW_SCALARS
        assert too_short.value.translated_message == payload.translated_message
        assert _TOO_SHORT not in repr(payload)

        assert _storage_snapshot(storage_root) == before
        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None


# ── rotation interplay ───────────────────────────────────────────────────────


def test_an_ordinary_rotation_after_enrolment_keeps_the_code_working(tmp_path: Path) -> None:
    """Rotation preserves the DEK epoch, so the wrapper enrolled before it still proves the same key."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    third = "recovery-enrollment-post-rotation-operator-secret"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        wrapper = _wrapper_path(profile_id)
        wrapper_before = wrapper.read_bytes()

        rotated = rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_CURRENT,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        assert rotated.recovery_enrollment_retained is True
        assert wrapper.read_bytes() == wrapper_before

        reset = reset_profile_passphrase_with_recovery(
            profile_id=profile_id,
            recovery_code=code,
            new_passphrase=third,
            new_passphrase_confirmation=third,
            profile_decode_context=_profile_decode_context_for_test,
        )

        assert reset.password_generation == 3
        assert reset.dek_epoch_preserved is True
        material = load_committed_profile_password_material(profile_id)
        assert unlock_profile_custody_password(material, password=third).dek is not None
        for retired in (_CURRENT, _REPLACEMENT):
            with pytest.raises(ProfileCustodyPasswordError):
                unlock_profile_custody_password(material, password=retired)

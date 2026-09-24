"""What every passphrase replacement leaves behind, whichever door authorised it.

A rotation proves the current passphrase; a reset proves the enrolled recovery
code. Both then run one shared re-wrap, so the facts pinned here hold for both:
the committed envelope names the one it replaced and carries the next
generation, and the profile's history says which proof was used. The reset
door is a credential proof like login, so it also answers to the same
failed-attempt backoff.

Real capsules on a real filesystem, real Argon2id through the supervised
worker, a real SQLite substrate and the real doors. Nothing is stubbed; the one
substitution below is a tripwire that fails the test if the key derivation is
reached at all.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    delete_profile_session,
    mint_profile_session,
    resume_profile_session,
)
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
from cadrumo.adapters.persistence.storage.master_key.login_throttle import (
    evaluate_login_throttle,
    record_login_failure,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile import recovery_custody
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.capsule_archive import (
    export_profile_capsule_archive,
    read_profile_capsule_archive,
)
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.capsule_restore import restore_profile_capsule_with_password
from cadrumo.application.user_profile.custody_ports import unlock_profile_custody_password
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.login_session import (
    ProfileLoginThrottledError,
    login_profile,
    logout_active_profile,
)
from cadrumo.application.user_profile.passphrase_rotation import (
    ProfilePassphraseReplacementProof,
    rotate_profile_passphrase,
)
from cadrumo.application.user_profile.profile_record_repository import require_profile_record_session
from cadrumo.application.user_profile.recovery_custody import (
    ProfileRecoveryError,
    enroll_profile_recovery,
    reset_profile_passphrase_with_recovery,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.time.clock import frozen_clock
from cadrumo.core.time.clock import now as _now
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.tests.os_keychain_hook import require_os_credential_store

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_LABEL = "Passphrase Replacement Subject"
_CURRENT = "passphrase-replacement-current-operator-secret"
_REPLACEMENT = "passphrase-replacement-new-operator-secret"


def _register() -> UUID:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    return UUID(outcome.profile_id)


def _enroll(profile_id: UUID) -> str:
    handed: list[str] = []
    enroll_profile_recovery(
        profile_id=profile_id,
        current_passphrase=_CURRENT,
        recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
    )
    return handed[0]


def _wrong(code: str) -> str:
    return code[:-1] + ("Z" if code[-1] != "Z" else "Y")


def _reset(profile_id: UUID, code: str, new_passphrase: str = _REPLACEMENT) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    reset_profile_passphrase_with_recovery(
        profile_id=profile_id,
        recovery_code=code,
        new_passphrase=new_passphrase,
        new_passphrase_confirmation=new_passphrase,
        profile_decode_context=_profile_decode_context_for_test,
    )


def _rotate(profile_id: UUID) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    rotate_profile_passphrase(
        profile_id=profile_id,
        current_passphrase=_CURRENT,
        new_passphrase=_REPLACEMENT,
        new_passphrase_confirmation=_REPLACEMENT,
        profile_decode_context=_profile_decode_context_for_test,
    )


def _replacement_proofs(profile_id: UUID, *, passphrase: str) -> list[str | None]:
    """Log in under ``passphrase`` and read every replacement event's recorded proof."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    login_profile(
        name=_LABEL,
        passphrase_callback=lambda: passphrase,
        profile_decode_context=_profile_decode_context_for_test,
    )
    try:
        history = ProfileRecordStore(
            session=require_profile_record_session(
                str(profile_id), profile_decode_context=_profile_decode_context_for_test
            )
        ).history()
    finally:
        logout_active_profile()
    return [
        event.payload.get("proof")
        for event in history
        if event.event_type is BucketEventType.PROFILE_PASSPHRASE_ROTATED
    ]


# ── lineage ──────────────────────────────────────────────────────────────────


def test_a_rotation_writes_the_replaced_envelope_digest_and_the_next_generation(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        before = load_committed_profile_password_material(profile_id).envelope
        assert before.password_generation == 1
        assert before.previous_envelope_digest is None

        _rotate(profile_id)

        after = load_committed_profile_password_material(profile_id).envelope
        assert after.password_generation == before.password_generation + 1
        assert after.previous_envelope_digest == before.self_digest


def test_a_reset_writes_the_replaced_envelope_digest_and_the_next_generation(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        first = load_committed_profile_password_material(profile_id).envelope

        _reset(profile_id, code)
        second = load_committed_profile_password_material(profile_id).envelope
        _reset(profile_id, code, new_passphrase=_CURRENT)
        third = load_committed_profile_password_material(profile_id).envelope

        assert (second.password_generation, second.previous_envelope_digest) == (2, first.self_digest)
        assert (third.password_generation, third.previous_envelope_digest) == (3, second.self_digest)


# ── proof on the audit event ─────────────────────────────────────────────────


def test_the_history_records_which_proof_authorised_each_replacement(tmp_path: Path) -> None:
    """One rotation and one reset: the same event type, told apart by its proof."""
    third = "passphrase-replacement-third-operator-secret"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        _rotate(profile_id)
        _reset(profile_id, code, new_passphrase=third)

        proofs = _replacement_proofs(profile_id, passphrase=third)

        assert proofs == ["current_passphrase", "recovery_code"]
        assert proofs == [
            ProfilePassphraseReplacementProof.CURRENT_CREDENTIAL,
            ProfilePassphraseReplacementProof.RECOVERY_CODE,
        ]


# ── failed-attempt backoff ───────────────────────────────────────────────────


def test_a_throttled_profile_refuses_a_reset_before_any_key_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even the CORRECT code is refused while the backoff holds, and the KDF is never reached."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        bucket_id = str(profile_id)
        # Five failures owe a 32-second wait: far longer than this test runs.
        for _ in range(5):
            record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=_now())
        envelope_before = load_committed_profile_password_material(profile_id).envelope

        def _kdf_reached(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("the recovery proof ran while the profile was throttled")

        monkeypatch.setattr(recovery_custody, "unlock_profile_custody_recovery", _kdf_reached)

        with pytest.raises(ProfileLoginThrottledError) as refused:
            _reset(profile_id, code)

        assert refused.value.remaining_seconds > 0
        assert load_committed_profile_password_material(profile_id).envelope == envelope_before
        assert (
            evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=_now()).consecutive_failures
            == 5
        )


def test_a_failed_recovery_proof_counts_against_the_login_backoff(tmp_path: Path) -> None:
    """The reset door and the login door share one counter, so alternating them buys nothing."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        bucket_id = str(profile_id)
        assert (
            evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=_now()).consecutive_failures
            == 0
        )

        # Held so the one-failure backoff, a two-second window, cannot elapse
        # while the proof and the login below run.
        refused_at = _now()
        with frozen_clock(refused_at), pytest.raises(ProfileRecoveryError) as refused:
            _reset(profile_id, _wrong(code))
        assert refused.value.translated_message == "application.user_profile.errors.recovery_code_rejected"

        evaluation = evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=refused_at)
        assert evaluation.consecutive_failures == 1
        assert evaluation.throttled is True

        # The login door now waits on the reset door's failure.
        _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
        with frozen_clock(refused_at + timedelta(seconds=1)), pytest.raises(ProfileLoginThrottledError):
            login_profile(
                name=_LABEL,
                passphrase_callback=lambda: _CURRENT,
                profile_decode_context=_profile_decode_context_for_test,
            )


def test_a_proven_recovery_code_clears_the_backoff_as_a_login_does(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        bucket_id = str(profile_id)
        # A failure old enough that its wait has elapsed: counted, not throttling.
        record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=_now() - timedelta(minutes=10))
        assert (
            evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=_now()).consecutive_failures
            == 1
        )

        _reset(profile_id, code)

        assert (
            evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=_now()).consecutive_failures
            == 0
        )


# ── what a reset leaves outstanding ──────────────────────────────────────────


@pytest.mark.os_keychain
def test_a_session_receipt_minted_before_a_reset_is_refused_at_resume(tmp_path: Path) -> None:
    """A receipt wraps the DEK against the generation it was minted under; a reset advances it."""
    require_os_credential_store()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        material = load_committed_profile_password_material(profile_id)
        dek = unlock_profile_custody_password(material, password=_CURRENT).dek
        issued = _now()
        mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            dek=bytes(dek),
            now=issued,
            idle_minutes=15,
            absolute_minutes=240,
        )
        try:
            # The control: before the reset the same receipt resumes, so the
            # refusal below is the reset's doing and nothing else's.
            control, control_dek = resume_profile_session(
                storage_root=storage_root,
                profile_id=profile_id,
                custody_generation=material.envelope.password_generation,
                dek_epoch=material.envelope.dek_epoch,
                now=issued + timedelta(minutes=1),
            )
            assert control.resumed is True
            assert control_dek is not None

            _reset(profile_id, code)
            current = load_committed_profile_password_material(profile_id).envelope

            outcome, resumed = resume_profile_session(
                storage_root=storage_root,
                profile_id=profile_id,
                custody_generation=current.password_generation,
                dek_epoch=current.dek_epoch,
                now=issued + timedelta(minutes=2),
            )

            assert outcome.resumed is False
            assert resumed is None
            assert outcome.refusal is ProfileSessionRefusalReason.CUSTODY_CHANGED
        finally:
            delete_profile_session(storage_root=storage_root, profile_id=profile_id)


def test_an_archive_exported_before_a_reset_restores_under_the_old_passphrase(tmp_path: Path) -> None:
    """A backup carries the envelope it was taken with, so a reset does not reach it.

    An operator who resets because the old passphrase leaked must also retire
    every archive taken under it: after the live profile is gone, the old
    archive still opens with the OLD passphrase and not with the new one.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        code = _enroll(profile_id)
        logout_active_profile()
        archive = tmp_path / "before-reset.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=profile_id, target=archive)

        _reset(profile_id, code)
        lifecycle = ProfileCapsuleLifecycle()
        lifecycle.delete(lifecycle.confirm_delete(lifecycle.prepare_delete(profile_id=profile_id)))

        with pytest.raises(ProfileAuthenticationRefusedError):
            restore_profile_capsule_with_password(
                label=_LABEL,
                capsule=read_profile_capsule_archive(archive),
                password=_REPLACEMENT,
                profile_decode_context=_profile_decode_context_for_test,
            )

        restored = restore_profile_capsule_with_password(
            label=_LABEL,
            capsule=read_profile_capsule_archive(archive),
            password=_CURRENT,
            profile_decode_context=_profile_decode_context_for_test,
        )

        assert restored.profile_id == str(profile_id)
        material = load_committed_profile_password_material(profile_id)
        assert material.envelope.password_generation == 1
        assert unlock_profile_custody_password(material, password=_CURRENT).dek is not None
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody_password(material, password=_REPLACEMENT)

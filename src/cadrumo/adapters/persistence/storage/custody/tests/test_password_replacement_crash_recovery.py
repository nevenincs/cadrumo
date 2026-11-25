"""A password replacement interrupted at any step settles into exactly one consistent state.

A replacement re-heads the profile record and then swaps the password
envelope, around a durable intent. Each test below stops one replacement at
one step boundary, as a crash would, and then signs in through the real login
door. The sign-in settles the intent before it reads the envelope, and what it
settles to depends only on how far the replacement got: before the record was
re-headed, the old password opens the old envelope; after it, the new
password opens the new one. Either way the record reads, the other password
is refused, and no intent is left behind.

Both doors that replace a password run the same steps, so each boundary is
crossed from a rotation and from a recovery reset. Real capsules, real
Argon2id through the supervised worker, real SQLite; the only substitution is
the interruption itself.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.password_replacement_intent import (
    ProfilePasswordReplacementIntent,
    ProfilePasswordReplacementResolution,
    profile_password_replacement_intent_path,
    profile_record_row_provenance,
    resolve_profile_password_replacement,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile import passphrase_rotation
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.profile_record_repository import require_profile_record_session
from cadrumo.application.user_profile.recovery_custody import (
    enroll_profile_recovery,
    reset_profile_passphrase_with_recovery,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.domain.buckets.event import BucketEventType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_LABEL = "Password Replacement Crash Subject"
_CURRENT = "password-replacement-crash-current-secret"
_REPLACEMENT = "password-replacement-crash-new-secret"


class _Crash(BaseException):
    """The process stopping at a step boundary; nothing in the replacement may catch it."""


def _register() -> UUID:
    create_context, decode_context = profile_authority_contexts()
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT,
        profile_create_context=create_context,
        profile_decode_context=decode_context,
    )
    return UUID(outcome.profile_id)


def _rotate(profile_id: UUID) -> None:
    _create_context, decode_context = profile_authority_contexts()
    rotate_profile_passphrase(
        profile_id=profile_id,
        current_passphrase=_CURRENT,
        new_passphrase=_REPLACEMENT,
        new_passphrase_confirmation=_REPLACEMENT,
        profile_decode_context=decode_context,
    )


def _reset_door(profile_id: UUID) -> Callable[[], None]:
    handed: list[str] = []
    enroll_profile_recovery(
        profile_id=profile_id,
        current_passphrase=_CURRENT,
        recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
    )
    _create_context, decode_context = profile_authority_contexts()

    def reset() -> None:
        reset_profile_passphrase_with_recovery(
            profile_id=profile_id,
            recovery_code=handed[0],
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
            profile_decode_context=decode_context,
        )

    return reset


def _door(name: str, profile_id: UUID) -> Callable[[], None]:
    if name == "rotation":
        return lambda: _rotate(profile_id)
    return _reset_door(profile_id)


def _crash_instead(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    def crash(*_args: object, **_kwargs: object) -> None:
        raise _Crash(step)

    monkeypatch.setattr(passphrase_rotation, step, crash)


def _crash_after(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    real = getattr(passphrase_rotation, step)

    def crash(*args: object, **kwargs: object) -> None:
        real(*args, **kwargs)
        raise _Crash(step)

    monkeypatch.setattr(passphrase_rotation, step, crash)


# Each boundary, and the password that must open the profile once a sign-in has settled it.
_BOUNDARIES: dict[str, tuple[Callable[[pytest.MonkeyPatch], None], str]] = {
    "before_the_intent": (
        lambda patch: _crash_instead(patch, "stage_profile_custody_password_replacement"),
        _CURRENT,
    ),
    "after_the_intent_before_the_re_head": (
        lambda patch: _crash_after(patch, "stage_profile_custody_password_replacement"),
        _CURRENT,
    ),
    "after_the_re_head_before_it_is_durable": (
        lambda patch: _crash_instead(patch, "make_profile_custody_record_durable"),
        _REPLACEMENT,
    ),
    "after_the_durable_re_head_before_the_swap": (
        lambda patch: _crash_instead(patch, "replace_profile_custody_password_envelope"),
        _REPLACEMENT,
    ),
    "after_the_swap_before_the_intent_is_cleared": (
        lambda patch: _crash_instead(patch, "clear_profile_custody_password_replacement"),
        _REPLACEMENT,
    ),
}


@contextmanager
def _signed_in(passphrase: str) -> Generator[ProfileRecordStore]:
    _create_context, decode_context = profile_authority_contexts()
    outcome = authenticate_profile_for_invocation(
        name=_LABEL,
        passphrase_callback=lambda: passphrase,
        profile_decode_context=decode_context,
    )
    try:
        yield ProfileRecordStore(
            session=require_profile_record_session(outcome.bucket_id, profile_decode_context=decode_context)
        )
    finally:
        reset_test_profile_session()


def _interrupted(
    monkeypatch: pytest.MonkeyPatch, interrupt: Callable[[pytest.MonkeyPatch], None], replace: Callable[[], None]
) -> None:
    with monkeypatch.context() as patch:
        interrupt(patch)
        with pytest.raises(_Crash):
            replace()


def _rotation_events(store: ProfileRecordStore) -> list[object]:
    return [event for event in store.history() if event.event_type is BucketEventType.PROFILE_PASSPHRASE_ROTATED]


@pytest.mark.parametrize("door", ["rotation", "recovery_reset"])
@pytest.mark.parametrize("boundary", list(_BOUNDARIES))
def test_a_sign_in_settles_an_interrupted_replacement_into_one_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, door: str, boundary: str
) -> None:
    interrupt, settled_password = _BOUNDARIES[boundary]
    rolled_forward = settled_password == _REPLACEMENT
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        replace = _door(door, profile_id)
        reset_test_profile_session()
        before = load_committed_profile_password_material(profile_id).envelope
        _interrupted(monkeypatch, interrupt, replace)

        with _signed_in(settled_password) as store:
            assert store.load().record.profile_id == str(profile_id)
            assert len(_rotation_events(store)) == int(rolled_forward)

        after = load_committed_profile_password_material(profile_id).envelope
        assert not os.path.lexists(profile_password_replacement_intent_path(profile_id, root=storage_root))
        expected = (
            (before.password_generation + 1, before.self_digest)
            if rolled_forward
            else (before.password_generation, before.previous_envelope_digest)
        )
        assert (after.password_generation, after.previous_envelope_digest) == expected
        assert (after == before) is not rolled_forward
        with pytest.raises(ProfileAuthenticationRefusedError), _signed_in(_CURRENT if rolled_forward else _REPLACEMENT):
            pass


def test_an_intent_that_matches_neither_side_is_refused_and_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recovery never guesses: a record header the replacement cannot have written stops it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        reset_test_profile_session()
        _interrupted(
            monkeypatch,
            lambda patch: _crash_after(patch, "stage_profile_custody_password_replacement"),
            lambda: _rotate(profile_id),
        )
        path = profile_password_replacement_intent_path(profile_id, root=storage_root)
        staged = ProfilePasswordReplacementIntent.model_validate_json(path.read_bytes())
        assert staged.previous_row_provenance == profile_record_row_provenance(profile_id, root=storage_root)
        foreign = ProfilePasswordReplacementIntent.create(
            profile_id=profile_id,
            expected_envelope=load_committed_profile_password_material(profile_id).envelope.canonical_json_bytes(),
            proposed_envelope=staged.proposed_envelope_bytes,
            previous_row_provenance="record-write-provenance:not-this-row",
            rehead_row_provenance="record-write-provenance:nor-this-one",
        )
        path.unlink()
        path.write_bytes(foreign.canonical_json_bytes())

        with pytest.raises(ProfileCustodyRecordError):
            resolve_profile_password_replacement(profile_id, root=storage_root)
        assert path.read_bytes() == foreign.canonical_json_bytes()
        path.unlink()
        path.write_bytes(staged.canonical_json_bytes())
        assert (
            resolve_profile_password_replacement(profile_id, root=storage_root)
            is ProfilePasswordReplacementResolution.ROLLED_BACK
        )

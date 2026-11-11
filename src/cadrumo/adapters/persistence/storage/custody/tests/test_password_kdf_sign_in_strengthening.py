"""A sign-in re-wraps a fallback password envelope at a stronger point, once, and only when nothing else depends on it.

The strengthening door is a password replacement with the same password: the
same data key and epoch under the successor generation, at a measured point
strictly stronger than the fixed fallback. It writes nothing when the envelope
the attempt proved is no longer committed, when the envelope is already past
the fallback, or when automation custody exists that the replacement would
retire. Interrupted at any step, it settles through the replacement journal to
exactly one envelope, old or new, and the one password opens it. Real capsules,
real Argon2id through the supervised worker, real SQLite; the only substitution
is the interruption itself.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.password_replacement_intent import (
    profile_password_replacement_intent_path,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile import passphrase_rotation
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.custody_ports import (
    ProfileKdfStrength,
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.passphrase_rotation import (
    ProfilePassphraseReplacementProof,
    strengthen_profile_password_kdf,
)
from cadrumo.application.user_profile.profile_record_repository import require_profile_record_session
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.domain.buckets.event import BucketEventType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_LABEL = "Sign-In Strengthening Subject"
_CREDENTIAL = "sign-in-strengthening-current-secret"
_FALLBACK = (64, 3, 1)
_STRONGER = ProfileKdfStrength(memory_mib=64, iterations=4, parallelism=1)


class _Crash(BaseException):
    """The process stopping at a step boundary; nothing in the replacement may catch it."""


def _register() -> UUID:
    create_context, decode_context = profile_authority_contexts()
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CREDENTIAL,
        profile_create_context=create_context,
        profile_decode_context=decode_context,
    )
    reset_test_profile_session()
    return UUID(outcome.profile_id)


def _point(profile_id: UUID) -> tuple[int, int, int]:
    kdf = load_committed_profile_password_material(profile_id).envelope.kdf
    return kdf.memory_mib, kdf.iterations, kdf.parallelism


def _strengthen(profile_id: UUID, *, proven_digest: str | None = None) -> bool:
    """Strengthen as a sign-in would: with the password it proved and the digest of the envelope it opened."""
    material = load_profile_custody_password_material(profile_id)
    dek = unlock_profile_custody_password(material, password=_CREDENTIAL).dek
    _create_context, decode_context = profile_authority_contexts()
    return strengthen_profile_password_kdf(
        profile_id=profile_id,
        password=_CREDENTIAL,
        dek=dek,
        proven_envelope_digest=material.envelope.self_digest if proven_digest is None else proven_digest,
        strength=_STRONGER,
        profile_decode_context=decode_context,
    )


@contextmanager
def _signed_in() -> Generator[ProfileRecordStore]:
    _create_context, decode_context = profile_authority_contexts()
    outcome = authenticate_profile_for_invocation(
        name=_LABEL,
        passphrase_callback=lambda: _CREDENTIAL,
        profile_decode_context=decode_context,
    )
    try:
        yield ProfileRecordStore(
            session=require_profile_record_session(outcome.bucket_id, profile_decode_context=decode_context)
        )
    finally:
        reset_test_profile_session()


def _rotation_proofs(store: ProfileRecordStore) -> list[str]:
    return [
        event.payload["proof"]
        for event in store.history()
        if event.event_type is BucketEventType.PROFILE_PASSPHRASE_ROTATED
    ]


def test_a_fallback_envelope_is_strengthened_over_the_same_key_and_password(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        before = load_committed_profile_password_material(profile_id).envelope
        assert _point(profile_id) == _FALLBACK
        dek = unlock_profile_custody_password(
            load_profile_custody_password_material(profile_id), password=_CREDENTIAL
        ).dek

        assert _strengthen(profile_id)

        after = load_committed_profile_password_material(profile_id).envelope
        assert _point(profile_id) == (64, 4, 1)
        assert (after.password_generation, after.previous_envelope_digest) == (
            before.password_generation + 1,
            before.self_digest,
        )
        assert after.dek_epoch == before.dek_epoch
        assert (
            unlock_profile_custody_password(
                load_profile_custody_password_material(profile_id), password=_CREDENTIAL
            ).dek
            == dek
        )
        with _signed_in() as store:
            assert store.load().record.profile_id == str(profile_id)
            assert _rotation_proofs(store) == [ProfilePassphraseReplacementProof.SIGN_IN_STRENGTHENING.value]
        # The envelope is past the fallback now, so a second attempt writes nothing.
        assert not _strengthen(profile_id)
        assert load_committed_profile_password_material(profile_id).envelope == after


def test_an_envelope_other_than_the_one_proved_is_left_alone(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        before = load_committed_profile_password_material(profile_id).envelope
        assert not _strengthen(profile_id, proven_digest="sha256:" + "0" * 64)
        assert load_committed_profile_password_material(profile_id).envelope == before


def test_automation_custody_holds_strengthening_off(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        before = load_committed_profile_password_material(profile_id).envelope
        (storage_root / ".automation-v1" / str(uuid4()) / str(profile_id)).mkdir(parents=True)
        assert not _strengthen(profile_id)
        assert load_committed_profile_password_material(profile_id).envelope == before


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


# Each boundary, and whether a sign-in settles it forward onto the stronger envelope.
_BOUNDARIES: dict[str, tuple[Callable[[pytest.MonkeyPatch], None], bool]] = {
    "before_the_intent": (lambda patch: _crash_instead(patch, "stage_profile_custody_password_replacement"), False),
    "after_the_intent_before_the_re_head": (
        lambda patch: _crash_after(patch, "stage_profile_custody_password_replacement"),
        False,
    ),
    "after_the_re_head_before_it_is_durable": (
        lambda patch: _crash_instead(patch, "make_profile_custody_record_durable"),
        True,
    ),
    "after_the_durable_re_head_before_the_swap": (
        lambda patch: _crash_instead(patch, "replace_profile_custody_password_envelope"),
        True,
    ),
    "after_the_swap_before_the_intent_is_cleared": (
        lambda patch: _crash_instead(patch, "clear_profile_custody_password_replacement"),
        True,
    ),
}


@pytest.mark.parametrize("boundary", list(_BOUNDARIES))
def test_an_interrupted_strengthening_settles_into_one_envelope_the_password_opens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    interrupt, rolled_forward = _BOUNDARIES[boundary]
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_id = _register()
        before = load_committed_profile_password_material(profile_id).envelope
        with monkeypatch.context() as patch:
            interrupt(patch)
            with pytest.raises(_Crash):
                _strengthen(profile_id)

        with _signed_in() as store:
            assert store.load().record.profile_id == str(profile_id)
            assert len(_rotation_proofs(store)) == int(rolled_forward)

        after = load_committed_profile_password_material(profile_id).envelope
        assert not os.path.lexists(profile_password_replacement_intent_path(profile_id, root=storage_root))
        assert _point(profile_id) == ((64, 4, 1) if rolled_forward else _FALLBACK)
        assert after.password_generation == before.password_generation + int(rolled_forward)
        assert (after == before) is not rolled_forward

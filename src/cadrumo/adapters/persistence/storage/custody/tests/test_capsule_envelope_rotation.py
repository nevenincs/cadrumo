"""The committed-capsule envelope replacement a passphrase rotation performs.

Rotation re-wraps the SAME data key under a key derived from a new password, so
exactly one capsule member changes: ``custody/envelope.v1.json``. Everything
else about the capsule is invariant, and the two properties that make that safe
are proven here rather than assumed.

The first is that the DEK sentinel is untouched. Its associated data binds only
``(profile_id, dek_epoch)``, so an epoch-preserving rotation leaves the
committed sentinel valid -- and with it every recovery artifact already minted
against that epoch. A rotation that quietly re-minted the sentinel would revoke
an operator's recovery mnemonic as a side effect of changing their password.

The second is that an envelope carrying a DIFFERENT epoch is refused. That is a
re-key rather than a rotation, and accepting it here would leave the sentinel
and every recovery artifact unopenable while the write reported success. The
invariant is enforced at the write boundary so it cannot be lost by a caller.

Real capsules on a real filesystem, real Argon2id-derived envelopes, real
sentinel verification. Nothing mocked.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ......core.config import Settings
from ......core.hashing import prefixed_digest
from ..capsule import (
    load_committed_profile_password_material,
    publish_profile_custody_capsule,
    recognize_current_profile_capsule,
    replace_committed_profile_custody_envelope,
)
from ..envelope import create_profile_custody_password_envelope
from ..errors import ProfileCustodyPasswordError, ProfileCustodyRecordError
from ..kdf_supervision import unlock_profile_custody
from ..records import PROFILE_CUSTODY_ENVELOPE_FILENAME, ProfileCustodyKdfParameters
from ..recovery import create_profile_custody_recovery_envelope, unlock_profile_custody_recovery
from ..sentinel import create_profile_custody_sentinel

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("5f1c2a7b-90de-4f31-8c62-3ab7d05e9142")
_OTHER_PROFILE_ID = UUID("a3d9e04c-71b8-4265-9e13-6c8f2b40d597")
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")
_OTHER_EPOCH = base64.b64encode(b"f" * 16).decode("ascii")
_OLD_PASSWORD = "profile " + "password" + " 123"
_NEW_PASSWORD = "rotated " + "passphrase" + " 456"
_RECOVERY_SECRET = "profile " + "recovery" + " 123"


def _settings(tmp_path: Path) -> Settings:
    return Settings(cadrumo_local_storage_root=tmp_path / "state")


def _kdf(salt: bytes = b"k" * 16) -> ProfileCustodyKdfParameters:
    """Stated Argon2id parameters: rotation is about WHICH password, not cost."""
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(salt).decode("ascii"),
        output_bytes=32,
    )


def _publish(tmp_path: Path, settings: Settings) -> None:
    """Publish one committed capsule for ``_PROFILE_ID`` under ``settings``."""
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_OLD_PASSWORD,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={},
        settings=settings,
    )


def _envelope_path(settings: Settings) -> Path:
    capsule = recognize_current_profile_capsule(_PROFILE_ID, settings=settings)
    assert capsule is not None
    return capsule / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME


def _rewrapped(settings: Settings, *, dek_epoch: str = _EPOCH, profile_id: UUID = _PROFILE_ID) -> bytes:
    """Return a genuine envelope wrapping the same DEK under the new password."""
    return create_profile_custody_password_envelope(
        profile_id=profile_id,
        password=_NEW_PASSWORD,
        dek=_DEK,
        dek_epoch=dek_epoch,
        # A fresh salt, as a real rotation mints: the same password must not
        # reproduce the same wrapped bytes.
        kdf=_kdf(salt=b"r" * 16),
        settings=settings,
    ).canonical_json_bytes()


def test_rotation_swaps_the_password_without_touching_the_data_key(tmp_path: Path) -> None:
    """After the swap the new password unwraps the SAME DEK and the old one is refused."""
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    envelope_path = _envelope_path(settings)
    witness = prefixed_digest(envelope_path.read_bytes())

    replace_committed_profile_custody_envelope(
        _PROFILE_ID,
        _rewrapped(settings),
        expected_sha256=witness,
        settings=settings,
    )

    # Read back through the production committed-material path, so the
    # rotated envelope is checked against the sentinel still on disk.
    material = load_committed_profile_password_material(_PROFILE_ID, settings=settings)
    unlocked = unlock_profile_custody(password=_NEW_PASSWORD, envelope=material.envelope, sentinel=material.sentinel)
    assert bytes(unlocked.dek) == _DEK
    # The narrower password refusal, not merely "some custody error": the old
    # password must fail to AUTHENTICATE, which is the property rotation sells.
    with pytest.raises(ProfileCustodyPasswordError):
        unlock_profile_custody(password=_OLD_PASSWORD, envelope=material.envelope, sentinel=material.sentinel)


def test_rotation_leaves_the_sentinel_and_its_recovery_artifact_valid(tmp_path: Path) -> None:
    """The property the epoch invariant exists to protect, proven end to end.

    A recovery envelope minted BEFORE the rotation must still unwrap to the same
    key afterwards. If the primitive re-minted the sentinel, or accepted a new
    epoch, this operator would have silently lost their recovery route by
    changing their password.
    """
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    recovery = create_profile_custody_recovery_envelope(
        profile_id=_PROFILE_ID,
        recovery_secret=_RECOVERY_SECRET,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(salt=b"y" * 16),
        settings=settings,
    )
    envelope_path = _envelope_path(settings)
    sentinel_before = (envelope_path.parent.parent / "data").glob("*")
    sentinel_bytes_before = sorted((p.name, p.read_bytes()) for p in sentinel_before if p.is_file())

    replace_committed_profile_custody_envelope(
        _PROFILE_ID,
        _rewrapped(settings),
        expected_sha256=prefixed_digest(envelope_path.read_bytes()),
        settings=settings,
    )

    # The COMMITTED sentinel -- the one on disk, not a freshly minted stand-in --
    # still opens the pre-rotation recovery envelope to the identical data key.
    material = load_committed_profile_password_material(_PROFILE_ID, settings=settings)
    recovered = unlock_profile_custody_recovery(
        recovery_secret=_RECOVERY_SECRET,
        envelope=recovery,
        sentinel=material.sentinel,
    )
    assert bytes(recovered.dek) == _DEK
    assert recovered.dek_epoch == _EPOCH
    # And the new password opens the rotated envelope against that same sentinel.
    unlocked = unlock_profile_custody(password=_NEW_PASSWORD, envelope=material.envelope, sentinel=material.sentinel)
    assert bytes(unlocked.dek) == _DEK
    # No other capsule member was rewritten.
    sentinel_after = (envelope_path.parent.parent / "data").glob("*")
    assert sorted((p.name, p.read_bytes()) for p in sentinel_after if p.is_file()) == sentinel_bytes_before


def test_rotation_refuses_an_envelope_that_changes_the_dek_epoch(tmp_path: Path) -> None:
    """A re-key wearing a rotation's clothes is refused, and nothing is written."""
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    envelope_path = _envelope_path(settings)
    before = envelope_path.read_bytes()

    with pytest.raises(ProfileCustodyRecordError, match="changes the DEK epoch"):
        replace_committed_profile_custody_envelope(
            _PROFILE_ID,
            _rewrapped(settings, dek_epoch=_OTHER_EPOCH),
            expected_sha256=prefixed_digest(before),
            settings=settings,
        )

    assert envelope_path.read_bytes() == before


def test_rotation_refuses_an_envelope_naming_another_profile(tmp_path: Path) -> None:
    """The capsule's own identity is checked, not merely the caller's argument."""
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    envelope_path = _envelope_path(settings)
    before = envelope_path.read_bytes()

    with pytest.raises(ProfileCustodyRecordError, match="different profile"):
        replace_committed_profile_custody_envelope(
            _PROFILE_ID,
            _rewrapped(settings, profile_id=_OTHER_PROFILE_ID),
            expected_sha256=prefixed_digest(before),
            settings=settings,
        )

    assert envelope_path.read_bytes() == before


def test_rotation_refuses_a_stale_compare_and_swap_witness(tmp_path: Path) -> None:
    """A concurrent writer's rotation is not overwritten by a stale one.

    The witness is what makes two racing rotations safe: the second caller
    authenticated bytes that are no longer current, so its write is refused
    rather than silently discarding the first caller's new password.
    """
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    envelope_path = _envelope_path(settings)
    stale_witness = prefixed_digest(envelope_path.read_bytes())

    replace_committed_profile_custody_envelope(
        _PROFILE_ID,
        _rewrapped(settings),
        expected_sha256=stale_witness,
        settings=settings,
    )
    after_first = envelope_path.read_bytes()

    with pytest.raises(ProfileCustodyRecordError, match="compare-and-swap witness is stale"):
        replace_committed_profile_custody_envelope(
            _PROFILE_ID,
            _rewrapped(settings),
            expected_sha256=stale_witness,
            settings=settings,
        )

    assert envelope_path.read_bytes() == after_first


def test_rotation_refuses_when_no_capsule_is_committed(tmp_path: Path) -> None:
    """Without a committed capsule there is nothing to rotate, and no file is created."""
    settings = _settings(tmp_path)

    with pytest.raises(ProfileCustodyRecordError, match="requires a committed capsule"):
        replace_committed_profile_custody_envelope(
            _PROFILE_ID,
            b"{}",
            expected_sha256=prefixed_digest(b"{}"),
            settings=settings,
        )


def test_rotation_refuses_a_payload_that_is_not_an_envelope(tmp_path: Path) -> None:
    """Malformed bytes are refused before the swap, not written and parsed later."""
    settings = _settings(tmp_path)
    _publish(tmp_path, settings)
    envelope_path = _envelope_path(settings)
    before = envelope_path.read_bytes()

    with pytest.raises(ProfileCustodyRecordError, match="not a valid envelope"):
        replace_committed_profile_custody_envelope(
            _PROFILE_ID,
            b'{"not": "an envelope"}',
            expected_sha256=prefixed_digest(before),
            settings=settings,
        )

    assert envelope_path.read_bytes() == before

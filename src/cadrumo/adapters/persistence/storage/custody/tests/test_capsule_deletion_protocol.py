"""The guard that decides which directory a profile deletion may destroy.

``verify_profile_custody_deletion_tombstone`` returns the exact
transaction-owned tombstone proven safe to remove, and its caller removes what
it returns. Every refusal in it therefore stands between a profile deletion and
the destruction of something it does not own: a live capsule, another
transaction's tombstone, or data that arrived after the operator consented.

The five-step protocol (mark, rename, verify tombstone, verify marker, remove
tombstone) is consumed by the custody delete flow in the application layer, and
three of its five functions had no test naming them at all.

Each refusal is paired with the acceptance it must not break, because a verifier
that refused everything would satisfy every refusal on its own while stranding
every legitimate deletion. Driven against real published capsules and real
filesystem state: the guard's subject is the filesystem, and a stand-in for it
would assert only the shape of the call.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ......core.config import Settings
from .. import (
    ProfileCustodyKdfParameters,
    ProfileCustodyRecordError,
    create_profile_custody_password_envelope,
    create_profile_custody_recovery_envelope,
    create_profile_custody_sentinel,
    inventory_committed_profile_custody_capsule,
    profile_custody_deletion_path,
    publish_profile_custody_capsule,
    recognize_current_profile_capsule,
    remove_profile_custody_deletion_tombstone,
    rename_profile_custody_capsule_for_deletion,
    verify_profile_custody_deletion_marker,
    verify_profile_custody_deletion_tombstone,
    write_profile_custody_deletion_marker,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("327b296d-8377-4be0-b13a-ca4d8f692e1d")
_TRANSACTION_ID = UUID("4f28d1c4-e466-4a08-a25a-ea5925146f36")
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")
_PASSPHRASE = "profile " + "password" + " 123"
_RECOVERY_SECRET = "profile " + "recovery" + " 123"


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
        output_bytes=32,
    )


def _publish(tmp_path: Path) -> Settings:
    """Publish one committed capsule the deletion protocol can operate on."""
    settings = Settings(cadrumo_local_storage_root=tmp_path)
    envelope = create_profile_custody_password_envelope(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    recovery = create_profile_custody_recovery_envelope(
        profile_id=_PROFILE_ID,
        recovery_secret=_RECOVERY_SECRET,
        dek=_DEK,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        settings=settings,
    )
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        recovery_envelope=recovery,
        data_files={"state/current.bin": b"current encrypted payload"},
        settings=settings,
    )
    return settings


def _digest(settings: Settings) -> str:
    """Return the committed capsule's current inventory digest."""
    return inventory_committed_profile_custody_capsule(_PROFILE_ID, settings=settings).digest


def _prepare_tombstone(settings: Settings) -> tuple[str, Path]:
    """Run the protocol up to the point the tombstone exists."""
    digest = _digest(settings)
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )
    tombstone = rename_profile_custody_capsule_for_deletion(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        settings=settings,
    )
    return digest, tombstone


def test_the_prepared_tombstone_is_the_one_returned_as_safe_to_remove(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the guard must still approve the deletion it owns.

    Every refusal below would be satisfied by a verifier that never returned,
    which would strand every profile deletion instead of protecting it.
    """
    settings = _publish(tmp_path)
    digest, tombstone = _prepare_tombstone(settings)

    approved = verify_profile_custody_deletion_tombstone(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )

    assert approved == tombstone


def test_a_tombstone_owned_by_another_transaction_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: the tombstone exists, but it is not this deletion's.

    The tombstone path is derived from the transaction id, so a foreign
    transaction owns no tombstone and must not be handed this one to destroy.
    """
    settings = _publish(tmp_path)
    digest, _tombstone = _prepare_tombstone(settings)

    with pytest.raises(ProfileCustodyRecordError):
        verify_profile_custody_deletion_tombstone(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            inventory_digest=digest,
            settings=settings,
        )


def test_a_tombstone_whose_contents_changed_since_preflight_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: new data must not be destroyed by an old approval.

    The inventory digest is captured before the deletion is prepared. If the
    capsule gained a file afterwards, approving removal would destroy data the
    operator never consented to delete.
    """
    settings = _publish(tmp_path)
    digest, tombstone = _prepare_tombstone(settings)
    (tombstone / "arrived-after-preflight.bin").write_bytes(b"unconsented")

    with pytest.raises(ProfileCustodyRecordError, match="inventory"):
        verify_profile_custody_deletion_tombstone(
            profile_id=_PROFILE_ID,
            transaction_id=_TRANSACTION_ID,
            inventory_digest=digest,
            settings=settings,
        )


def test_a_missing_tombstone_is_refused_rather_than_treated_as_done(tmp_path: Path) -> None:
    """An absent tombstone is ambiguous, not an idempotent success.

    Reporting the removal as already complete would let a delete transaction
    advance past a step it never performed.
    """
    settings = _publish(tmp_path)

    with pytest.raises(ProfileCustodyRecordError, match="ambiguous"):
        verify_profile_custody_deletion_tombstone(
            profile_id=_PROFILE_ID,
            transaction_id=_TRANSACTION_ID,
            inventory_digest=_digest(settings),
            settings=settings,
        )


def test_a_second_deletion_marker_is_refused_on_the_same_capsule(tmp_path: Path) -> None:
    """DISCRIMINATING: the marker binds one deletion exclusively.

    A second marker would let two transactions each believe they own the
    destruction of the same capsule.
    """
    settings = _publish(tmp_path)
    digest = _digest(settings)
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )

    with pytest.raises(ProfileCustodyRecordError, match="already carries"):
        write_profile_custody_deletion_marker(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            inventory_digest=digest,
            settings=settings,
        )


def test_marking_an_uncommitted_capsule_is_refused(tmp_path: Path) -> None:
    """There is nothing to bind a deletion to before publication."""
    settings = Settings(cadrumo_local_storage_root=tmp_path)

    with pytest.raises(ProfileCustodyRecordError, match="not committed"):
        write_profile_custody_deletion_marker(
            profile_id=_PROFILE_ID,
            transaction_id=_TRANSACTION_ID,
            inventory_digest="0" * 64,
            settings=settings,
        )


def test_the_prepared_marker_is_verified_while_the_capsule_keeps_its_name(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the pre-rename checkpoint must approve its own deletion.

    This is the checkpoint taken BEFORE the capsule is renamed away, so a
    verifier that refused everything would block every deletion at the step
    before the destructive one.
    """
    settings = _publish(tmp_path)
    digest = _digest(settings)
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )

    capsule = verify_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )

    assert capsule.is_dir()


def test_a_marker_bound_to_another_transaction_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: the marker on disk belongs to a different deletion.

    Unlike the tombstone, the marker path is fixed inside the capsule, so a
    foreign transaction genuinely reaches this marker and must be turned away
    by the binding rather than by the path.
    """
    settings = _publish(tmp_path)
    digest = _digest(settings)
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )

    with pytest.raises(ProfileCustodyRecordError, match="does not bind"):
        verify_profile_custody_deletion_marker(
            profile_id=_PROFILE_ID,
            transaction_id=uuid4(),
            inventory_digest=digest,
            settings=settings,
        )


def test_a_capsule_that_changed_after_marking_is_refused(tmp_path: Path) -> None:
    """New data arriving after the marker must not be swept into the deletion."""
    settings = _publish(tmp_path)
    digest = _digest(settings)
    write_profile_custody_deletion_marker(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        inventory_digest=digest,
        settings=settings,
    )
    capsule = recognize_current_profile_capsule(_PROFILE_ID, settings=settings)
    assert capsule is not None
    (capsule / "arrived-after-marking.bin").write_bytes(b"unconsented")

    with pytest.raises(ProfileCustodyRecordError, match="inventory"):
        verify_profile_custody_deletion_marker(
            profile_id=_PROFILE_ID,
            transaction_id=_TRANSACTION_ID,
            inventory_digest=digest,
            settings=settings,
        )


def test_the_tombstone_removal_actually_removes_it(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the removal must do its job, not merely be careful."""
    settings = _publish(tmp_path)
    _digest_value, tombstone = _prepare_tombstone(settings)

    remove_profile_custody_deletion_tombstone(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        settings=settings,
    )

    assert not tombstone.exists()


def test_removing_an_absent_tombstone_is_idempotent(tmp_path: Path) -> None:
    """A retried rollback clears a tombstone that may already be gone."""
    settings = _publish(tmp_path)

    remove_profile_custody_deletion_tombstone(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        settings=settings,
    )


def test_a_symlinked_tombstone_is_refused_and_its_target_survives(tmp_path: Path) -> None:
    """DISCRIMINATING: the removal deletes a TREE, so a link must never be followed.

    If the tombstone path is a link, following it would recursively delete
    whatever it points at -- a directory the deletion never owned. The refusal
    is asserted together with the survival of the target, because a guard that
    raised only after removing the contents would satisfy the exception alone.

    Deliberately asserts the OUTCOME rather than one mechanism: the path is
    defended twice over, by the directory anchor's reparse check and again by
    the staging snapshot, and removing either one alone still leaves the target
    intact. Naming a single guard here would make the test pass for a reason it
    does not actually pin.
    """
    settings = _publish(tmp_path)
    tombstone = profile_custody_deletion_path(
        profile_id=_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        settings=settings,
    )
    victim = tmp_path / "not-ours"
    victim.mkdir()
    (victim / "keepsake.bin").write_bytes(b"must survive")
    tombstone.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(victim, tombstone, target_is_directory=True)

    with pytest.raises(ProfileCustodyRecordError):
        remove_profile_custody_deletion_tombstone(
            profile_id=_PROFILE_ID,
            transaction_id=_TRANSACTION_ID,
            settings=settings,
        )

    assert (victim / "keepsake.bin").read_bytes() == b"must survive"

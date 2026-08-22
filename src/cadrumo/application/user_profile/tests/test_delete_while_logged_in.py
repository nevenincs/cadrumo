"""Deleting a profile the operator is signed into, without losing the guard.

A local deletion inventories the capsule at preflight, pins that digest into a
deletion marker, and re-authenticates the marker against the source capsule
before every later destructive step. A live login holds the capsule's own
SQLite connection open, so the write-ahead sidecars sit inside the tree that
inventory walks -- and the deletion's FIRST act is to revoke the live profile
secret, which closes that connection, checkpoints the sidecars away and rewrites
the main database file. The re-inventory could therefore never match the digest
the same transaction had just prepared, and the ordinary logged-in deletion
refused itself. The configuration reset path reaches this directly: it runs
prepare, confirm and delete with no prior session close.

Both directions are proven here, because a guard that stops refusing is worse
than the bug it fixed. Real registration, real login, real capsule, real DEK,
real encrypted store, real custody transaction; nothing is mocked or stubbed,
and every path runs under an isolated storage root.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage import master_key
from ....adapters.persistence.storage.custody import (
    inventory_committed_profile_custody_capsule,
    recognize_current_profile_capsule,
)
from ....core.time import now as _now
from ....tests.secure_sql import isolated_profile_storage_root
from ...evidence import LegalHoldCaseAuthority
from ...filing import FilingRetentionAuthority
from .._custody_service import _ProfileCustodyTransactionCapability as ProfileCustodyTransactionService
from .._custody_transactions import (
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionState,
)
from .._lifecycle import ProfileCapsuleLifecycle
from .._login_session import login_profile
from .._profile_record_repository import close_active_profile_record_session
from .._registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "delete-while-logged-in-password"  # noqa: S105 - real test credential
_LABEL = "Signed-in operator"

_LABEL_RECORD_RELATIVE_PATH = "data/profile-label.v1.json"


def _close_live_login() -> None:
    close_active_profile_record_session()
    master_key.close_active_bucket_session()


def _register_and_sign_in(root: Path) -> UUID:
    """Register a real profile and open a real login session against it.

    ``login_profile`` is what makes this reproduction the ordinary case rather
    than a contrived one: it opens the capsule's own database connection, which
    is the thing whose sidecars land inside the inventoried tree.
    """
    outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
    login_profile(name=outcome.profile_id, passphrase_callback=lambda: _PASSWORD)
    assert master_key.current_active_bucket_session() is not None, (
        "the login must be live, or nothing here reproduces the logged-in case"
    )
    return UUID(outcome.profile_id)


def _authorise_clear_hold(root: Path, profile_id: UUID) -> None:
    """Record the real owner facts a deletion consumes projections of.

    Deletion refuses without them; an empty legal-hold snapshot and an empty
    filing catalogue are the genuine "nothing retains this profile" state, not
    a bypass of the check.
    """
    LegalHoldCaseAuthority(root=root).record_open_case_snapshot(
        profile_id=profile_id,
        open_case_ids=(),
        observed_at=_now(),
    )
    FilingRetentionAuthority(root=root).record_filing_catalogue(
        profile_id=profile_id,
        records=(),
        observed_at=_now(),
    )


def _capsule_of(root: Path, profile_id: UUID) -> Path:
    capsule = recognize_current_profile_capsule(profile_id, root=root)
    assert capsule is not None
    return capsule


def _assert_content_covered(root: Path, profile_id: UUID, relative_path: str) -> None:
    """Refuse to let a negative case pass vacuously.

    A "still refuses when custody content changed" proof means nothing if the
    file it mutates is one the digest deliberately stopped covering. The
    database and its sidecars are exactly such files now, so every negative
    case below states which member it perturbs and this checks that the digest
    really does answer for that member's CONTENT.
    """
    inventory = inventory_committed_profile_custody_capsule(profile_id, root=root)
    covered = {entry.relative_path for entry in inventory.digest_entries}
    assert relative_path in covered, (
        f"{relative_path} is not content-covered by the inventory digest, so mutating it proves nothing"
    )


def test_a_profile_the_operator_is_signed_into_can_be_deleted(tmp_path: Path) -> None:
    """The blocking defect, driven through the public lifecycle end to end.

    This is the exact call sequence ``application/config_reset.py`` uses to
    erase a target -- prepare, confirm, delete, with no session close before it
    -- so proving it here proves the reset path.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_sign_in(storage_root)
            _authorise_clear_hold(storage_root, profile_id)
            capsule = _capsule_of(storage_root, profile_id)
            assert (capsule / "db/cadrumo.db-wal").is_file(), (
                "the live login must hold the capsule database open, or the case is not the one that failed"
            )
            lifecycle = ProfileCapsuleLifecycle(root=storage_root)

            journal = lifecycle.prepare_delete(profile_id=profile_id)
            receipt = lifecycle.delete(lifecycle.confirm_delete(journal))

            assert receipt.profile_id == profile_id
            assert recognize_current_profile_capsule(profile_id, root=storage_root) is None
            assert not capsule.exists()
        finally:
            _close_live_login()


def test_a_changed_custody_record_still_refuses_the_prepared_deletion(tmp_path: Path) -> None:
    """The marker's reason for existing, exercised through a real mutation.

    The label CAS writer that once carried this mutation was removed as a
    verified-dead surface, so the durable custody record is perturbed directly,
    as the marker-level sibling test does. The operator confirmed a specific
    inventory; the capsule is no longer that inventory, so the deletion must
    refuse rather than destroy what it was not shown.

    The label projection is a content-covered member, checked rather than
    assumed, so this cannot pass by mutating something the digest ignores.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_sign_in(storage_root)
            _authorise_clear_hold(storage_root, profile_id)
            _assert_content_covered(storage_root, profile_id, _LABEL_RECORD_RELATIVE_PATH)
            lifecycle = ProfileCapsuleLifecycle(root=storage_root)
            journal = lifecycle.prepare_delete(profile_id=profile_id)
            confirmation = lifecycle.confirm_delete(journal)

            label_record = _capsule_of(storage_root, profile_id) / _LABEL_RECORD_RELATIVE_PATH
            label_record.write_bytes(label_record.read_bytes().replace(b"1", b"2", 1))

            with pytest.raises(ProfileCustodyTransactionConflictError):
                lifecycle.delete(confirmation)
            assert recognize_current_profile_capsule(profile_id, root=storage_root) is not None
        finally:
            _close_live_login()


def test_the_marker_still_bites_after_the_deletion_revokes_its_own_session(tmp_path: Path) -> None:
    """Both directions at the one call site that used to break.

    ``_verify_source_delete_marker`` runs before every destructive step after
    the revocation. It is the guard that false-fired, so proving it now passes
    is only half the claim: the same call, on the same journal, with a durable
    custody record altered underneath it, must still refuse. Driving the
    transaction one stage at a time is what puts the assertions on either side of the
    revocation, which no public entry point can do.

    The record it perturbs is confirmed content-covered first, so the refusal
    below cannot be an artefact of touching a member the digest still watches
    by accident.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_sign_in(storage_root)
            _authorise_clear_hold(storage_root, profile_id)
            _assert_content_covered(storage_root, profile_id, _LABEL_RECORD_RELATIVE_PATH)
            capsule = _capsule_of(storage_root, profile_id)
            service = ProfileCustodyTransactionService(root=storage_root)

            journal = service.prepare_delete(profile_id=profile_id)
            journal = service._mark_delete_prepared(journal, _now())
            journal = service._advance_delete_state(
                journal,
                _now(),
                expected=ProfileCustodyTransactionState.DELETE_MARKED,
                next_state=ProfileCustodyTransactionState.PROCESS_SECRETS_REVOKED,
                action=service._revoke_process_secrets,
            )

            assert master_key.current_active_bucket_session() is None
            assert not (capsule / "db/cadrumo.db-wal").exists(), (
                "the revocation must have checkpointed the sidecars away, or the guard is not under test"
            )
            service._verify_source_delete_marker(journal)

            label_record = capsule / _LABEL_RECORD_RELATIVE_PATH
            label_record.write_bytes(label_record.read_bytes().replace(b"1", b"2", 1))

            with pytest.raises(ProfileCustodyTransactionConflictError):
                service._verify_source_delete_marker(journal)
        finally:
            _close_live_login()

"""Destroying a profile takes its session artefacts with it.

Login mints durable, profile-keyed session state that outlives the process:
an encrypted acceleration receipt, its acceleration secret, and the
failed-login backoff. Only ``logout`` and the login-time handover ever
revoked any of it. Nothing reaped on a DESTROY path, so every profile
deleted without an explicit logout left state behind for an identity the
operator believes they retired -- and in the credential store's case, state
that accumulates until the store saturates and every later login on the
machine silently downgrades to process-scoped.

Real adapters throughout: a genuine capsule registered through the production
credential door, the real custody delete transaction, and real files under an
isolated storage root. Nothing is mocked or stubbed.

Scope note. The sibling case
``test_delete_owner_receipts_are_durable_and_idempotent`` in
:mod:`test_custody_transactions` already proves that a REAL minted
acceleration receipt is destroyed by the delete -- but it is marked
``os_keychain``, which every default lane excludes, because minting one
requires a usable credential store. The cases here are the half that needs no
such precondition and therefore runs everywhere: the durable backoff, the
process-secret revocation and its deliberate narrowness, and the owner
receipts that make the whole reap replayable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage import master_key
from ....adapters.persistence.storage.custody import profile_session_path
from ....adapters.persistence.storage.master_key import (
    BucketSession,
    bind_active_bucket_session,
    login_throttle_path,
)
from ....core import capture_pointer
from ....core.time import now as _now
from ....tests.secure_sql import isolated_profile_storage_root
from ...evidence import LegalHoldCaseAuthority
from ...filing import FilingRetentionAuthority
from .._custody_service import _ProfileCustodyTransactionCapability as ProfileCustodyTransactionService
from .._lifecycle import ProfileCapsuleLifecycle
from .._login_session import (
    ProfileCustodySessionOwnerEffect,
    revoke_live_profile_secret_for_custody_delete,
)
from .._profile_record_repository import close_active_profile_record_session
from .._registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "destroy-reaps-session-artefacts-password"  # noqa: S105 - real test credential
_LABEL = "Destroy operator"
_UNRELATED_PROFILE_ID = UUID("2b6d4c19-8e30-4a55-9c71-0d3f8a6e5417")
_INSTANT = datetime(2026, 8, 15, 10, 15, 0, tzinfo=UTC)


def _close_live_login() -> None:
    """Release both process-local authorities without asserting anything."""

    close_active_profile_record_session()
    master_key.close_active_bucket_session()


def _register_with_a_live_process_secret(storage_root: Path) -> tuple[UUID, BucketSession]:
    """Register a real profile and bind a real live bucket session for it.

    Registration commits the capsule but binds no live bucket session, so the
    destroy path would otherwise have no process secret to revoke and the
    ``revoked`` effect would prove nothing.

    The session is opened directly rather than through ``login_profile``
    because a full login also opens the capsule's own SQLite connection, and
    that connection's write-ahead sidecars live inside the capsule directory
    the delete transaction inventories at preflight and re-verifies at execute.
    Binding the session on its own reproduces the state the reap exists for --
    a process holding the target's DEK -- without entangling this proof with
    the inventory's treatment of transient database sidecars.
    """
    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
    )
    profile_id = UUID(outcome.profile_id)
    session = BucketSession.open(
        bucket_id=outcome.profile_id,
        kek=b"k" * 32,
        dek=bytes(range(32)),
        idle_minutes=15,
        absolute_minutes=240,
        opened_at=_INSTANT,
        storage_root=storage_root,
    )
    bind_active_bucket_session(session)
    return profile_id, session


def _authorise_clear_hold(root: Path, profile_id: UUID) -> None:
    """Record the real owner facts a deletion consumes projections of.

    Deletion refuses without them; recording an empty legal-hold snapshot and
    an empty filing catalogue is the genuine "nothing retains this profile"
    state, not a bypass of the check.
    """
    LegalHoldCaseAuthority(root=root).record_open_case_snapshot(
        profile_id=profile_id,
        open_case_ids=(),
        observed_at=_INSTANT,
    )
    FilingRetentionAuthority(root=root).record_filing_catalogue(
        profile_id=profile_id,
        records=(),
        observed_at=_INSTANT,
    )


def _destroy(root: Path, profile_id: UUID) -> None:
    """Run the real prepare / confirm / execute custody deletion."""
    lifecycle = ProfileCapsuleLifecycle(root=root)
    journal = lifecycle.prepare_delete(profile_id=profile_id)
    lifecycle.delete(lifecycle.confirm_delete(journal))


def test_destroying_a_profile_clears_its_durable_failed_login_backoff(tmp_path: Path) -> None:
    """The backoff is profile-keyed durable state, and destruction owns it.

    It lives outside the capsule, so capsule removal alone does not take it.
    Left behind, it charges a freshly created profile that happens to reuse
    the identity for attempts made against a profile that no longer exists,
    and no surface would ever explain the wait.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            outcome = register_profile_with_credentials(
                recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
                label=_LABEL,
                passphrase=_PASSWORD,
            )
            profile_id = UUID(outcome.profile_id)
            _authorise_clear_hold(storage_root, profile_id)
            master_key.record_login_failure(storage_root=storage_root, bucket_id=outcome.profile_id, now=_now())
            throttle_path = login_throttle_path(storage_root=storage_root, bucket_id=outcome.profile_id)
            assert throttle_path.is_file(), "the backoff must exist, or its removal proves nothing"

            _destroy(storage_root, profile_id)

            assert not throttle_path.is_file()
        finally:
            _close_live_login()


def test_destroying_a_profile_revokes_its_live_process_secret_and_clears_the_pointer(
    tmp_path: Path,
) -> None:
    """The in-process DEK binding and the durable selection both go.

    A destroyed profile whose session survives in the running process is a
    live decryption capability for a capsule the operator was told is gone,
    and a pointer still naming it makes the next command select a profile
    that cannot be loaded.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id, live = _register_with_a_live_process_secret(storage_root)
            _authorise_clear_hold(storage_root, profile_id)
            assert live.sealed is False
            assert capture_pointer(storage_root) is not None, (
                "the profile must be the durable selection, or clearing the pointer proves nothing"
            )

            _destroy(storage_root, profile_id)

            assert live.sealed is True
            assert master_key.current_active_bucket_session() is None
            assert capture_pointer(storage_root) is None
        finally:
            _close_live_login()


def test_destroying_a_profile_records_both_session_owner_effects(tmp_path: Path) -> None:
    """The reap is receipted per owner, so an interrupted delete can resume.

    Without a durable receipt the resumed delete cannot tell "already reaped"
    from "never reaped" and either re-runs a side effect or skips one. The
    acceleration owner reports ``verified_absent`` here rather than
    ``removed``: this host laid no receipt down, and reporting the verified
    absence is the honest outcome, not a silent skip.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id, _live = _register_with_a_live_process_secret(storage_root)
            _authorise_clear_hold(storage_root, profile_id)
            service = ProfileCustodyTransactionService(root=storage_root)
            journal = service.prepare_delete(profile_id=profile_id)

            service.execute_delete(service.confirmation_for(journal))

            process_receipt = service._repository.load_owner_receipt(
                journal.transaction_id,
                "process-secret-revocation",
            )
            acceleration_receipt = service._repository.load_owner_receipt(
                journal.transaction_id,
                "local-session-acceleration",
            )
            assert process_receipt is not None
            assert process_receipt.effect == ProfileCustodySessionOwnerEffect.REVOKED.value
            assert acceleration_receipt is not None
            assert acceleration_receipt.effect in {
                ProfileCustodySessionOwnerEffect.REMOVED.value,
                ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT.value,
            }
            assert not profile_session_path(storage_root=storage_root, profile_id=profile_id).exists()
        finally:
            _close_live_login()


def test_the_process_secret_revocation_spares_an_unrelated_live_session(tmp_path: Path) -> None:
    """Deleting one profile must never tear down another's active session.

    This is the narrowness that separates the destroy reap from logout, and
    it is the failure mode with the worst blast radius: an operator working
    in profile A who deletes profile B would otherwise lose A's live DEK
    binding mid-command, with no signal beyond the next operation failing.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        unrelated = BucketSession.open(
            bucket_id=str(_UNRELATED_PROFILE_ID),
            kek=b"k" * 32,
            dek=bytes(range(32)),
            idle_minutes=15,
            absolute_minutes=240,
            opened_at=_INSTANT,
            storage_root=storage_root,
        )
        bind_active_bucket_session(unrelated)
        try:
            target = UUID("9f2c7e51-4a08-4d63-8b12-6ec5a930fd47")

            effect = revoke_live_profile_secret_for_custody_delete(bucket_id=str(target))

            assert effect is ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT
            assert unrelated.sealed is False
            assert master_key.current_active_bucket_session() is unrelated
        finally:
            _close_live_login()

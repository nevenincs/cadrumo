"""Logout strong close: every artefact that could re-open the session is gone.

Real adapters throughout -- a genuine capsule registered through the
production credential door, a real isolated storage root, the real durable
pointer, and the real persisted session acceleration. The proofs that matter
are negative: after logout the on-disk half of the split-knowledge session no
longer exists and a resume can no longer reconstruct the DEK, so neither a
disk-only attacker nor a later process holds anything.

This module is the strong close's dedicated coverage in its owning package.
Between the capsule cutover and here the only assertions of
:func:`logout_active_profile` lived in TUI and CLI test packages, which
exercise the frontend that calls it rather than the teardown it performs.

The keychain half of the split-knowledge pair is deliberately NOT asserted
here. Its public read (``load_profile_session_key``) no longer exists; the
acceleration secret is now addressed by a session id that only the receipt
carries, and reading it back would mean importing a private function of the
storage custody package from an application test. The on-disk half plus the
resume refusal below already decide the security property -- the refusal is
reached before the resume path consults the credential store at all -- so
every case here stays in the default lanes instead of behind ``os_keychain``.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage import master_key
from ....adapters.persistence.storage.custody import profile_session_path
from ....adapters.persistence.storage.master_key import current_active_bucket_session, login_throttle_path
from ....core import ProfileSessionRefusalReason
from ....core.bucket_pointer import read_pointer
from ....core.time import now as _now
from ....tests.secure_sql import isolated_profile_storage_root
from ..login_session import (
    bind_resumed_profile_session,
    login_profile,
    logout_active_profile,
)
from ..profile_record_repository import close_active_profile_record_session
from ..registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "logout-strong-close-password"  # noqa: S105 - real test credential
_LABEL = "Logout operator"


def _close_live_login() -> None:
    """Release both process-local authorities without asserting anything."""

    close_active_profile_record_session()
    master_key.close_active_bucket_session()


def _register_and_login(storage_root: Path) -> str:
    """Register one real profile and leave it authenticated in this process."""
    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
    )
    login_profile(name=outcome.profile_id, passphrase_callback=lambda: _PASSWORD)
    assert master_key.current_active_bucket_session() is not None
    assert read_pointer(storage_root).bucket_id is not None
    return outcome.profile_id


def test_logout_clears_the_live_session_the_pointer_and_the_persisted_acceleration(
    tmp_path: Path,
) -> None:
    """Every artefact logout destroys, and the negative that makes it matter.

    The security-load-bearing claim is the last one: once the durable
    acceleration receipt is gone, ``bind_resumed_profile_session`` can no
    longer reconstruct the DEK and refuses ``ABSENT``. That refusal is
    decided before the resume path reaches the credential store, which is
    why this case needs no keychain precondition.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_login(storage_root)
            session_path = profile_session_path(storage_root=storage_root, profile_id=UUID(profile_id))

            signed_out = logout_active_profile()

            assert signed_out == profile_id
            assert master_key.current_active_bucket_session() is None
            assert not session_path.exists()
            assert read_pointer(storage_root).bucket_id is None
            assert bind_resumed_profile_session(bucket_id=profile_id) is ProfileSessionRefusalReason.ABSENT
            assert master_key.current_active_bucket_session() is None
        finally:
            _close_live_login()


def test_logout_seals_the_live_session_it_evicts(tmp_path: Path) -> None:
    """The evicted session object is sealed, not merely unbound.

    Eviction alone would leave a live key buffer reachable by anything still
    holding the object. The strong close seals it in place, so a retained
    reference is worthless rather than merely orphaned.

    The concrete session is read through the storage facade rather than the
    application port because sealing is a property of the key buffer the
    adapter owns; the port deliberately exposes no such handle.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            _register_and_login(storage_root)
            session = current_active_bucket_session()
            assert session is not None
            assert session.sealed is False

            logout_active_profile()

            assert session.sealed is True
        finally:
            _close_live_login()


def test_logout_clears_the_failed_login_backoff(tmp_path: Path) -> None:
    """A successful sign-out retires the profile's accumulated backoff.

    The backoff is keyed by profile and survives process exit, so leaving it
    behind on a clean logout charges the next operator for attempts that were
    already resolved.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_login(storage_root)
            master_key.record_login_failure(storage_root=storage_root, bucket_id=profile_id, now=_now())
            throttle_path = login_throttle_path(storage_root=storage_root, bucket_id=profile_id)
            assert throttle_path.is_file(), "the backoff must exist, or its removal proves nothing"

            logout_active_profile()

            assert not throttle_path.is_file()
        finally:
            _close_live_login()


def test_second_logout_is_a_clean_no_op(tmp_path: Path) -> None:
    """A repeated sign-out reports nothing to revoke and changes nothing.

    The operator surface is an autonomous agent that retries, so a second
    logout must be a reported no-op rather than a refusal or a second
    teardown pass over artefacts that are already gone.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_login(storage_root)
            session_path = profile_session_path(storage_root=storage_root, profile_id=UUID(profile_id))
            assert logout_active_profile() == profile_id

            assert logout_active_profile() is None

            assert master_key.current_active_bucket_session() is None
            assert read_pointer(storage_root).bucket_id is None
            assert not session_path.exists()
        finally:
            _close_live_login()


def test_logout_without_any_session_is_a_no_op(tmp_path: Path) -> None:
    """Signing out of a storage root that never had a session reports ``None``."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert logout_active_profile() is None
        assert master_key.current_active_bucket_session() is None


def test_login_after_logout_is_a_fresh_authentication_not_a_resume(tmp_path: Path) -> None:
    """The re-login re-authenticates rather than resuming the revoked session.

    Logout cleared the pointer, so the profile must be named again, and the
    acceleration receipt it destroyed is exactly what an idempotent resume
    would have used. ``already_authenticated`` false is therefore the
    assertion that the strong close actually reached the resume path, not
    merely the process binding.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            profile_id = _register_and_login(storage_root)
            first = master_key.current_active_bucket_session()
            assert first is not None
            logout_active_profile()

            outcome = login_profile(name=profile_id, passphrase_callback=lambda: _PASSWORD)

            assert outcome.already_authenticated is False
            assert outcome.bucket_id == profile_id
            assert master_key.current_active_bucket_session() is not first
            assert read_pointer(storage_root).bucket_id is not None
        finally:
            _close_live_login()

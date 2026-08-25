"""Closing the bucket session retires the record authority with it.

The record authority is derived from a live bucket session and then latched
in a process-local context variable. Nothing else re-checks that derivation,
so a bucket session closed by any path other than the strong logout used to
leave the latched authority behind: within one process, "logged out" and
"record authority gone" were different states, and a health check run after
the close still decrypted facts through the survivor.

That also made a shipped cold-profile test read as green while exercising a
profile that was not genuinely locked, which is the more expensive failure --
a locked-profile guarantee proved by a profile that was not locked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    profile_record_session_if_authenticated,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials

from ....adapters.persistence.storage import master_key
from ....domain.user_profile.errors import ProfileNotFoundError
from ....tests.secure_sql import isolated_profile_storage_root

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Record Authority Retirement Subject"
_PASSPHRASE = "record-authority-retires-with-session-operator-secret"  # noqa: S105 - synthetic test credential


def test_closing_the_bucket_session_leaves_no_readable_record_authority(tmp_path: Path) -> None:
    """One close, one state: no session means no authority and no facts."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)

        # Precondition, not decoration: the authority has to be live and
        # latched for its survival to be the thing under test.
        assert profile_record_session_if_authenticated(outcome.profile_id) is not None
        ProfileRecordRepository.for_current_session(outcome.profile_id).load(outcome.profile_id)

        master_key.close_active_bucket_session()

        assert profile_record_session_if_authenticated(outcome.profile_id) is None
        with pytest.raises(ProfileNotFoundError):
            ProfileRecordRepository.for_current_session(outcome.profile_id)


def test_a_sealed_but_still_bound_session_serves_no_record_authority(tmp_path: Path) -> None:
    """Identity alone is not liveness: a closed session still names its bucket.

    A session is sealed in place rather than replaced, so one closed by the
    holder that opened it stays bound, keeps answering with its bucket id, and
    keeps satisfying the substrate's identity-only reuse predicate — while its
    key is already zeroised. Serving a record authority on that basis hands the
    caller a decryptable-looking route over a session that cannot decrypt.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)

        assert profile_record_session_if_authenticated(outcome.profile_id) is not None

        live = master_key.current_active_bucket_session()
        assert live is not None
        # Closed directly, NOT through the eviction door: ownership of a
        # session stays with whoever opened it, so this is a reachable state
        # rather than a contrived one.
        live.close()

        assert live.sealed is True
        assert profile_record_session_if_authenticated(outcome.profile_id) is None
        with pytest.raises(ProfileNotFoundError):
            ProfileRecordRepository.for_current_session(outcome.profile_id)


def test_an_open_bucket_session_still_serves_its_record_authority(tmp_path: Path) -> None:
    """Converse control: the retirement must not fire on a live session.

    Without this, refusing unconditionally would satisfy the sibling test and
    lock every logged-in operator out of their own facts.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)

        first = profile_record_session_if_authenticated(outcome.profile_id)
        second = profile_record_session_if_authenticated(outcome.profile_id)

        assert first is not None
        assert second is not None
        assert ProfileRecordRepository.for_current_session(outcome.profile_id).load(outcome.profile_id) is not None

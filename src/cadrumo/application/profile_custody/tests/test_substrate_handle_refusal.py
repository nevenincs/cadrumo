"""The delegates refuse a custody handle the substrate did not mint.

The record-shaped ports narrow what the application may read from a custody
handle.  A handful of delegates then pass the same object straight back to the
substrate, which requires its own concrete type.  Structural typing alone would
accept any object carrying the right attribute names -- a plain stand-in with a
``bucket_id`` and a ``dek`` satisfies the narrowed port -- and the substrate
would then receive an object it never minted.

The refusal is what makes that impossible, so it is proved here on the real
public delegates rather than on the private helper: a test that reaches past the
delegate proves the helper works without proving the delegate uses it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never
from uuid import uuid4

import pytest

from ....adapters.persistence.storage import StorageValidationError
from ....core import SecureObjectWrite
from ....core.classification import SensitivityClass
from .. import (
    default_profile_bucket_event_history_repository,
    profile_advance_session_idle_deadline,
    profile_bind_bucket_session,
    profile_refuse_unsecured_bucket_with_real_profile,
    profile_session_serves_bucket,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _StandInBucketSession:
    """Satisfies the narrowed session port without being a custody session."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.bucket_id = str(uuid4())
        self.dek = b"\x00" * 32
        self.opened_at = now
        self.idle_deadline = now + timedelta(minutes=5)
        self.absolute_deadline = now + timedelta(minutes=30)
        self.unsecured_backend = False
        self.sealed = False

    def touch(self, now: datetime) -> None:
        self.idle_deadline = now + timedelta(minutes=5)

    def is_expired(self, now: datetime) -> bool:
        return now >= self.absolute_deadline

    def close(self) -> None:
        self.dek = b""
        self.sealed = True


class _StandInPersistedSession:
    """Satisfies the narrowed receipt port without being a custody receipt."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.profile_id = uuid4()
        self.session_id = uuid4()
        self.custody_generation = 1
        self.dek_epoch = "epoch-1"
        self.issued_at = now
        self.idle_deadline = now + timedelta(minutes=5)
        self.absolute_deadline = now + timedelta(minutes=30)


def test_binding_refuses_a_session_the_substrate_did_not_mint() -> None:
    with pytest.raises(TypeError, match="did not originate from the custody substrate"):
        profile_bind_bucket_session(_StandInBucketSession())


def test_serves_bucket_refuses_a_session_the_substrate_did_not_mint() -> None:
    session = _StandInBucketSession()
    with pytest.raises(TypeError, match="did not originate from the custody substrate"):
        profile_session_serves_bucket(session, session.bucket_id)


def test_serves_bucket_still_answers_for_an_absent_session() -> None:
    """The refusal must not swallow the legitimate no-session case."""
    assert profile_session_serves_bucket(None, str(uuid4())) is False


def test_unsecured_refusal_refuses_a_session_the_substrate_did_not_mint() -> None:
    with pytest.raises(TypeError, match="did not originate from the custody substrate"):
        profile_refuse_unsecured_bucket_with_real_profile(_StandInBucketSession())


def test_idle_advance_refuses_a_receipt_the_substrate_did_not_mint(tmp_path: Path) -> None:
    record = _StandInPersistedSession()
    with pytest.raises(TypeError, match="did not originate from the custody substrate"):
        profile_advance_session_idle_deadline(
            storage_root=tmp_path,
            profile_id=record.profile_id,
            record=record,
            new_idle_deadline=record.idle_deadline + timedelta(minutes=5),
        )


def test_event_history_refuses_a_repository_the_substrate_did_not_mint() -> None:
    class _StandInRepository:
        """Satisfies the narrowed repository port without being the real store."""

        def iter_all_records_raw(self) -> Iterator[Never]:
            return iter(())

        def load(
            self,
            namespace: str,
            object_key: str,
            *,
            expected_class: SensitivityClass,
            max_supported_version: int,
        ) -> None:
            return None

        def apply_batch(self, writes: tuple[SecureObjectWrite, ...]) -> None:
            return None

    with pytest.raises(TypeError, match="did not originate from the custody substrate"):
        default_profile_bucket_event_history_repository(objects=_StandInRepository())


def test_event_history_leaves_the_default_composition_path_to_the_substrate() -> None:
    """The refusal must not intercept the absent-repository case.

    Composing without an injected repository sends the substrate to the active
    bucket session, and with none open it raises its own readiness refusal.  A
    guard that fired on ``None`` would replace that instructive refusal with a
    type error, so the assertion is that the substrate's refusal is what
    surfaces.
    """
    with pytest.raises(StorageValidationError) as refusal:
        default_profile_bucket_event_history_repository()
    assert "did not originate from the custody substrate" not in str(refusal.value)

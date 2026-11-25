"""Custody proves its committed capsule without holding its lock, and never commits a proof custody overtook.

Custody runs in this process over a real committed capsule and the real binding
validator. Only the validator's entry is wrapped, to hold one read open while
other threads use custody. The process-wide worker pin is replaced by an
isolated owner, since this test's process outlives the case.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ...profile_persistence_composition import composed_profile_persistence_ports
from ...tests.profile_capsule_runtime import derive_test_bucket_key, publish_test_profile_capsule
from ...tests.secure_sql import isolated_profile_storage_root
from .. import active_session, profile_worker_custody
from ..active_session import current_active_bucket_session
from ..profile_worker_binding import ProfileWorkerBindingOwner
from ..profile_worker_custody import ProfileWorkerCustody
from .capsule_read_support import HELD_READ_WAIT_SECONDS, HeldCapsuleRead, republish_capsule_commit
from .profile_worker_identity_support import published_capsule_identity, worker_lease

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


@dataclass(frozen=True)
class _Subject:
    custody: ProfileWorkerCustody
    lease: AccessSession
    key: bytes
    root: Path


@pytest.fixture
def subject(tmp_path: Path) -> Generator[_Subject]:
    with (
        composed_profile_persistence_ports(),
        isolated_profile_storage_root(tmp_path=tmp_path) as root,
        pytest.MonkeyPatch.context() as patch,
    ):
        isolated = ProfileWorkerBindingOwner()
        patch.setattr(profile_worker_custody, "profile_worker_binding", isolated)
        patch.setattr(active_session, "profile_worker_binding", isolated)
        root.mkdir(parents=True, exist_ok=True)
        profile_id = uuid4()
        publish_test_profile_capsule(profile_id, label="Capsule proof subject", root=root)
        identity = published_capsule_identity(profile_id, root)
        with override_settings(cadrumo_storage_root=root, cadrumo_active_profile=str(profile_id)):
            custody = ProfileWorkerCustody(identity, storage_root=root, monotonic=lambda: 0.0)
            try:
                yield _Subject(
                    custody, worker_lease(identity), derive_test_bucket_key(str(profile_id), purpose="dek"), root
                )
            finally:
                custody.close()


class _Outcome:
    """Run one custody call on its own thread and keep what it returned or raised."""

    def __init__(self, call: Callable[[], object]) -> None:
        self.value: object = None
        self.error: BaseException | None = None
        self._thread = Thread(target=self._run, args=(call,), name="synthetic-custody-caller")
        self._thread.start()

    def _run(self, call: Callable[[], object]) -> None:
        try:
            self.value = call()
        except BaseException as error:
            self.error = error

    def settled(self) -> bool:
        self._thread.join(HELD_READ_WAIT_SECONDS)
        return not self._thread.is_alive()


def test_a_stalled_capsule_read_leaves_the_custody_lock_free(
    subject: _Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    custody, lease = subject.custody, subject.lease
    custody.install(lease, bytearray(subject.key))
    read = HeldCapsuleRead(fail_held=False)
    monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)
    republish_capsule_commit(subject.custody.identity.binding.profile_id, root=subject.root)

    stalled = _Outcome(lambda: custody.require(lease.session_id))
    try:
        assert read.entered.wait(HELD_READ_WAIT_SECONDS)
        # Each of these takes the custody lock; none may wait for the held read.
        idle = _Outcome(lambda: (custody.seconds_until_expiry(), custody.retire(uuid4())))
        assert idle.settled(), "a custody entry waited for a capsule read"
        assert idle.error is None
        assert idle.value == (pytest.approx(900, abs=5), frozenset())
    finally:
        read.release.set()
    assert stalled.settled()
    assert stalled.error is None and stalled.value == lease


def test_a_close_that_overtakes_a_stalled_read_refuses_the_request_it_held(
    subject: _Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    custody, lease = subject.custody, subject.lease
    custody.install(lease, bytearray(subject.key))
    read = HeldCapsuleRead(fail_held=False)
    monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)
    republish_capsule_commit(subject.custody.identity.binding.profile_id, root=subject.root)

    stalled = _Outcome(lambda: custody.require(lease.session_id))
    try:
        assert read.entered.wait(HELD_READ_WAIT_SECONDS)
        closing = _Outcome(custody.close)
        assert closing.settled() and closing.error is None
    finally:
        read.release.set()
    assert stalled.settled()
    # The read itself passed, but the custody it proved no longer exists.
    assert isinstance(stalled.error, AutomationCustodyError)
    assert stalled.error.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    assert current_active_bucket_session() is None


def test_an_install_that_a_close_overtakes_never_binds_its_key(
    subject: _Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    custody, lease = subject.custody, subject.lease
    read = HeldCapsuleRead(fail_held=False)
    monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)

    installing = _Outcome(lambda: custody.install(lease, bytearray(subject.key)))
    try:
        assert read.entered.wait(HELD_READ_WAIT_SECONDS)
        closing = _Outcome(custody.close)
        assert closing.settled() and closing.error is None
    finally:
        read.release.set()
    assert installing.settled()
    assert isinstance(installing.error, AutomationCustodyError)
    assert installing.error.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    assert current_active_bucket_session() is None


def test_a_failed_read_that_a_section_overtook_is_read_again_and_custody_stays_open(
    subject: _Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    custody, lease = subject.custody, subject.lease
    custody.install(lease, bytearray(subject.key))
    read = HeldCapsuleRead(fail_held=True)
    monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)
    republish_capsule_commit(subject.custody.identity.binding.profile_id, root=subject.root)

    expiring = _Outcome(custody.expire)
    try:
        assert read.entered.wait(HELD_READ_WAIT_SECONDS)

        def section_body() -> None:
            with custody.section(lease.session_id):
                pass

        sectioned = _Outcome(section_body)
        assert sectioned.settled() and sectioned.error is None
    finally:
        read.release.set()
    assert expiring.settled()
    # The held read failed, but a section began after it started: it is read again and passes.
    assert expiring.error is None
    assert custody.require(lease.session_id) == lease
    assert current_active_bucket_session() is not None


def test_a_current_failed_read_still_closes_custody(subject: _Subject, monkeypatch: pytest.MonkeyPatch) -> None:
    custody, lease = subject.custody, subject.lease
    custody.install(lease, bytearray(subject.key))
    read = HeldCapsuleRead(fail_held=True)
    read.release.set()
    monkeypatch.setattr(profile_worker_custody, "validate_automation_profile_binding", read)
    republish_capsule_commit(subject.custody.identity.binding.profile_id, root=subject.root)

    with pytest.raises(AutomationCustodyError) as refused:
        custody.expire()

    assert refused.value.reason is AutomationCustodyCode.INVALID
    assert custody.live_sessions() == ()
    assert current_active_bucket_session() is None
    with pytest.raises(AutomationCustodyError) as rejected:
        custody.require(lease.session_id)
    assert rejected.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED


def test_a_key_the_capsule_does_not_open_is_refused_and_binds_nothing(subject: _Subject) -> None:
    custody, lease = subject.custody, subject.lease

    with pytest.raises(AutomationCustodyError) as refused:
        custody.install(lease, bytearray(bytes(len(subject.key))))

    assert refused.value.reason is AutomationCustodyCode.INVALID
    assert current_active_bucket_session() is None
    with pytest.raises(AutomationCustodyError):
        custody.require(lease.session_id)
    custody.install(lease, bytearray(subject.key))
    assert custody.require(lease.session_id) == lease


def test_a_retirement_inside_a_section_releases_material_only_when_the_last_section_closes(
    subject: _Subject,
) -> None:
    custody, lease = subject.custody, subject.lease
    custody.install(lease, bytearray(subject.key))
    outer = custody.section(lease.session_id)
    inner = custody.section(lease.session_id)

    assert custody.retire(lease.session_id) == frozenset({lease.session_id})
    with pytest.raises(ProfileAccessRefusedError) as retired:
        custody.require(lease.session_id)
    assert retired.value.reason is AccessDenialCode.AUTHENTICATION_REQUIRED
    assert custody.retire(lease.session_id) == frozenset()
    material = current_active_bucket_session()
    assert material is not None

    inner.close()
    assert current_active_bucket_session() is material and not material.sealed
    outer.close()
    outer.close()
    assert current_active_bucket_session() is None
    assert material.sealed

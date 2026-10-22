"""Authority checks read held custody facts only while nothing has changed them.

Every runtime round trip asks for the profile lock and enrollment state. The
store answers from its last read until a custody directory reports a change, so
these cases change custody through a second store or through the capsule's own
rotation, which nothing tells the observing store about except the directory.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo_client.contracts.automation_codes import AutomationCustodyError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
    pytest.mark.skipif(sys.platform != "win32", reason="custody observation is held only under Windows notifications"),
]


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[AdministrationSubject]:
    with administration_subject(tmp_path) as subject:
        yield subject


def _observer(subject: AdministrationSubject) -> AutomationControlStore:
    """A second store over the same custody, as another process's would be."""
    return AutomationControlStore(root=subject.store.root, binding=subject.store.binding, secrets_store=subject.native)


def test_an_unchanged_custody_is_answered_without_reading_it_again(
    subject: AdministrationSubject, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = _observer(subject)
    # The first check creates the automation directory, so only the next one can be watched and held.
    observer.observed_access_state()
    first = observer.observed_access_state()
    reads: list[str] = []
    monkeypatch.setattr(observer, "profile_lock_state", lambda: reads.append("lock") or first[0])
    assert [observer.observed_access_state() for _ in range(3)] == [first, first, first]
    assert reads == []


def test_a_lock_published_by_another_store_is_seen_at_the_next_check(subject: AdministrationSubject) -> None:
    observer = _observer(subject)
    lock, _ = observer.observed_access_state()
    assert not lock.globally_locked
    subject.store.deny(
        AutomationDenial(
            request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.PROFILE_LOCK, target_id=None
        )
    )
    lock, _ = observer.observed_access_state()
    assert lock.globally_locked
    assert lock.generation == 1


def test_a_lock_this_store_publishes_is_seen_at_its_next_check(subject: AdministrationSubject) -> None:
    subject.store.observed_access_state()
    subject.store.deny(
        AutomationDenial(
            request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.PROFILE_LOCK, target_id=None
        )
    )
    lock, _ = subject.store.observed_access_state()
    assert lock.globally_locked


def test_a_rotated_password_capsule_refuses_the_old_binding_at_the_next_check(subject: AdministrationSubject) -> None:
    observer = _observer(subject)
    observer.observed_access_state()
    _, decode = profile_authority_contexts()
    replacement = "a-replacement-operator-passphrase"
    with bind_profile_custody_port(build_profile_custody_port(automation_secrets_store=subject.native)):
        rotate_profile_passphrase(
            profile_id=subject.store.binding.profile_id,
            current_passphrase=PROFILE_INPUT,
            new_passphrase=replacement,
            new_passphrase_confirmation=replacement,
            root=subject.store.root,
            profile_decode_context=decode,
        )
    with pytest.raises(AutomationCustodyError) as observed:
        observer.observed_access_state()
    with pytest.raises(AutomationCustodyError) as read:
        observer.profile_lock_state()
    assert observed.value.code is read.value.code


def test_an_observation_that_raises_is_read_again(subject: AdministrationSubject) -> None:
    observer = _observer(subject)
    native = subject.native
    native.unavailable = True
    with pytest.raises(AutomationCustodyError):
        observer.observed_access_state()
    native.unavailable = False
    lock, _ = observer.observed_access_state()
    assert not lock.globally_locked


def test_a_held_observation_carries_no_secret(subject: AdministrationSubject) -> None:
    lock, enrollment = _observer(subject).observed_access_state()
    assert not any(isinstance(value, SecretBytes) for value in (*lock.__dict__.values(), *enrollment.__dict__.values()))

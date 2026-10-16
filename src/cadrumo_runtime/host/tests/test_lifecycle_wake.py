"""A lifecycle pass is called for, not timed, wherever the OS reports what changes the logins."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@dataclass
class _Login:
    lock_state: OsLockState = OsLockState.UNLOCKED
    login_id: str = "synthetic-native-login"
    observations: int = 0

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        self.observations += 1
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id="synthetic-owner",
            active=True,
            lock_state=self.lock_state,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _runtime(tmp_path: Path, login: _Login) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=uuid4(),
        stop=Event(),
        service_descriptors=(),
        login_inventory=lambda: LoginInventory(logins=(cast(LoginEvidence, login),), complete=True),
    )


def test_reported_logins_leave_nothing_due_and_a_request_is_looked_at_one_interval_later(tmp_path: Path) -> None:
    login = _Login()
    profiles = _runtime(tmp_path, login)
    profiles.poll()
    due = profiles.lifecycle_due_in()
    assert due is not None and due <= 0.5, "without session notifications the logins are observed on an interval"
    profiles.session_changes_pushed(True)
    assert profiles.lifecycle_due_in() is None
    observed = login.observations
    profiles.lifecycle_changed()
    assert profiles.lifecycle_wake.is_set()
    profiles.poll()
    assert not profiles.lifecycle_wake.is_set()
    # The wake only decides the wait again; the pass comes an interval on, so a burst costs one.
    assert login.observations == observed
    owed = profiles.lifecycle_due_in()
    assert owed is not None and 0 < owed <= 0.5


def test_an_os_session_change_calls_for_a_pass_at_once(tmp_path: Path) -> None:
    login = _Login()
    profiles = _runtime(tmp_path, login)
    profiles.session_changes_pushed(True)
    profiles.poll()
    observed = login.observations
    profiles.os_session_changed()
    assert profiles.lifecycle_wake.is_set()
    # Asked within the interval of the last pass: owed at the interval's end, not dropped.
    profiles.poll()
    owed = profiles.lifecycle_due_in()
    assert owed is not None and 0 < owed <= 0.5
    profiles._last_poll -= 1.0
    profiles.os_session_changed()
    profiles.poll()
    assert login.observations > observed


@pytest.mark.parametrize("lock_state", [OsLockState.NOT_APPLICABLE, OsLockState.UNKNOWN])
def test_a_login_no_session_notification_reports_is_observed_on_an_interval(
    tmp_path: Path, lock_state: OsLockState
) -> None:
    profiles = _runtime(tmp_path, _Login(lock_state))
    profiles.session_changes_pushed(True)
    profiles.poll()
    due = profiles.lifecycle_due_in()
    assert due is not None and due <= 0.5


class _Host:
    """A profile whose checks all pass, counting how often its next lapse is asked for."""

    def __init__(self, due: float) -> None:
        self.due, self.asked, self.profile_id = due, 0, uuid4()
        self.store = SimpleNamespace(binding=SimpleNamespace(profile_id=self.profile_id))
        self.approvals = SimpleNamespace(expire=lambda: None, retire_sessions=lambda _identities: None)
        self.authority = SimpleNamespace(revalidate_sessions=tuple)
        self.owner = SimpleNamespace(lost=False)

    def retire_replaced_binding(self, *, deadline: float) -> bool:
        return False

    def observe_human_lock_down(self) -> tuple[UUID, ...]:
        return ()

    def lifecycle_due(self) -> float:
        self.asked += 1
        return self.due


def test_the_wait_reads_the_deadlines_the_last_pass_took_and_never_asks_a_profile(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path, _Login())
    profiles.session_changes_pushed(True)
    host = _Host(due=time.monotonic() + 60)
    profiles._profiles[host.profile_id] = cast(RuntimeProfileHost, host)
    profiles.poll()
    assert host.asked == 1
    due = profiles.lifecycle_due_in()
    # A profile's guard can be held through a long private effect; the accept loop must not wait on it.
    assert host.asked == 1
    assert due is not None and 59 < due <= 60

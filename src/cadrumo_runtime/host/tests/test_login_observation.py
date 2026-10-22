"""Authority checks reuse a logon observation only while OS session notifications cover it.

Each runtime round trip checks the person's logon. The connections service
answers those checks from its last observation until Windows reports a session
change, the logons it holds for connections change, or the observation is a
lifecycle interval old, and only while every observed logon has a lock state
those notifications report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.login import LoginInventory
from cadrumo_runtime.host import profile_connections
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@dataclass
class _Logon:
    login_id: str
    lock_state: OsLockState = OsLockState.UNLOCKED
    observed: list[Availability] = field(default_factory=list)

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        self.observed.append(credential_facilities)
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id="synthetic-owner",
            active=True,
            lock_state=self.lock_state,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass
class _Inventory:
    logons: tuple[_Logon, ...]
    taken: int = 0

    def __call__(self) -> LoginInventory:
        self.taken += 1
        return LoginInventory(self.logons, complete=True)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _service(tmp_path: Path, inventory: _Inventory, *, pushed: bool) -> RuntimeProfileConnections:
    service = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=Event(),
        login_inventory=inventory,
        secret_store=MemoryNativePort,
        os_owner_id="synthetic-owner",
    )
    service.session_changes_pushed(pushed)
    return service


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(profile_connections.time, "monotonic", clock)
    return clock


def test_a_notified_logon_is_observed_once_for_every_check_until_the_os_reports_a_change(
    tmp_path: Path, clock: _Clock
) -> None:
    logon = _Logon("desktop")
    inventory = _Inventory((logon,))
    service = _service(tmp_path, inventory, pushed=True)
    service._login_contexts()
    for _ in range(5):
        (held,) = service._observed_login_contexts()
        assert held.observe(credential_facilities=Availability.UNAVAILABLE).login_id == "desktop"
    assert inventory.taken == 1
    assert logon.observed == [Availability.UNAVAILABLE]
    service.os_session_changed()
    service._observed_login_contexts()
    assert inventory.taken == 2


def test_another_credential_availability_is_observed_once_and_then_held(tmp_path: Path, clock: _Clock) -> None:
    logon = _Logon("desktop")
    service = _service(tmp_path, _Inventory((logon,)), pushed=True)
    service._login_contexts()
    for _ in range(3):
        (held,) = service._observed_login_contexts()
        observed = held.observe(credential_facilities=Availability.AVAILABLE)
        assert observed.credential_facilities is Availability.AVAILABLE
    assert logon.observed == [Availability.UNAVAILABLE, Availability.AVAILABLE]


def test_an_observation_a_lifecycle_interval_old_is_taken_again(tmp_path: Path, clock: _Clock) -> None:
    inventory = _Inventory((_Logon("desktop"),))
    service = _service(tmp_path, inventory, pushed=True)
    service._login_contexts()
    clock.now += 0.49
    service._observed_login_contexts()
    assert inventory.taken == 1
    clock.now += 0.01
    service._observed_login_contexts()
    assert inventory.taken == 2


def test_a_logon_without_a_lock_surface_is_held_for_one_lifecycle_interval(tmp_path: Path, clock: _Clock) -> None:
    """A batch or service logon changes only by ending, which the lifecycle pass observes at this interval too."""
    inventory = _Inventory((_Logon("desktop"), _Logon("service", lock_state=OsLockState.NOT_APPLICABLE)))
    service = _service(tmp_path, inventory, pushed=True)
    service._login_contexts()
    for _ in range(3):
        service._observed_login_contexts()
    assert inventory.taken == 1
    clock.now += 0.5
    service._observed_login_contexts()
    assert inventory.taken == 2


@pytest.mark.parametrize(
    ("pushed", "lock_state"),
    [(False, OsLockState.UNLOCKED), (True, OsLockState.UNKNOWN)],
)
def test_a_logon_no_notification_reports_is_observed_at_every_check(
    tmp_path: Path, clock: _Clock, pushed: bool, lock_state: OsLockState
) -> None:
    inventory = _Inventory((_Logon("service", lock_state=lock_state),))
    service = _service(tmp_path, inventory, pushed=pushed)
    service._login_contexts()
    for _ in range(3):
        service._observed_login_contexts()
    assert inventory.taken == 4


def test_a_change_in_the_held_peer_logons_is_observed_again(tmp_path: Path, clock: _Clock) -> None:
    inventory = _Inventory((_Logon("desktop"),))
    service = _service(tmp_path, inventory, pushed=True)
    service._login_contexts()
    service._logins["connection-peer"] = _Logon("connection-peer")
    service._observed_login_contexts()
    assert inventory.taken == 2

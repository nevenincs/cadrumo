"""Invalidation cues reach exactly the connections that asked for them, once per pending change."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo_client.contracts.contracts import ByteChannel, Peer
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor, ServiceLease, VerifiedServicePeer
from cadrumo_client.contracts.session_events import (
    AttendanceChanged,
    ServiceLeaseChanged,
    SessionEvent,
    SignInChanged,
)
from cadrumo_client.contracts.transport import ConnectionContext

from ..profile_connection_services import ServiceConnection
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SCOPE = AccessScope(
    operations=frozenset(),
    actions=frozenset(),
    disclosures=frozenset(),
    periods=None,
    allow_period_independent=True,
    allow_delegation=False,
)


@dataclass
class _Login:
    login_id: str = "synthetic-native-login"
    lock_state: OsLockState = OsLockState.UNLOCKED

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id="synthetic-owner",
            active=True,
            lock_state=self.lock_state,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _runtime(tmp_path: Path, login: _Login | None = None) -> RuntimeProfileConnections:
    native = login or _Login()
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=uuid4(),
        stop=Event(),
        service_descriptors=(),
        login_inventory=lambda: LoginInventory(logins=(cast(LoginEvidence, native),), complete=True),
    )


def _connected(profiles: RuntimeProfileConnections) -> ConnectionContext:
    context = ConnectionContext(uuid4(), profiles.boot, Peer(os_owner_id="synthetic-owner", process_id=1))
    profiles.connect_events(context)
    return context


def _person(profiles: RuntimeProfileConnections, profile_id: UUID) -> ConnectionContext:
    context = _connected(profiles)
    profiles._connections[context.connection_id] = ProfileConnection(
        context=context,
        login=cast(LoginEvidence, _Login()),
        client_id=uuid4(),
        profile_id=profile_id,
        frontend=OperationFrontendProjection.DESKTOP,
        session_id=uuid4(),
    )
    return context


def test_sign_in_watchers_hear_one_cue_per_pending_change_and_nothing_once_gone(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    watcher, bystander = _connected(profiles), _connected(profiles)
    profiles.watch_sign_in(watcher)

    profiles._retired(())
    assert profiles.take_events(watcher) == ()
    profiles._retired((uuid4(),))
    profiles._retired((uuid4(),))
    (cue,) = profiles.take_events(watcher)
    assert cue == SignInChanged(runtime_boot_id=profiles.boot, connection_id=watcher.connection_id)
    assert profiles.take_events(bystander) == ()

    # Once taken, a later change queues a fresh cue.
    profiles._retired((uuid4(),))
    assert profiles.take_events(watcher) == (cue,)

    profiles.disconnect(watcher)
    assert watcher.connection_id not in profiles._sign_in_watchers
    profiles._retired((uuid4(),))
    assert profiles.take_events(bystander) == ()


def test_os_lock_changes_cue_watchers_and_unchanged_logins_do_not(tmp_path: Path) -> None:
    native = _Login()
    profiles = _runtime(tmp_path, native)
    watcher = _connected(profiles)
    profiles.watch_sign_in(watcher)
    profiles._login_contexts()
    assert len(profiles.take_events(watcher)) == 1, "the first observation establishes what later ones compare to"
    profiles._login_contexts()
    assert profiles.take_events(watcher) == ()
    native.lock_state = OsLockState.LOCKED
    profiles._login_contexts()
    (cue,) = profiles.take_events(watcher)
    assert isinstance(cue, SignInChanged)


def test_a_disconnected_held_sign_in_cues_watchers(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    watcher = _connected(profiles)
    profiles.watch_sign_in(watcher)
    holder = _person(profiles, uuid4())
    profiles.disconnect(holder)
    (cue,) = profiles.take_events(watcher)
    assert isinstance(cue, SignInChanged)


def test_retiring_the_parent_session_withdraws_the_service_lease_and_cues_only_that_service(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id, parent_session = uuid4(), uuid4()
    holder = _person(profiles, profile_id)
    service, unrelated = _connected(profiles), _connected(profiles)
    descriptor = InstalledServiceDescriptor(
        service_id="synthetic-service",
        launch_image="synthetic.exe",
        launch_module="synthetic.service",
        image_digest="1" * 64,
        descriptor_digest="2" * 64,
        record_capabilities=(),
        operation_scope=_SCOPE,
    )
    peer = VerifiedServicePeer(
        "synthetic-service",
        "2" * 64,
        7,
        "1",
        "synthetic.exe",
        "1" * 64,
        service.connection_id,
        profiles.boot,
        "0:0:0:0",
    )
    lease = ServiceLease(
        lease_id=uuid4(),
        session_id=uuid4(),
        profile_id=profile_id,
        parent_session_id=parent_session,
        descriptor_digest="2" * 64,
        service_id="synthetic-service",
        runtime_boot_id=profiles.boot,
        connection_id=service.connection_id,
    )
    profiles._services[service.connection_id] = ServiceConnection(descriptor, peer, cast(ByteChannel, object()), lease)
    retirement = SessionEvent(
        runtime_boot_id=profiles.boot,
        connection_id=holder.connection_id,
        profile_id=profile_id,
        session_id=parent_session,
        event=SessionRetirementKind.SIGNED_OUT,
        reason=AccessDenialCode.AUTHENTICATION_REQUIRED,
    )

    profiles._publish_retirement(retirement)

    assert profiles._services[service.connection_id].lease is None
    assert profiles.take_events(holder) == (retirement,)
    assert profiles.take_events(service) == (
        ServiceLeaseChanged(runtime_boot_id=profiles.boot, connection_id=service.connection_id, profile_id=profile_id),
    )
    assert profiles.take_events(unrelated) == ()


def test_attendance_cues_reach_only_the_profiles_current_holders(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    holder, stale, other_profile = (
        _person(profiles, profile_id),
        _person(profiles, profile_id),
        _person(profiles, uuid4()),
    )
    holder_session = profiles._connections[holder.connection_id].session_id
    assert holder_session is not None
    profiles._attendance_holders[holder.connection_id] = holder_session
    # A holder whose session has since changed no longer decides for this person.
    profiles._attendance_holders[stale.connection_id] = uuid4()
    other_session = profiles._connections[other_profile.connection_id].session_id
    assert other_session is not None
    profiles._attendance_holders[other_profile.connection_id] = other_session

    profiles._attendance_changed(profile_id)
    profiles._attendance_changed(profile_id)

    assert profiles.take_events(holder) == (
        AttendanceChanged(
            runtime_boot_id=profiles.boot,
            connection_id=holder.connection_id,
            profile_id=profile_id,
            session_id=holder_session,
        ),
    )
    assert profiles.take_events(stale) == ()
    assert profiles.take_events(other_profile) == ()

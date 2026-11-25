"""Invalidation cues reach exactly the connections that asked for them, once per pending change."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.user_profile.access_contracts import (
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.core.operations import OperationFrontendProjection, OperationLifecycle
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessScope, Availability
from cadrumo_client.contracts.contracts import ByteChannel, Peer
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory
from cadrumo_client.contracts.operation_access import OperationObserve, OperationObserved
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor, ServiceLease, VerifiedServicePeer
from cadrumo_client.contracts.session_events import (
    AttendanceChanged,
    OperationChanged,
    ProfileRecordsChanged,
    ServiceLeaseChanged,
    SessionEvent,
    SignInChanged,
)
from cadrumo_client.contracts.transport import ConnectionContext

from ..profile_connection import ProfileConnection
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost
from ..service_connection_records import ServiceConnection

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


def _ended(profiles: RuntimeProfileConnections) -> SessionEvent:
    return SessionEvent(
        runtime_boot_id=profiles.boot,
        connection_id=uuid4(),
        profile_id=uuid4(),
        session_id=uuid4(),
        event=SessionRetirementKind.REVOKED,
        reason=AccessDenialCode.SESSION_INACTIVE,
    )


def test_sign_in_watchers_hear_one_cue_per_pending_change_and_nothing_once_gone(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    watcher, bystander = _connected(profiles), _connected(profiles)
    profiles.watch_sign_in(watcher)

    profiles._publish_retirement(_ended(profiles), SessionKind.HUMAN)
    profiles._publish_retirement(_ended(profiles), SessionKind.HUMAN)
    (cue,) = profiles.take_events(watcher)
    assert cue == SignInChanged(runtime_boot_id=profiles.boot, connection_id=watcher.connection_id)
    assert profiles.take_events(bystander) == ()

    # Once taken, a later change queues a fresh cue.
    profiles._publish_retirement(_ended(profiles), SessionKind.HUMAN)
    assert profiles.take_events(watcher) == (cue,)

    profiles.disconnect(watcher)
    assert watcher.connection_id not in profiles._sign_in_watchers
    profiles._publish_retirement(_ended(profiles), SessionKind.HUMAN)
    assert profiles.take_events(bystander) == ()


@pytest.mark.parametrize("kind", [SessionKind.ATTENDED, SessionKind.API_KEY])
def test_a_delegated_lease_ending_leaves_sign_in_watchers_alone(tmp_path: Path, kind: SessionKind) -> None:
    # A service's attended lease is retired and renewed on a short cycle; the
    # person's sign-in did not move, so no watcher is sent to read it again.
    profiles = _runtime(tmp_path)
    watcher = _connected(profiles)
    profiles.watch_sign_in(watcher)

    profiles._publish_retirement(_ended(profiles), kind)
    profiles._retired((uuid4(),))
    assert profiles.take_events(watcher) == ()

    # ANTI-VACUITY: the same watcher hears a person's lease ending.
    profiles._publish_retirement(_ended(profiles), SessionKind.HUMAN)
    (cue,) = profiles.take_events(watcher)
    assert isinstance(cue, SignInChanged)


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

    profiles._publish_retirement(retirement, SessionKind.HUMAN)

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


def _observe(
    profiles: RuntimeProfileConnections, context: ConnectionContext, operation_id: str, lifecycle: OperationLifecycle
) -> None:
    """Record what one OperationObserve reply showed this connection, as the request handler does."""
    connection = profiles._connections[context.connection_id]
    assert connection.session_id is not None
    request = OperationObserve(
        request_id=uuid4(),
        profile_id=connection.profile_id,
        session_id=connection.session_id,
        observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
    )
    # Only the lifecycle decides the watch; the rest of the projection is not read.
    observation = OperationObservationSuccessV1.model_construct(
        projection=OperationPublicProjectionV1.model_construct(lifecycle=lifecycle)
    )
    profiles._watch_observed_operation(connection, request, OperationObserved.model_construct(observation=observation))


def test_operation_cues_reach_only_connections_still_observing_a_reported_operation(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    operation, unrelated = "a" * 64, "b" * 64
    watcher, idle, finished, foreign = (
        _person(profiles, profile_id),
        _person(profiles, profile_id),
        _person(profiles, profile_id),
        _person(profiles, uuid4()),
    )
    _observe(profiles, watcher, operation, OperationLifecycle.RUNNING)
    _observe(profiles, finished, operation, OperationLifecycle.RUNNING)
    _observe(profiles, finished, operation, OperationLifecycle.TERMINAL)
    # Another profile's connection observing the same id is never cued by this profile's worker.
    _observe(profiles, foreign, operation, OperationLifecycle.RUNNING)

    profiles._operations_advanced(profile_id, (unrelated,))
    assert profiles.take_events(watcher) == ()
    profiles._operations_advanced(profile_id, (operation,))
    profiles._operations_advanced(profile_id, (operation, unrelated))

    session_id = profiles._connections[watcher.connection_id].session_id
    assert session_id is not None
    assert profiles.take_events(watcher) == (
        OperationChanged(
            runtime_boot_id=profiles.boot,
            connection_id=watcher.connection_id,
            profile_id=profile_id,
            session_id=session_id,
        ),
    )
    assert profiles.take_events(idle) == ()
    assert profiles.take_events(finished) == ()
    assert profiles.take_events(foreign) == ()

    profiles.disconnect(watcher)
    profiles._operations_advanced(profile_id, (operation,))
    assert watcher.connection_id not in profiles._operation_watches


@pytest.mark.parametrize("advanced_after_watch", [False, True])
def test_observation_covers_a_terminal_commit_on_either_side_of_watch_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, advanced_after_watch: bool
) -> None:
    profiles = _runtime(tmp_path)
    profile_id, operation_id = uuid4(), "a" * 64
    context = _person(profiles, profile_id)
    connection = profiles._connections[context.connection_id]
    assert connection.session_id is not None
    request = OperationObserve(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=connection.session_id,
        observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
    )
    held = False
    reads = 0

    @contextmanager
    def authorized_output() -> Generator[None]:
        nonlocal held
        assert not held, "worker callbacks must not run under an earlier output fence"
        held = True
        try:
            yield
        finally:
            held = False

    def worker_reply(*_args: object, release_guard: ExitStack) -> tuple[OperationObserved, datetime | None]:
        nonlocal reads
        assert not held, "each worker snapshot needs callbacks on the profile guard"
        reads += 1
        lifecycle = (
            OperationLifecycle.TERMINAL if reads == 2 and not advanced_after_watch else OperationLifecycle.RUNNING
        )
        snapshot = OperationObservationSuccessV1.model_construct(
            projection=OperationPublicProjectionV1.model_construct(lifecycle=lifecycle)
        )
        # Reproduce the production race: the worker has captured RUNNING,
        # then its final committed progress reaches the parent before the
        # authorized snapshot has installed its watch. No later cue arrives.
        if reads == (2 if advanced_after_watch else 1):
            profiles._operations_advanced(profile_id, (operation_id,))
        release_guard.enter_context(authorized_output())
        return OperationObserved.model_construct(observation=snapshot), None

    monkeypatch.setattr(profiles, "_operation_reply", worker_reply)
    with ExitStack() as guard:
        result, _expires = profiles._observe_and_watch_operation(
            connection,
            cast(RuntimeProfileHost, object()),
            context,
            cast(ByteChannel, object()),
            request,
            release_guard=guard,
        )
        assert held, "the final snapshot retains its output fence through disclosure"
        assert isinstance(result, OperationObserved)
        assert isinstance(result.observation, OperationObservationSuccessV1)
        assert result.observation.projection.lifecycle is (
            OperationLifecycle.RUNNING if advanced_after_watch else OperationLifecycle.TERMINAL
        )
    assert reads == 2
    assert not held
    if advanced_after_watch:
        assert profiles._operation_watches[context.connection_id] == {operation_id: connection.session_id}
    else:
        assert context.connection_id not in profiles._operation_watches
    assert len(profiles.take_events(context)) == int(advanced_after_watch)


@pytest.mark.parametrize("refuse_read", [1, 2])
def test_refused_observation_never_installs_a_watch_and_a_refused_reread_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refuse_read: int
) -> None:
    profiles = _runtime(tmp_path)
    profile_id, operation_id = uuid4(), "a" * 64
    context = _person(profiles, profile_id)
    connection = profiles._connections[context.connection_id]
    assert connection.session_id is not None
    request = OperationObserve(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=connection.session_id,
        observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
    )
    reads = 0

    def worker_reply(*_args: object, release_guard: ExitStack) -> tuple[OperationObserved, datetime | None]:
        nonlocal reads
        reads += 1
        if reads == refuse_read:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        snapshot = OperationObservationSuccessV1.model_construct(
            projection=OperationPublicProjectionV1.model_construct(lifecycle=OperationLifecycle.RUNNING)
        )
        return OperationObserved.model_construct(observation=snapshot), None

    monkeypatch.setattr(profiles, "_operation_reply", worker_reply)
    with ExitStack() as guard, pytest.raises(ProfileAccessRefusedError):
        profiles._observe_and_watch_operation(
            connection,
            cast(RuntimeProfileHost, object()),
            context,
            cast(ByteChannel, object()),
            request,
            release_guard=guard,
        )
    profiles._operations_advanced(profile_id, (operation_id,))
    assert context.connection_id not in profiles._operation_watches
    assert profiles.take_events(context) == ()


def test_record_effect_cues_other_editors_once_without_values_or_operation_watches(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    editor, foreign, retired = _person(profiles, profile_id), _person(profiles, uuid4()), _person(profiles, profile_id)
    profiles._connections[retired.connection_id].session_id = None
    profiles._operations_advanced(profile_id, ("a" * 64,))
    assert profiles.take_events(editor) == ()
    for _ in range(100):
        profiles._operations_advanced(profile_id, ("b" * 64,), records_changed=True)
    (cue,) = profiles.take_events(editor)
    assert isinstance(cue, ProfileRecordsChanged)
    assert cue.profile_id == profile_id
    assert set(cue.model_dump()) == {"kind", "runtime_boot_id", "connection_id", "profile_id", "session_id"}
    assert profiles.take_events(foreign) == ()
    assert profiles.take_events(retired) == ()

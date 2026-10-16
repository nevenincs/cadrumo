"""Per-connection event overflow closes only that stream without delaying retirement, and queuing wakes its writer."""

from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo_client.contracts.contracts import Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.session_events import SessionEvent, SignInChanged
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.native_wake import NativeWake

from ..session_events import SESSION_EVENT_QUEUE_LIMIT, RuntimeSessionEvents

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_event_overflow_refuses_only_affected_connection() -> None:
    boot = uuid4()
    peer = Peer(os_owner_id="synthetic-owner", process_id=1)
    affected = ConnectionContext(uuid4(), boot, peer)
    other = ConnectionContext(uuid4(), boot, peer)
    events = RuntimeSessionEvents()
    events.connect(affected)
    events.connect(other)
    notice = SessionEvent(
        runtime_boot_id=boot,
        connection_id=affected.connection_id,
        profile_id=uuid4(),
        session_id=uuid4(),
        event=SessionRetirementKind.SIGNED_OUT,
        reason=AccessDenialCode.AUTHENTICATION_REQUIRED,
    )
    for _ in range(SESSION_EVENT_QUEUE_LIMIT + 1):
        events.publish(notice)
    with pytest.raises(RefusalError) as closed:
        events.take(affected)
    assert closed.value.reason is RefusalCode.CONNECTION_CLOSED
    assert events.take(other) == ()
    events.disconnect(affected)
    events.publish(notice)
    assert events.take(other) == ()


def test_event_batch_is_ordered_and_consumed_once() -> None:
    context = ConnectionContext(uuid4(), uuid4(), Peer(os_owner_id="synthetic-owner", process_id=1))
    events = RuntimeSessionEvents()
    events.connect(context)
    notices = tuple(
        SessionEvent(
            runtime_boot_id=context.runtime_boot_id,
            connection_id=context.connection_id,
            profile_id=uuid4(),
            session_id=uuid4(),
            event=SessionRetirementKind.REVOKED,
            reason=AccessDenialCode.SESSION_EXPIRED,
        )
        for _ in range(3)
    )
    for notice in notices:
        events.publish(notice)
    assert events.take(context) == notices
    assert events.take(context) == ()


def test_a_queued_event_wakes_only_its_own_writer_and_an_overflow_wakes_it_to_close() -> None:
    boot = uuid4()
    peer = Peer(os_owner_id="synthetic-owner", process_id=1)
    context, other = ConnectionContext(uuid4(), boot, peer), ConnectionContext(uuid4(), boot, peer)
    queued, idle = NativeWake(), NativeWake()
    events = RuntimeSessionEvents()
    events.connect(context, queued)
    events.connect(other, idle)
    cue = SignInChanged(runtime_boot_id=boot, connection_id=context.connection_id)
    events.publish_cue(cue)
    assert queued.is_set() and not idle.is_set()
    queued.clear()
    # A cue already waiting answers the next change too: nothing new is queued or woken.
    events.publish_cue(cue)
    assert not queued.is_set()
    assert events.take(context) == (cue,)
    notice = SessionEvent(
        runtime_boot_id=boot,
        connection_id=context.connection_id,
        profile_id=uuid4(),
        session_id=uuid4(),
        event=SessionRetirementKind.SIGNED_OUT,
        reason=AccessDenialCode.AUTHENTICATION_REQUIRED,
    )
    for _ in range(SESSION_EVENT_QUEUE_LIMIT):
        events.publish(notice)
    queued.clear()
    events.publish(notice)
    assert queued.is_set(), "the writer must wake to find its stream closed"
    with pytest.raises(RefusalError):
        events.take(context)
    assert not idle.is_set()

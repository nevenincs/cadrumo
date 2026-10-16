"""Nonsecret language invalidation follows exact connection/profile/session scope."""

from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.bucket.output_language_hint import write_bucket_output_language_hint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.contracts import Peer
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.session_events import ProfileLanguageChanged
from cadrumo_client.contracts.transport import ConnectionContext

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_committed_hint_invalidates_only_its_profile_and_live_session(tmp_path: Path) -> None:
    """Real sidecar publication is presentation invalidation, never admission evidence."""
    boot = uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=boot,
        stop=Event(),
        service_descriptors=(),
    )
    first, other, stranger = (
        ConnectionContext(uuid4(), boot, Peer(os_owner_id="fixture", process_id=1)) for _ in range(3)
    )
    for context in (first, other, stranger):
        profiles.connect_events(context)
    for context in (first, other):
        profiles._connections[context.connection_id] = ProfileConnection(
            context=context,
            login=cast(LoginEvidence, object()),
            client_id=uuid4(),
            profile_id=uuid4(),
            frontend=OperationFrontendProjection.TUI,
            session_id=uuid4(),
        )
    connection = profiles._connections[first.connection_id]
    other_profile = profiles._connections[other.connection_id].profile_id

    # Operation traffic is the only moment the hint can move; the first look gives each session a baseline.
    profiles.observe_profile_language(connection.profile_id)
    assert len(profiles.take_events(first)) == 1
    assert profiles.take_events(other) == ()
    assert profiles.take_events(stranger) == ()
    profiles.observe_profile_language(connection.profile_id)
    assert profiles.take_events(first) == ()

    write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=str(connection.profile_id), language="hu")
    # An idle connection's turns never read the hint: nothing moves without operation traffic.
    assert profiles.take_events(first) == ()
    profiles.observe_profile_language(other_profile)
    assert profiles.take_events(first) == () and len(profiles.take_events(other)) == 1

    profiles.observe_profile_language(connection.profile_id)
    (event,) = profiles.take_events(first)
    assert isinstance(event, ProfileLanguageChanged)
    assert (event.profile_id, event.session_id, event.connection_id) == (
        connection.profile_id,
        connection.session_id,
        first.connection_id,
    )
    assert profiles.take_events(other) == ()
    assert profiles.take_events(stranger) == ()
    profiles.observe_profile_language(connection.profile_id)
    assert profiles.take_events(first) == ()

    connection.session_id = None
    write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=str(connection.profile_id), language="ca")
    profiles.observe_profile_language(connection.profile_id)
    assert profiles.take_events(first) == ()

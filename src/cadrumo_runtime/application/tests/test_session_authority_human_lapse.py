"""A person's lease that lapses with an attended child retires both, and nothing revives it without the person."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessSession, SessionKind
from cadrumo_client.contracts.access_refusals import AccessDenied
from cadrumo_client.contracts.access_vocabulary import Availability

from .session_authority_support import Subject

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


def test_a_lapsed_person_lease_retires_with_its_attended_child_and_is_not_revived(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    service = uuid4()
    subject.owner.connections[service] = api.client_id
    child = subject.authority.attend(
        connection_id=subject.connection,
        parent_session_id=human.session_id,
        recipient_connection_id=service,
        scope=human.scope,
    )
    assert isinstance(child, AccessSession) and child.kind is SessionKind.ATTENDED
    lifetime = (human.expires_at - human.issued_at).total_seconds()
    subject.advance(lifetime + 1)

    retired = set(subject.authority.revalidate_sessions())
    assert {human.session_id, child.session_id} <= retired

    activity = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=timedelta(minutes=15)
    )
    assert isinstance(activity, AccessDenied)
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=human.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, AccessDenied) or status.session_id is None

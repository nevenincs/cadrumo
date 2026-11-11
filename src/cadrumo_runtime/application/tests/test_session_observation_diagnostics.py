"""Unavailable-session diagnostics preserve admission and protect identifying data."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import changed
from cadrumo.application.user_profile.access_contracts import AccessSession, LoginEligibility, OsLockState
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied

from .. import session_authority_core, session_login_observation
from ..session_authority_contracts import SessionAuthorityFacts
from .session_authority_support import Subject

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize(
    "observation,reason",
    [
        ("private_work", "private_work_unavailable"),
        ("absent", "originating_login_absent"),
        ("inactive", "originating_login_inactive"),
        ("unknown", "originating_lock_unknown"),
    ],
)
def test_unavailable_observation_reason_classifies_current_facts(
    observation: str, reason: str, subject: Subject
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    context = subject.owner.current.context
    if observation == "private_work":
        context = changed(context, private_work_available=False)
    elif observation == "absent":
        context = changed(context, login_contexts=())
    else:
        login = context.login_contexts[0]
        login = (
            changed(login, active=False)
            if observation == "inactive"
            else changed(login, lock_state=OsLockState.UNKNOWN, unattended=LoginEligibility.UNKNOWN)
        )
        context = changed(context, login_contexts=(login,))
    facts = SessionAuthorityFacts(subject.owner.current.profile, context)
    assert session_login_observation.unavailable_observation_reason(human, facts) == reason


def test_unknown_observation_emits_only_safe_reason_and_does_not_retire(
    subject: Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    context = subject.owner.current.context
    login = changed(context.login_contexts[0], lock_state=OsLockState.UNKNOWN, unattended=LoginEligibility.UNKNOWN)
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile, changed(context, login_contexts=(login,))
    )
    events: list[tuple[str, dict[str, Any], int]] = []

    def record(_logger: object, event: str, *, fields: dict[str, Any], level: int) -> None:
        events.append((event, fields, level))

    monkeypatch.setattr(session_authority_core, "diagnostic_event", record)
    result = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.OS_SESSION_UNAVAILABLE
    assert events and all(
        event == "runtime_session_observation_unavailable"
        and fields == {"reason_code": "originating_lock_unknown"}
        and level == logging.DEBUG
        for event, fields, level in events
    )
    assert human.session_id in subject.owner.active
    assert not subject.owner.retired
    assert not subject.owner.refreshed

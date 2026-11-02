"""A key or grant denial must name something the profile holds."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ._session_authority_support import Subject, lifecycle

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


def _human(subject: Subject) -> AccessSession:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    return human


@pytest.mark.parametrize("kind", [AutomationDenialKind.GRANT, AutomationDenialKind.KEY])
def test_denying_an_unknown_target_is_refused_as_missing_and_changes_nothing(
    subject: Subject, kind: AutomationDenialKind
) -> None:
    human = _human(subject)
    before = subject.store.enrollment_state()

    with pytest.raises(AutomationCustodyError) as refused:
        lifecycle(subject, human).deny(
            AutomationDenial(request_id=uuid4(), binding=human.binding, kind=kind, target_id=uuid4())
        )

    assert refused.value.reason is AutomationCustodyCode.MISSING
    assert subject.store.enrollment_state() == before


def test_denying_a_held_grant_and_a_held_key_still_revokes_them(subject: Subject) -> None:
    human = _human(subject)
    service = lifecycle(subject, human)
    entry = subject.store.enrollment_state().grants[0]

    key_receipt = service.deny(
        AutomationDenial(
            request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.KEY, target_id=entry.keys[0].key.key_id
        )
    )
    grant_receipt = service.deny(
        AutomationDenial(
            request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.GRANT, target_id=entry.grant.grant_id
        )
    )

    assert key_receipt.access_denied and grant_receipt.access_denied
    revoked = subject.store.enrollment_state().grants[0]
    assert revoked.grant.state is AuthorityState.REVOKED
    assert revoked.keys[0].key.state is AuthorityState.REVOKED

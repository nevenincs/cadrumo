"""The enrollment proposal the automation request and decision tests submit."""

from __future__ import annotations

from datetime import timedelta

from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind, EnrollmentProposal


def enrollment_proposal() -> EnrollmentProposal:
    """Propose a thirty-day enrollment to submit, start and commit profile field mutations unattended."""
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=now() + timedelta(days=30),
        key_expires_at=now() + timedelta(days=15),
        unattended=True,
        allow_os_lock=False,
    )

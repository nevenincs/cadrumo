"""Build the lifecycle probe's first-enrollment proposal for an agent key.

The probe's requester runs inside the packaged interpreter, which loads this
file by path. It therefore imports only modules the package ships.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationPublicContractSetV1
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosureCategoryGrant,
)
from cadrumo_client.contracts.enrollment_proposal import GRANT_DEFAULT_VALIDITY, EnrollmentKind, EnrollmentProposal

AGENT_KEY_CATEGORIES: frozenset[DisclosureCategory] = frozenset(
    {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA}
)
"""The probe's agent operates the profile and observes its own operations."""


def agent_key_operations(contracts: OperationPublicContractSetV1) -> frozenset[str]:
    """Return every registered operation an agent may run: all but the person's own acts."""
    return frozenset(
        contract.definition_id
        for contract in contracts.definitions
        if not operation_is_persons_act(
            contract.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required
        )
    )


def agent_key_proposal(
    contracts: OperationPublicContractSetV1, *, destination_id: UUID, now: datetime
) -> EnrollmentProposal:
    """Propose the first enrollment of an agent key, bound to the runtime-minted destination.

    API-key admission needs an unattended grant, which the person approves on
    the protected channel; it never continues while the OS is locked. The grant
    and its key run for the default validity.
    """
    expires_at = now + GRANT_DEFAULT_VALIDITY
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=AccessScope(
            operations=agent_key_operations(contracts),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
            disclosure_categories=frozenset(
                DisclosureCategoryGrant(destination_id=destination_id, category=category)
                for category in AGENT_KEY_CATEGORIES
            ),
        ),
        expires_at=expires_at,
        key_expires_at=expires_at,
        unattended=True,
        allow_os_lock=False,
    )

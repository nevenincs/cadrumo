"""The lifecycle probe's agent key grants its data categories to the runtime-minted destination."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationPublicContractSetV1
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo_client.contracts.access_vocabulary import AccessAction, DisclosureCategory, DisclosureCategoryGrant
from cadrumo_client.contracts.enrollment_proposal import GRANT_DEFAULT_VALIDITY, EnrollmentKind

from .. import agent_key_proposal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VIEW = "user-profile.view"


@pytest.fixture(scope="module")
def contracts() -> OperationPublicContractSetV1:
    """The real profile operation contracts, without unrelated live families."""
    definitions = build_user_profile_operation_definitions()
    return OperationPublicContractSetV1.build(
        tuple(item.contract for item in build_user_profile_operation_registrations(definitions))
    )


def test_an_agent_may_run_every_registered_operation_but_the_persons_own_acts(
    contracts: OperationPublicContractSetV1,
) -> None:
    runnable = agent_key_proposal.agent_key_operations(contracts)

    assert _VIEW in runnable
    assert "user-profile.patch" in runnable
    assert "user-profile.automation-approve" not in runnable
    assert "user-profile.automation-inventory" not in runnable
    assert not any(
        str(item.definition_id) in runnable for item in contracts.definitions if item.ephemeral_secret_required
    )


def test_the_proposal_grants_every_agent_operation_and_each_category_to_the_minted_destination(
    contracts: OperationPublicContractSetV1,
) -> None:
    destination = uuid4()
    issued = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    proposal = agent_key_proposal.agent_key_proposal(contracts, destination_id=destination, now=issued)

    assert proposal.kind is EnrollmentKind.ENROLL
    assert proposal.target_grant_id is None and proposal.target_key_id is None
    assert _VIEW in proposal.scope.operations
    assert "user-profile.patch" in proposal.scope.operations
    assert "user-profile.automation-approve" not in proposal.scope.operations
    assert "anything.registered-later" not in proposal.scope.operations
    assert proposal.scope.actions == frozenset(AccessAction)
    assert proposal.scope.disclosures == frozenset()
    assert proposal.scope.disclosure_categories == {
        DisclosureCategoryGrant(destination_id=destination, category=DisclosureCategory.PROFILE_VALUES),
        DisclosureCategoryGrant(destination_id=destination, category=DisclosureCategory.OPERATION_METADATA),
    }
    assert proposal.scope.periods is None
    assert proposal.scope.allow_period_independent is True
    assert proposal.scope.allow_delegation is False
    # A key is admitted with nobody signed in only on an unattended grant; it never runs while the OS is locked.
    assert proposal.unattended is True
    assert proposal.allow_os_lock is False
    assert proposal.expires_at == issued + GRANT_DEFAULT_VALIDITY
    assert proposal.key_expires_at == proposal.expires_at


def test_the_packaged_requester_loads_the_builder_by_path_alone(contracts: OperationPublicContractSetV1) -> None:
    """The requester runs outside the dev tree, so the file must load without its package."""
    spec = importlib.util.spec_from_file_location("lifecycle_agent_key_proposal", Path(agent_key_proposal.__file__))
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    destination = uuid4()
    issued = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    loaded = builder.agent_key_proposal(contracts, destination_id=destination, now=issued)

    assert loaded == agent_key_proposal.agent_key_proposal(contracts, destination_id=destination, now=issued)

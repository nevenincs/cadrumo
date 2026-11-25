"""Lease expiry is authority timing: it follows real time, never a fixed clock."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo.core.time.clock import frozen_clock, wall_now
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorizationPermit, WorkerAuthorizationRequest

from ..worker_authorization_lease import _validated_authority_permit

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DEFINITION_ID = "user-profile.field-mutation"


def _identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


def _request(identity: ProfileWorkerIdentity) -> WorkerAuthorizationRequest:
    return WorkerAuthorizationRequest(
        request_id=uuid4(),
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        request=OperationAccessRequest(
            profile_id=identity.binding.profile_id,
            definition_id=_DEFINITION_ID,
            action=AccessAction.COMMIT,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=_DEFINITION_ID,
            definition_contract_digest="b" * 64,
            actions=frozenset({AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def _permit(
    request: WorkerAuthorizationRequest, identity: ProfileWorkerIdentity, expires_at: datetime
) -> WorkerAuthorizationPermit:
    return WorkerAuthorizationPermit(
        request_id=request.request_id,
        runtime_boot_id=identity.runtime_boot_id,
        permit_id=uuid4(),
        expires_at=expires_at,
    )


def test_a_lease_expired_on_wall_time_stays_expired_under_an_earlier_fixed_instant() -> None:
    identity = _identity()
    request = _request(identity)
    permit = _permit(request, identity, wall_now() - timedelta(seconds=1))
    with frozen_clock(wall_now() - timedelta(days=3650)), pytest.raises(RefusalError) as refused:
        _validated_authority_permit(permit, request, identity)
    assert refused.value.reason is RefusalCode.TIMEOUT


def test_a_live_lease_stays_valid_under_a_later_fixed_instant() -> None:
    identity = _identity()
    request = _request(identity)
    permit = _permit(request, identity, wall_now() + timedelta(minutes=5))
    with frozen_clock(wall_now() + timedelta(days=30)):
        assert _validated_authority_permit(permit, request, identity) is permit

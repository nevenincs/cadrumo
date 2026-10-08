"""A complete inventory must fit before the worker receives a held permit."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from cadrumo.application.runtime.worker_authorization import WORKER_AUTOMATION_INVENTORY_MAX_BYTES
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AuthorityState
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_projections import PublicApiKey
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.time.clock import now

from ..worker_authorization import _require_inventory_ipc_budget

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_inventory_budget_accepts_small_complete_snapshot_and_refuses_oversize() -> None:
    _require_inventory_ipc_budget(AutomationInventory(grants=(), keys=(), requests=()))

    instant = now()
    profile_id, grant_id = uuid4(), uuid4()
    inventory = AutomationInventory(
        grants=(),
        keys=tuple(
            PublicApiKey(
                key_id=uuid4(),
                grant_id=grant_id,
                profile_id=profile_id,
                state=AuthorityState.ACTIVE,
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                last_used_at=None,
            )
            for _ in range(180)
        ),
        requests=(),
    )
    assert len(canonical_json_bytes(inventory.model_dump(mode="json"))) > WORKER_AUTOMATION_INVENTORY_MAX_BYTES
    with pytest.raises(ProfileAccessRefusedError) as refused:
        _require_inventory_ipc_budget(inventory)
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

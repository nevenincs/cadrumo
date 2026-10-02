"""Management facts cannot imply authority from a reachable service manager."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_snapshot_keeps_manager_autostart_separate_from_listener() -> None:
    manager = RuntimeManagerInspection(
        kind=RuntimeManagerKind.WINDOWS_TASK,
        available=True,
        provisioned=True,
        binding_matches=True,
        login_autostart=True,
        process_state=RuntimeManagerProcessState.RUNNING,
    )
    snapshot = RuntimeManagementSnapshot(
        listener=RuntimeListenerState.UNAVAILABLE,
        manager_availability=RuntimeManagerAvailability.AVAILABLE,
        manager=manager,
    )
    assert snapshot.listener is RuntimeListenerState.UNAVAILABLE
    assert snapshot.manager is not None and snapshot.manager.login_autostart
    assert not any(
        item in snapshot.model_dump_json() for item in ("executable", "storage_root", "os_owner_id", "unattended")
    )


def test_snapshot_refuses_unproved_manager_facts() -> None:
    manager = RuntimeManagerInspection(
        kind=RuntimeManagerKind.LINUX_USER_SERVICE,
        available=True,
        provisioned=False,
        binding_matches=False,
        login_autostart=False,
        process_state=RuntimeManagerProcessState.UNKNOWN,
    )
    with pytest.raises(ValidationError):
        RuntimeManagementSnapshot(
            listener=RuntimeListenerState.READY,
            manager_availability=RuntimeManagerAvailability.UNKNOWN,
            manager=manager,
        )

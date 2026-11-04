"""An expired attended service lease must not retire its human parent."""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
)
from cadrumo_client.contracts.profile_access import SessionRequest, SessionsLocked

from ...application import session_authority_delegation
from .test_service_records import RECORD_CAPABILITY, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_service_lease_renews_after_expiry_without_losing_human_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        # Shorten only this fixture's child lease, after cold human admission.
        monkeypatch.setattr(session_authority_delegation, "ACCESS_LEASE_MAXIMUM", timedelta(seconds=4))
        service = runtime.connect_service()
        runtime.admit(service)
        original = service.claim()
        assert original is not None
        record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
        assert record.state == "absent" and not material
        # Let both the worker's idle expiry and the runtime's lease sweep run
        # without service polling keeping the control pipe active.
        time.sleep(4.5)
        stale, material = service.connection.extension_record(
            ExtensionRecordRequest(
                action="extension_record_read",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=original.session_id,
                lease_id=original.lease_id,
                capability=RECORD_CAPABILITY,
                object_key="synthetic-expiry",
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(stale, ExtensionRecordReply)
        assert stale.refusal is ExtensionRecordRefusal.LEASE_INACTIVE and not material
        deadline = time.monotonic() + 8
        renewed = original
        while renewed.session_id == original.session_id and time.monotonic() < deadline:
            time.sleep(0.1)
            claimed = service.claim()
            assert claimed is not None, "expiry lost the live person's service approval"
            renewed = claimed
        assert renewed.session_id != original.session_id
        assert renewed.parent_session_id == runtime.person_session_id
        assert renewed.lease_id == original.lease_id
        record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
        assert record.state == "absent" and not material


@pytest.mark.parametrize("generation", [False, True])
def test_service_read_reclaims_expired_child_without_manual_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, generation: bool
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        monkeypatch.setattr(session_authority_delegation, "ACCESS_LEASE_MAXIMUM", timedelta(seconds=4))
        service = runtime.connect_service()
        runtime.admit(service)
        original = service.claim()
        assert original is not None
        time.sleep(4.5)
        exchanges: list[tuple[str, float]] = []
        exchange = service.connection.extension_record
        claim = service.claim

        def observed_exchange(request: ExtensionRecordRequest, payload: bytearray | None = None, *, deadline: float):
            exchanges.append((request.action, deadline))
            return exchange(request, payload, deadline=deadline)

        def observed_claim(*, timeout_deadline: TimeoutDeadline | None = None):
            assert timeout_deadline is not None
            exchanges.append(("claim", timeout_deadline.instant))
            return claim(timeout_deadline=timeout_deadline)

        monkeypatch.setattr(service.connection, "extension_record", observed_exchange)
        monkeypatch.setattr(service, "claim", observed_claim)
        payload = bytearray(b"expired child must not write")
        written = service.record_write(
            RECORD_CAPABILITY, "synthetic-expiry", payload, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert written.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert not any(payload)
        deleted = service.record_delete(
            RECORD_CAPABILITY, "synthetic-expiry", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert deleted.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert [action for action, _ in exchanges] == ["extension_record_write", "extension_record_delete"]
        exchanges.clear()
        timeout = TimeoutDeadline(time.monotonic() + 12)
        if generation:
            record = service.observe_generation(RECORD_CAPABILITY, timeout_deadline=timeout)
            assert record.state == "generation"
        else:
            record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry", timeout_deadline=timeout)
            assert record.state == "absent" and not material
        action = "extension_record_generation" if generation else "extension_record_read"
        assert exchanges == [(action, timeout.instant), ("claim", timeout.instant), (action, timeout.instant)]
        renewed = service.lease
        assert renewed is not None and renewed.session_id != original.session_id
        assert renewed.parent_session_id == original.parent_session_id == runtime.person_session_id
        assert renewed.lease_id == original.lease_id
        assert renewed.runtime_boot_id == original.runtime_boot_id
        exchanges.clear()
        denied, material = service.record_read("unregistered", "synthetic-expiry")
        assert denied.refusal is ExtensionRecordRefusal.CAPABILITY_DENIED and not material
        assert [action for action, _ in exchanges] == ["extension_record_read"]
        exchanges.clear()
        service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
        assert [action for action, _ in exchanges] == ["extension_record_read"]


@pytest.mark.parametrize("generation", [False, True])
def test_service_read_cannot_reclaim_after_parent_retirement(tmp_path: Path, generation: bool) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        runtime.admit(service)
        original = service.claim()
        assert original is not None
        locked = runtime.human.session(
            SessionRequest(
                action="session_lock",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=runtime.person_session_id,
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(locked, SessionsLocked) and runtime.person_session_id in locked.session_ids
        if generation:
            record = service.observe_generation(RECORD_CAPABILITY)
        else:
            record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
            assert not material
        assert record.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert service.lease is None
        assert service.claim() is None
        assert service.claim() is None

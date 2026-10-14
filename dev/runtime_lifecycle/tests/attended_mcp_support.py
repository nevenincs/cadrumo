"""Real person-reviewed attendance for cross-product MCP integration tests."""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import UUID

import psutil

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import SessionKind
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_harness.mcp.access_scope import surface_scope
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.runtime_admission import McpAdmission
from cadrumo_harness.mcp.surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES
from cadrumo_runtime.host.tests.stored_sign_in_runtime import StoredSignInRuntime

from ..proof_support import ProcessIdentity

_SCOPE = surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE])


def holding_person(runtime: StoredSignInRuntime) -> FrontendClient:
    """Resume a real CLI receipt and register its exact live session as a holder."""
    person = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI)
    person.resume_receipt()
    inventory = person.attendance_inventory()
    assert inventory.profile_id == runtime.profile_id and inventory.candidates == ()
    return person


def review_attendance(
    person: FrontendClient, identity: ProcessIdentity, *, attendance_id: UUID | None = None, approve: bool = True
) -> UUID | None:
    """Decide only a current kernel-witnessed ask with the finite harness scope."""
    inventory = person.attendance_inventory()
    assert inventory.profile_id == person.profile_id
    matching = [
        candidate
        for candidate in inventory.candidates
        if (attendance_id is None or candidate.attendance_id == attendance_id)
        and candidate.process_id == identity.pid
        and candidate.image_path is not None
        and Path(candidate.image_path).resolve(strict=True) == identity.image
    ]
    assert len(matching) <= 1
    if not matching:
        return None
    candidate = matching[0]
    assert identity.matches(psutil.Process(identity.pid))
    assert candidate.frontend is OperationFrontendProjection.EXTERNAL_CLIENT
    assert candidate.scope == _SCOPE
    decision = person.decide_attendance(candidate.attendance_id, approve=approve)
    assert decision.approved is approve and decision.attendance_id == candidate.attendance_id
    assert decision.runtime_boot_id == inventory.runtime_boot_id
    assert decision.connection_id == inventory.connection_id
    return candidate.attendance_id


def attended_client(
    runtime: StoredSignInRuntime, person: FrontendClient, *, connection: VerifiedConnection | None = None
) -> FrontendClient:
    """Admit this exact verified connection under the person's actual runtime lease."""
    identity = ProcessIdentity.capture(os.getpid())
    person.attendance_inventory()
    wire = runtime.connect() if connection is None else connection
    client = FrontendClient(
        wire, profile_id=runtime.profile_id, frontend=OperationFrontendProjection.EXTERNAL_CLIENT, scope=_SCOPE
    )
    pending = client.request_attendance()
    assert isinstance(pending, AttendancePending)
    assert pending.runtime_boot_id == wire.hello.boot_id
    assert review_attendance(person, identity, attendance_id=pending.attendance_id) == pending.attendance_id
    admitted = client.attendance_status(pending.attendance_id)
    assert isinstance(admitted, ProfileStatus)
    assert admitted.runtime_boot_id == pending.runtime_boot_id and admitted.connection_id == pending.connection_id
    assert admitted.status.profile_id == runtime.profile_id and admitted.status.denial is None
    lease = runtime.lease(client.session_id)
    assert lease.kind is SessionKind.ATTENDED and lease.parent_session_id == person.session_id
    return client


async def attended_status(
    runtime: StoredSignInRuntime, person: FrontendClient, adapter: RuntimeMcpAdapter, *, allow_renewal: bool = False
) -> dict[str, Any]:
    """Review the native ask opened by the real adapter, and retain its runtime provenance."""
    renewing = allow_renewal and adapter.admission is McpAdmission.ATTENDED and adapter.client is not None
    if allow_renewal:
        assert renewing, "a first admission must receive an exact person review"
        parent = await asyncio.to_thread(person.status)
        assert parent.status.denial is None and parent.status.session_id == person.session_id
    identity = ProcessIdentity.capture(os.getpid())
    asking = asyncio.create_task(adapter.call("status", {}))
    deadline = time.monotonic() + 30
    try:
        while await asyncio.to_thread(review_attendance, person, identity) is None:
            if asking.done():
                if renewing:
                    break
                answer = await asking
                raise AssertionError(f"adapter answered before exact attendance review: {answer}")
            assert time.monotonic() < deadline, "adapter made no exact native attendance ask"
            await asyncio.sleep(0.01)
        status = await asking
        assert adapter.admission is McpAdmission.ATTENDED
        assert adapter.client is not None
        lease = runtime.lease(adapter.client.session_id)
        assert lease.kind is SessionKind.ATTENDED and lease.parent_session_id == person.session_id
        assert status["session"] == McpAdmission.ATTENDED.value
        return status
    finally:
        if not asking.done():
            asking.cancel()
            with suppress(asyncio.CancelledError):
                await asking

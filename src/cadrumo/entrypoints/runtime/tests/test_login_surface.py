"""A connection is bound to the MCP surface its first login names, and to no other.

The connection service and its admission rules are the real ones. A login that
names a surface the runtime cannot enforce is refused before any credential is
read, any login is captured or any profile is opened, so these checks need no
profile custody and no worker.
"""

from __future__ import annotations

from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.test_enrollment_framing import MemoryChannel
from cadrumo.application.operations.mcp_surfaces import McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_READ_ONLY_LOCAL = McpSurfaceName.READ_ONLY_LOCAL
_SURFACES: tuple[McpSurfaceName | None, ...] = (None, McpSurfaceName.FULL, _READ_ONLY_LOCAL)


class _Login:
    """One live native login of the connecting owner."""

    login_id = "surface-test-login"

    def __init__(self, os_owner_id: str) -> None:
        self.os_owner_id = os_owner_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.os_owner_id,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _refuse_capture(_channel: object) -> _Login:
    raise AssertionError("a refused login must not capture the native login")


def _connections(tmp_path: Path, boot: UUID) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=boot,
        stop=Event(),
        capture_login=_refuse_capture,
    )


def _login(
    profile_id: UUID,
    *,
    surface: str | None,
    frontend: OperationFrontendProjection = OperationFrontendProjection.MCP,
    method: str = "api_key",
) -> RuntimeProfileLogin:
    document: dict[str, object] = {
        "request_id": uuid4(),
        "profile_id": profile_id,
        "method": method,
        "frontend": frontend,
    }
    if surface is not None:
        document["surface"] = surface
    return RuntimeProfileLogin.model_validate(document)


def _admitted_connection(
    connections: RuntimeProfileConnections,
    context: RuntimeConnectionContext,
    profile_id: UUID,
    surface: McpSurfaceName | None,
) -> ProfileConnection:
    """Register the connection a first key login leaves behind, bound to ``surface``."""
    connection = ProfileConnection(
        context,
        _Login(context.peer.os_owner_id),
        uuid4(),
        profile_id,
        OperationFrontendProjection.MCP,
        method="api_key",
        surface=surface,
    )
    connections._connections[context.connection_id] = connection
    return connection


@pytest.mark.parametrize("unknown", ["read-only", "Full", "read_only_local", "everything"])
def test_a_login_that_names_an_unknown_surface_is_refused(tmp_path: Path, unknown: str) -> None:
    boot, profile_id = uuid4(), uuid4()
    channel = MemoryChannel()
    context = RuntimeConnectionContext(uuid4(), boot, channel.peer)
    connections = _connections(tmp_path, boot)

    reply = connections.handle(context, channel, _login(profile_id, surface=unknown))

    assert isinstance(reply, RuntimeAccessRefusal)
    assert reply.code is RuntimeRefusalCode.INVALID_FRAME
    assert not connections._connections
    assert not channel.writes


@pytest.mark.parametrize("surface", [McpSurfaceName.FULL, _READ_ONLY_LOCAL])
@pytest.mark.parametrize(
    ("frontend", "method"),
    [
        (OperationFrontendProjection.CLI, "api_key"),
        (OperationFrontendProjection.TUI, "api_key"),
        (OperationFrontendProjection.CLI, "password"),
        (OperationFrontendProjection.TUI, "receipt"),
    ],
)
def test_a_surface_named_by_another_frontend_is_refused(
    tmp_path: Path, surface: McpSurfaceName, frontend: OperationFrontendProjection, method: str
) -> None:
    boot, profile_id = uuid4(), uuid4()
    channel = MemoryChannel()
    context = RuntimeConnectionContext(uuid4(), boot, channel.peer)
    connections = _connections(tmp_path, boot)
    request = _login(profile_id, surface=surface.value, frontend=frontend, method=method)

    reply = connections.handle(context, channel, request)

    assert isinstance(reply, RuntimeAccessRefusal)
    assert reply.code is RuntimeRefusalCode.INVALID_FRAME
    assert not connections._connections
    assert not channel.writes


def test_the_surface_a_login_names_is_resolved_only_for_the_mcp_frontend() -> None:
    profile_id = uuid4()
    resolve = RuntimeProfileConnections._login_surface

    assert resolve(_login(profile_id, surface=None)) is None
    assert resolve(_login(profile_id, surface=None, frontend=OperationFrontendProjection.CLI)) is None
    assert resolve(_login(profile_id, surface="full")) is McpSurfaceName.FULL
    assert resolve(_login(profile_id, surface="read-only-local")) is _READ_ONLY_LOCAL
    with pytest.raises(RuntimeRefusalError) as refused:
        resolve(_login(profile_id, surface="read-only-local", frontend=OperationFrontendProjection.TUI))
    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.parametrize("bound", _SURFACES)
@pytest.mark.parametrize("named", _SURFACES)
def test_a_connection_cannot_change_its_surface_after_its_first_login(
    tmp_path: Path, bound: McpSurfaceName | None, named: McpSurfaceName | None
) -> None:
    boot, profile_id = uuid4(), uuid4()
    channel = MemoryChannel()
    context = RuntimeConnectionContext(uuid4(), boot, channel.peer)
    connections = _connections(tmp_path, boot)
    connection = _admitted_connection(connections, context, profile_id, bound)
    request = _login(profile_id, surface=None if named is None else named.value)

    if named is bound:
        # The same surface is the same connection; nothing about it is rebound.
        assert connections._existing_or_captured_connection(context, channel, request, named) is connection
    else:
        with pytest.raises(AutomationCustodyError) as conflict:
            connections._existing_or_captured_connection(context, channel, request, named)
        assert conflict.value.reason is AutomationCustodyCode.CONFLICT
        reply = connections.handle(context, channel, request)
        assert isinstance(reply, RuntimeAccessRefusal)
        assert reply.code is AutomationCustodyCode.CONFLICT
    assert connections._connections[context.connection_id] is connection
    assert connection.surface is bound
    assert not channel.writes

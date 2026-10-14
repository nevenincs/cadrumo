"""The MCP server serves the tools and reveals the operations of the surface it was started on.

The surface is enforced by the runtime, which this file does not exercise: the
admitted client here answers every description. What is shown is the server's
own part, that it advertises the surface's tools, leaves operations outside the
surface out of search and describe, and names the surface when it is admitted.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    build_ledger_attach_definition,
    build_ledger_attach_registration,
    build_ledger_detach_definition,
    build_ledger_detach_registration,
)
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    EffectiveScopeSummary,
    ProfileAccessStatus,
)
from cadrumo.core import logging as cadrumo_logging
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_harness.mcp.access_scope import surface_scope

from .. import main as mcp_main
from .. import runtime_adapter as mcp_runtime
from .. import server as mcp_server
from ..protocol_contract import MCP_TOOL_CATALOGUE
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from ..surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface, McpSurfaceName
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_FULL = MCP_SURFACES[McpSurfaceName.FULL]
_READ_ONLY_LOCAL = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
_WRITES = (LEDGER_ATTACH_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID)
_EVERY_ID = sorted((AUTH_READ_OPERATION_DEFINITION_ID, *_WRITES))


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract description must not construct executor ports")


def _registry() -> OperationRegistry:
    """Compose the real public contracts of one local read and two ledger writes."""
    auth = build_auth_read_definition(_unused_ports)
    attach = build_ledger_attach_definition(_unused_ports)
    detach = build_ledger_detach_definition(_unused_ports)
    return OperationRegistry(
        definitions=(auth, attach, detach),
        public_registrations=(
            build_auth_read_registration(auth),
            build_ledger_attach_registration(attach),
            build_ledger_detach_registration(detach),
        ),
    )


class _AdmittedClient:
    """One exact MCP lease whose scope holds every operation and whose runtime describes each."""

    def __init__(self, profile_id: UUID, registry: OperationRegistry) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.EXTERNAL_CLIENT
        self.session_id = uuid4()
        self.registry = registry
        self.described: list[str] = []
        self._status = ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=profile_id,
            session_id=self.session_id,
            session_expires_at=now() + timedelta(minutes=5),
            grant_state=AuthorityState.ACTIVE,
            grant_expires_at=now() + timedelta(minutes=5),
            grant_valid=True,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=EffectiveScopeSummary.summarize(
                AccessScope(
                    operations=frozenset(_EVERY_ID),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                )
            ),
            denial=None,
        )

    def status(self) -> SimpleNamespace:
        return SimpleNamespace(status=self._status)

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        self.described.append(definition_id)
        return self.registry.describe_public_definition(definition_id)

    def subscribe_session_retirement(self, receive: object) -> None:
        """The runtime retires no lease of this double."""

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """The runtime sends this double no lifecycle notice."""

    def close(self) -> None:
        return None


def _adapter(surface: McpSurface, client: _AdmittedClient | None = None) -> RuntimeMcpAdapter:
    profile_id = uuid4() if client is None else client.profile_id
    return RuntimeMcpAdapter(
        profile_id=profile_id, client=None if client is None else cast(FrontendClient, client), surface=surface
    )


def _found(result: dict[str, object]) -> list[str]:
    assert result["outcome"] == "found"
    operations = cast("list[dict[str, object]]", result["operations"])
    return [str(contract["definition_id"]) for contract in operations]


def test_the_two_fixture_writes_are_off_the_read_only_local_surface_and_the_read_is_on_it() -> None:
    """The operations below are told apart by the surface itself, not by this file."""
    assert _READ_ONLY_LOCAL.admits(AUTH_READ_OPERATION_DEFINITION_ID)
    assert not any(_READ_ONLY_LOCAL.admits(definition_id) for definition_id in _WRITES)
    assert all(_FULL.admits(definition_id) for definition_id in _EVERY_ID)


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_the_server_advertises_exactly_the_tools_of_its_surface(surface: McpSurface) -> None:
    adapter = _adapter(surface)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            names = [tool.name for tool in (await client.list_tools()).tools]
    finally:
        await adapter.close()

    assert names == [name for name, _description, _schema in MCP_TOOL_CATALOGUE if name in surface.tools]
    assert set(names) == surface.tools


@pytest.mark.anyio
async def test_a_tool_the_surface_leaves_out_does_not_answer() -> None:
    left_out = sorted(_FULL.tools - _READ_ONLY_LOCAL.tools)
    assert left_out
    narrowed, whole = _adapter(_READ_ONLY_LOCAL), _adapter(_FULL)
    try:
        for name in left_out:
            assert await narrowed.call(name, {}) == {"outcome": "refused", "code": "unknown_tool"}
            # The same call reaches the tool on the full surface, which then refuses its empty arguments.
            assert await whole.call(name, {}) == {"outcome": "refused", "code": "invalid_request"}
    finally:
        await narrowed.close()
        await whole.close()


@pytest.mark.anyio
@pytest.mark.parametrize("args", [{}, {"query": "ledger"}, {"family": "ledger"}, {"query": "diagnostics"}])
async def test_search_returns_only_operations_on_the_surface(args: dict[str, object]) -> None:
    registry = _registry()
    narrowed_client = _AdmittedClient(uuid4(), registry)
    whole_client = _AdmittedClient(uuid4(), registry)
    narrowed, whole = _adapter(_READ_ONLY_LOCAL, narrowed_client), _adapter(_FULL, whole_client)
    try:
        on_surface = _found(await narrowed.call("search", args))
        on_full = _found(await whole.call("search", args))
    finally:
        await narrowed.close()
        await whole.close()

    assert set(on_surface) <= {AUTH_READ_OPERATION_DEFINITION_ID}
    assert on_surface == [definition_id for definition_id in on_full if _READ_ONLY_LOCAL.admits(definition_id)]
    # The server does not even ask the runtime about an operation outside its surface.
    assert set(narrowed_client.described) <= {AUTH_READ_OPERATION_DEFINITION_ID}


@pytest.mark.anyio
async def test_search_without_a_query_lists_the_whole_scope_only_on_the_full_surface() -> None:
    registry = _registry()
    narrowed_client = _AdmittedClient(uuid4(), registry)
    whole_client = _AdmittedClient(uuid4(), registry)
    narrowed, whole = _adapter(_READ_ONLY_LOCAL, narrowed_client), _adapter(_FULL, whole_client)
    try:
        assert _found(await narrowed.call("search", {})) == [AUTH_READ_OPERATION_DEFINITION_ID]
        assert _found(await whole.call("search", {})) == _EVERY_ID
    finally:
        await narrowed.close()
        await whole.close()


@pytest.mark.anyio
async def test_describe_reveals_only_operations_on_the_surface() -> None:
    registry = _registry()
    narrowed_client = _AdmittedClient(uuid4(), registry)
    whole_client = _AdmittedClient(uuid4(), registry)
    narrowed, whole = _adapter(_READ_ONLY_LOCAL, narrowed_client), _adapter(_FULL, whole_client)
    try:
        for definition_id in _WRITES:
            refused = await narrowed.call("describe", {"definition_id": definition_id})
            assert refused == {"outcome": "refused", "code": "frontend_denied"}
            assert (await whole.call("describe", {"definition_id": definition_id}))["outcome"] == "described"
        read = await narrowed.call("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
        assert read["outcome"] == "described"
    finally:
        await narrowed.close()
        await whole.close()

    assert narrowed_client.described == [AUTH_READ_OPERATION_DEFINITION_ID]
    assert whole_client.described == list(_WRITES)


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_an_admission_names_the_finite_scope_ceiling_for_every_surface(
    monkeypatch: pytest.MonkeyPatch, surface: McpSurface
) -> None:
    profile_id, reference = uuid4(), uuid4()
    admitted = _AdmittedClient(profile_id, _registry())
    opened: list[dict[str, object]] = []

    async def admit(**options: object) -> FrontendClient:
        opened.append(options)
        return cast(FrontendClient, admitted)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", admit)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None, surface=surface)
    try:
        await adapter.bootstrap_reference(reference)
        assert adapter.client is admitted
    finally:
        await adapter.close()

    expected: dict[str, object] = {
        "profile_id": profile_id,
        "credential_reference": reference,
        "frontend": OperationFrontendProjection.EXTERNAL_CLIENT,
        "timeout": PROFILE_ADMISSION_TIMEOUT_SECONDS,
        "scope": surface_scope(surface),
    }
    assert opened == [expected]


def _run_entry_point(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> list[dict[str, object]]:
    """Run the installed entry point on these arguments and return what it asked to be served."""
    served: list[dict[str, object]] = []
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    monkeypatch.delenv("CADRUMO_MCP_REQUIRED_VERSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["cadrumo-mcp", *arguments])
    monkeypatch.setattr(cadrumo_logging, "configure_logging", lambda: None)
    monkeypatch.setattr(mcp_server, "serve", lambda **options: served.append(options))
    mcp_main.main()
    return served


@pytest.mark.parametrize("unknown", ["read-only", "Full", "", "everything"])
def test_the_entry_point_refuses_an_unknown_surface_before_serving(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], unknown: str
) -> None:
    with pytest.raises(SystemExit) as stopped:
        _run_entry_point(monkeypatch, ["--profile-id", str(uuid4()), "--surface", unknown])

    assert stopped.value.code == 2
    message = capsys.readouterr().err
    assert f"unknown surface {unknown!r}" in message
    for name in McpSurfaceName:
        assert name.value in message


@pytest.mark.parametrize("surface", list(McpSurfaceName))
def test_the_entry_point_serves_the_surface_it_is_given(
    monkeypatch: pytest.MonkeyPatch, surface: McpSurfaceName
) -> None:
    profile_id = uuid4()

    served = _run_entry_point(monkeypatch, ["--profile-id", str(profile_id), "--surface", surface.value])

    assert served == [{"profile_id": profile_id, "credential_reference": None, "surface": MCP_SURFACES[surface]}]


def test_the_entry_point_serves_the_full_surface_when_none_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id, reference = uuid4(), uuid4()

    served = _run_entry_point(monkeypatch, ["--profile-id", str(profile_id), "--credential-reference", str(reference)])

    assert served == [
        {"profile_id": profile_id, "credential_reference": reference, "surface": MCP_SURFACES[DEFAULT_MCP_SURFACE]}
    ]
    assert served[0]["surface"] is _FULL

"""MCP operation discovery ranks only admitted, describable registered contracts."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import (
    build_auth_read_definition,
    build_auth_read_registration,
)
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
    ProfileAccessStatus,
)
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DENIED_DEFINITION_ID = "modelo.calculate"


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract description must not construct executor ports")


def _registry() -> OperationRegistry:
    """Compose real public contracts whose request schemas carry distinct vocabulary."""
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
    """One exact MCP lease whose runtime admits every description but one."""

    def __init__(self, profile_id: UUID, registry: OperationRegistry, *, failure: str | None = None) -> None:
        self.profile_id = profile_id
        self.failure = failure
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.registry = registry
        self.described: list[str] = []
        self.closed = False
        operations = {definition.definition_id for definition in registry.definitions} | {_DENIED_DEFINITION_ID}
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
            effective_scope=AccessScope(
                operations=frozenset(operations),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            denial=None,
        )

    def status(self) -> SimpleNamespace:
        return SimpleNamespace(status=self._status)

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        self.described.append(definition_id)
        if self.failure is not None:
            raise RuntimeFrontendRefusedError(self.failure)
        if definition_id == _DENIED_DEFINITION_ID:
            raise RuntimeFrontendRefusedError("operation_denied")
        return self.registry.describe_public_definition(definition_id)

    def close(self) -> None:
        self.closed = True


def _definition_ids(result: dict[str, object]) -> list[str]:
    assert result["outcome"] == "found"
    operations = cast("list[dict[str, object]]", result["operations"])
    return [str(contract["definition_id"]) for contract in operations]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "expected"),
    (
        # Request field vocabulary, not the definition id, carries these terms.
        ("purchase invoice", [LEDGER_ATTACH_OPERATION_DEFINITION_ID]),
        ("diagnostics", [AUTH_READ_OPERATION_DEFINITION_ID]),
        # A definition-id term outranks the shared ledger term.
        ("ledger detach", [LEDGER_DETACH_OPERATION_DEFINITION_ID, LEDGER_ATTACH_OPERATION_DEFINITION_ID]),
        (AUTH_READ_OPERATION_DEFINITION_ID, [AUTH_READ_OPERATION_DEFINITION_ID]),
        # Ranking matches whole terms and stems; a fragment is not a match.
        ("loc", []),
    ),
)
async def test_search_ranks_admitted_contracts_with_the_command_ranker(query: str, expected: list[str]) -> None:
    profile_id = uuid4()
    registry = _registry()
    client = _AdmittedClient(profile_id, registry)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            found = await sdk.call_tool("search", {"query": query})
        assert found.is_error is False
        result = found.structured_content
        assert result is not None
        assert _definition_ids(result) == expected
        operations = cast("list[dict[str, object]]", result["operations"])
        for contract in operations:
            definition_id = str(contract["definition_id"])
            assert contract == registry.lookup_public_contract(definition_id).model_dump(mode="json")
        assert sorted(client.described) == sorted(
            {definition.definition_id for definition in registry.definitions} | {_DENIED_DEFINITION_ID}
        )
    finally:
        await adapter.close()
    assert client.closed


@pytest.mark.anyio
@pytest.mark.parametrize("args", ({}, {"query": "  "}))
async def test_search_without_query_lists_every_describable_admitted_contract(args: dict[str, object]) -> None:
    profile_id = uuid4()
    registry = _registry()
    client = _AdmittedClient(profile_id, registry)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", args)
    finally:
        await adapter.close()
    assert _definition_ids(result) == sorted(definition.definition_id for definition in registry.definitions)
    assert _DENIED_DEFINITION_ID not in _definition_ids(result)


@pytest.mark.anyio
async def test_search_refuses_when_a_description_fails_for_a_reason_other_than_scope() -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry(), failure="session_expired")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {"query": "ledger"})
    finally:
        await adapter.close()
    assert result == {"outcome": "refused", "code": "session_expired"}

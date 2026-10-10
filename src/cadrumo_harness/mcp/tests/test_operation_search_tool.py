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
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.operation_contract_cache import OperationContractCache
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

    def __init__(
        self,
        profile_id: UUID,
        registry: OperationRegistry,
        *,
        failure: str | None = None,
        refusals: dict[str, str] | None = None,
    ) -> None:
        self.profile_id = profile_id
        self.failure = failure
        self.refusals = {} if refusals is None else refusals
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
        if definition_id in self.refusals:
            raise RuntimeFrontendRefusedError(self.refusals[definition_id])
        return self.registry.describe_public_definition(definition_id)

    def operation(self, request: object, *, deadline: float) -> NoReturn:
        assert deadline > 0
        raise TimeoutError("synthetic transport timeout")

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


_PERMITTED_IDS = sorted(
    (AUTH_READ_OPERATION_DEFINITION_ID, LEDGER_ATTACH_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID)
)


async def _all_pages(adapter: RuntimeMcpAdapter, args: dict[str, object]) -> list[dict[str, object]]:
    """Follow next_cursor from the first page until the runtime stops offering one."""
    pages: list[dict[str, object]] = []
    page = await adapter.call("search", args)
    while True:
        assert page["outcome"] == "found"
        pages.append(page)
        cursor = page.get("next_cursor")
        if cursor is None:
            return pages
        assert len(pages) <= len(_PERMITTED_IDS) + 1
        page = await adapter.call("search", args | {"cursor": cursor})


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "expected"),
    (
        ("", _PERMITTED_IDS),
        ("ledger", [LEDGER_ATTACH_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID]),
    ),
)
async def test_search_pages_are_disjoint_and_cover_the_scope_in_stable_order(query: str, expected: list[str]) -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        whole = await adapter.call("search", {"query": query})
        pages = await _all_pages(adapter, {"query": query, "limit": 1})
        again = await _all_pages(adapter, {"query": query, "limit": 1})
    finally:
        await adapter.close()
    assert "next_cursor" not in whole and "unavailable" not in whole
    assert sorted(_definition_ids(whole)) == expected
    paged = [_definition_ids(page) for page in pages]
    assert all(len(ids) <= 1 for ids in paged)
    assert "next_cursor" in pages[0]
    covered = [definition_id for ids in paged for definition_id in ids]
    assert len(covered) == len(set(covered))
    assert covered == _definition_ids(whole)
    assert [_definition_ids(page) for page in again] == paged


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("family", "expected"),
    (
        ("ledger", [LEDGER_ATTACH_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID]),
        (LEDGER_ATTACH_OPERATION_DEFINITION_ID, [LEDGER_ATTACH_OPERATION_DEFINITION_ID]),
        ("auth", [AUTH_READ_OPERATION_DEFINITION_ID]),
        # A family is a whole dotted segment, not a leading fragment.
        ("led", []),
        ("  ", _PERMITTED_IDS),
    ),
)
async def test_search_family_narrows_the_scope_before_any_contract_is_read(family: str, expected: list[str]) -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {"family": family})
    finally:
        await adapter.close()
    assert _definition_ids(result) == expected
    assert set(client.described) - {_DENIED_DEFINITION_ID} == set(expected)
    assert (_DENIED_DEFINITION_ID in client.described) == (not family.strip())


@pytest.mark.anyio
@pytest.mark.parametrize(
    "args",
    (
        {"limit": 0},
        {"limit": 201},
        {"limit": True},
        {"cursor": 7},
        # A listing cursor names a definition; a ranked cursor is a position.
        {"cursor": "7"},
        {"query": "ledger", "cursor": LEDGER_ATTACH_OPERATION_DEFINITION_ID},
    ),
)
async def test_search_refuses_malformed_paging_before_reading_any_contract(args: dict[str, object]) -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", args)
    finally:
        await adapter.close()
    assert result == {"outcome": "refused", "code": "invalid_request"}
    assert client.described == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "expected"),
    (
        ("", [AUTH_READ_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID]),
        ("ledger", [LEDGER_DETACH_OPERATION_DEFINITION_ID]),
    ),
)
async def test_search_reports_one_unavailable_operation_and_lists_the_rest(query: str, expected: list[str]) -> None:
    profile_id = uuid4()
    refusals = {LEDGER_ATTACH_OPERATION_DEFINITION_ID: "backend_unavailable"}
    client = _AdmittedClient(profile_id, _registry(), refusals=refusals)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {"query": query})
    finally:
        await adapter.close()
    assert _definition_ids(result) == expected
    assert result["unavailable"] == [
        {"definition_id": LEDGER_ATTACH_OPERATION_DEFINITION_ID, "code": "backend_unavailable"}
    ]


@pytest.mark.anyio
async def test_search_still_fails_whole_when_the_session_is_refused_for_one_operation() -> None:
    profile_id = uuid4()
    refusals = {LEDGER_DETACH_OPERATION_DEFINITION_ID: "session_inactive"}
    client = _AdmittedClient(profile_id, _registry(), refusals=refusals)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {})
    finally:
        await adapter.close()
    assert result == {"outcome": "refused", "code": "session_inactive"}


@pytest.mark.anyio
async def test_search_rows_carry_what_selects_an_operation_without_the_request_schema() -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {})
    finally:
        await adapter.close()
    operations = cast("list[dict[str, object]]", result["operations"])
    assert len(operations) == len(_PERMITTED_IDS)
    for row in operations:
        assert {"definition_id", "permitted_effects", "interaction_kinds", "review_projection_schema"} <= set(row)
        assert "request_json_schema" not in row


@pytest.mark.anyio
async def test_search_and_execute_read_each_contract_once_per_session_while_describe_reads_afresh() -> None:
    profile_id = uuid4()
    client = _AdmittedClient(profile_id, _registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        await adapter.call("search", {})
        await adapter.call("search", {"query": "ledger"})
        submitted = await adapter.call(
            "execute",
            {
                "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                "subject_ref": f"profile:{profile_id}",
                "payload": {"kind": "status"},
            },
        )
        assert submitted["outcome"] == "unresolved"
        assert [client.described.count(definition_id) for definition_id in _PERMITTED_IDS] == [1, 1, 1]
        # An operation the runtime does not offer is never remembered, so every search asks again.
        assert client.described.count(_DENIED_DEFINITION_ID) == 2
        described = await adapter.call("describe", {"definition_id": LEDGER_ATTACH_OPERATION_DEFINITION_ID})
        assert described["outcome"] == "described"
        assert client.described.count(LEDGER_ATTACH_OPERATION_DEFINITION_ID) == 2
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_reauthentication_starts_a_fresh_description_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    registry = _registry()
    original = _AdmittedClient(profile_id, registry)
    replacement = _AdmittedClient(profile_id, registry)

    async def admit(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        return cast(RuntimeFrontendClient, replacement)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", admit)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, original))
    try:
        await adapter.call("search", {})
        authenticated = await adapter.call("authenticate", {"credential_reference": str(uuid4())})
        assert authenticated["outcome"] == "authenticated"
        await adapter.call("search", {})
    finally:
        await adapter.close()
    assert sorted(original.described) == sorted(replacement.described)
    assert sorted(set(replacement.described)) == sorted({*_PERMITTED_IDS, _DENIED_DEFINITION_ID})


def test_contract_cache_is_not_shared_across_sessions_or_profiles() -> None:
    registry = _registry()
    profile_id = uuid4()
    first = _AdmittedClient(profile_id, registry)
    other_session = _AdmittedClient(profile_id, registry)
    other_profile = _AdmittedClient(uuid4(), registry)
    cache = OperationContractCache()
    for client in (first, first, other_session, other_session, other_profile, other_profile, first):
        cache.description(cast(RuntimeFrontendClient, client), AUTH_READ_OPERATION_DEFINITION_ID, deadline=1.0)
    assert first.described == [AUTH_READ_OPERATION_DEFINITION_ID] * 2
    assert other_session.described == [AUTH_READ_OPERATION_DEFINITION_ID]
    assert other_profile.described == [AUTH_READ_OPERATION_DEFINITION_ID]


def test_contract_cache_reads_again_when_the_runtime_reports_another_digest() -> None:
    registry = _registry()
    client = _AdmittedClient(uuid4(), registry)
    cache = OperationContractCache()
    reader = cast(RuntimeFrontendClient, client)
    definition_id = AUTH_READ_OPERATION_DEFINITION_ID
    current = registry.lookup_public_contract(definition_id).definition_contract_digest
    cache.description(reader, definition_id, deadline=1.0)
    cache.description(reader, definition_id, deadline=1.0, digest=current)
    assert client.described == [definition_id]
    cache.description(reader, definition_id, deadline=1.0, digest="0" * 64)
    assert client.described == [definition_id] * 2


def test_contract_cache_forgets_an_operation_the_runtime_now_refuses() -> None:
    registry = _registry()
    client = _AdmittedClient(uuid4(), registry)
    cache = OperationContractCache()
    reader = cast(RuntimeFrontendClient, client)
    definition_id = LEDGER_ATTACH_OPERATION_DEFINITION_ID
    cache.description(reader, definition_id, deadline=1.0)
    client.refusals[definition_id] = "operation_denied"
    with pytest.raises(RuntimeFrontendRefusedError):
        cache.description(reader, definition_id, deadline=1.0, fresh=True)
    with pytest.raises(RuntimeFrontendRefusedError):
        cache.description(reader, definition_id, deadline=1.0)
    assert client.described == [definition_id] * 3

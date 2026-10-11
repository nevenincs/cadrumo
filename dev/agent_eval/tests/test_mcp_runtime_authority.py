"""MCP authority queries retain canonical registry data and publication identity."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import override
from uuid import uuid4

import pytest

from cadrumo.application.modelo.registry_discovery import registry_support_matrix
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry import authority as authority_module
from cadrumo.domain.calculations.registry.authority import (
    IndexedRegistryAuthority,
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    SnapshotGlobalsComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    synthetic_legal_identity,
)
from cadrumo.domain.portals.registry import PORTAL_REGISTRY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DESCRIPTOR_NAME = "authority.current.json"
_SYNTHETIC_MODELO = "130"
"""The modelo whose titles the synthetic publications borrow, and the only one they hold."""


def _a_portal_id() -> str:
    return str(next(iter(PORTAL_REGISTRY)))


async def _assert_all_advertised_authority_queries_refuse(adapter: RuntimeMcpAdapter, code: str) -> None:
    """Ask every query the tool advertises, each with coordinates it accepts, and hold each to one refusal."""
    scoped = {"modelo": "100", "filing_year": 2024, "period": "0A"}
    requests: dict[str, dict[str, object]] = {
        "modelos": {},
        "support": {},
        "bindings": {"modelo": "100", "filing_year": 2024},
        "describe": scoped,
        "casillas": scoped,
        "casilla": {**scoped, "casilla": "0505"},
        "formulas": scoped,
        "categories": {},
        "portals": {},
        "portal": {"portal": _a_portal_id()},
        "auth_providers": {},
        "apoderado_scopes": {},
    }
    async with connected_server_and_client_session(build_server(adapter)) as client:
        tools = (await client.list_tools()).tools
        authority_tool = next(tool for tool in tools if tool.name == "authority")
        queries = authority_tool.input_schema["properties"]["query"]["enum"]
        assert set(queries) == set(requests)
        for query in queries:
            refused = await client.call_tool("authority", {"query": query, **requests[query]})
            assert refused.is_error is True, query
            assert refused.structured_content == {"outcome": "refused", "code": code}, query
    assert adapter.client is None


def _synthetic_artifact(identity: str) -> AuthorityArtifact:
    """Build one publishable authority that holds a single modelo and its own legal identity."""
    with bundled_indexed_authority().operation() as packaged:
        profile_schema = packaged.profile_schema()
        directory = packaged.modelo_directory(_SYNTHETIC_MODELO)
    modelo = minimal_modelo(minimal_revision()).model_copy(
        update={
            "title_localization_key": directory.modelo.title_localization_key,
            "official_name_localization_key": directory.modelo.official_name_localization_key,
        }
    )
    return AuthorityArtifact(
        modelos=(modelo,),
        catalogues=minimal_catalogues(),
        identity_digest=synthetic_legal_identity(identity),
        profile_schema=profile_schema,
    )


class _SucceededWhileHeld(IndexedRegistryAuthority):
    """A real authority whose publisher installs a successor just after an operation is pinned.

    Everything the authority does is its own. Only the moment of the cutover
    is arranged: once armed, the next operation is handed to ``succeed`` after
    its pin is taken and before its holder reads anything.
    """

    def __init__(self, descriptor_path: Path, *, succeed: Callable[[PinnedAuthorityOperation], None]) -> None:
        super().__init__(descriptor_path)
        self._succeed = succeed
        self.armed = False

    @override
    @contextmanager
    def operation(self) -> Generator[PinnedAuthorityOperation]:
        with super().operation() as pinned:
            if self.armed:
                self.armed = False
                self._succeed(pinned)
            yield pinned


@pytest.mark.anyio
async def test_public_authority_queries_preserve_coordinates_and_support_projection() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        described = await adapter.call(
            "authority",
            {
                "query": "describe",
                "modelo": "100",
                "filing_year": 2024,
                "period": "0A",
                "as_of": "2024-12-31",
            },
        )

        assert described["outcome"] == "published"
        assert adapter.client is None
        assert described["report"]["code"] == "100"
        assert described["report"]["filing_year"] == 2024
        assert described["report"]["period"] == "0A"
        assert described["report"]["revision"]
        assert described["report"]["authority_grade"] == "filing"

        low_grade = await adapter.call(
            "authority",
            {
                "query": "describe",
                "modelo": "036",
                "filing_year": 2024,
                "period": "alta",
                "as_of": "2024-12-31",
            },
        )
        assert low_grade["outcome"] == "published"
        assert low_grade["report"]["authority_grade"] == "applicability"
        assert (low_grade["report"]["filing_year"], low_grade["report"]["period"]) == (2024, "alta")

        with bundled_indexed_authority().operation() as operation:
            canonical_support = registry_support_matrix(operation=operation).model_dump(mode="json")
        support = await adapter.call("authority", {"query": "support"})

        assert support["outcome"] == "published"
        assert canonical_support["entries"], "the published authority supports no modelo; the comparison is empty"
        assert support["report"]["entries"] == canonical_support["entries"]
        assert support["report"]["modelo_count"] == len(canonical_support["entries"])
        assert adapter.client is None
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_authority_response_provenance_is_the_publication_the_report_was_read_from(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    publish_authority_artifact: Callable[[AuthorityArtifact], AuthorityDescriptor],
) -> None:
    artifact = _synthetic_artifact("mcp-provenance-publication")
    published = publish_authority_artifact(artifact)
    authority = IndexedRegistryAuthority(tmp_path / _DESCRIPTOR_NAME)
    with authority.operation() as held:
        pin = held.pin()
    with bundled_indexed_authority().operation() as packaged:
        packaged_pin = packaged.pin()
    assert pin.logical_generation == published.logical_generation == artifact.identity_digest
    assert pin.logical_generation != packaged_pin.logical_generation

    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", authority)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        listed = await adapter.call("authority", {"query": "modelos"})
        support = await adapter.call("authority", {"query": "support"})
    finally:
        await adapter.close()
        authority.close()

    # Each reply names the publication it was read under, and its report holds that publication's
    # one modelo and none of the packaged authority's.
    for result in (listed, support):
        assert result["outcome"] == "published"
        assert result["logical_generation"] == pin.logical_generation
        assert result["reader_incarnation"] == pin.reader_incarnation
    assert [row["code"] for row in listed["report"]["modelos"]] == [_SYNTHETIC_MODELO]
    assert [entry["modelo_id"] for entry in support["report"]["entries"]] == [_SYNTHETIC_MODELO]


@pytest.mark.anyio
async def test_missing_configured_authority_refuses_without_packaged_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        with override_settings(cadrumo_authority_root=tmp_path):
            await _assert_all_advertised_authority_queries_refuse(adapter, "published_authority_unavailable")
    finally:
        await adapter.close()


def _copy_and_corrupt_published_database(source_descriptor: Path, destination: Path) -> Path:
    """Copy one real publication and alter one database byte in the isolated copy."""
    descriptor = AuthorityDescriptor.read(source_descriptor)
    copied_descriptor = destination / _DESCRIPTOR_NAME
    copied_database = destination / descriptor.database
    shutil.copy2(source_descriptor, copied_descriptor)
    shutil.copy2(source_descriptor.parent / descriptor.database, copied_database)

    offset = copied_database.stat().st_size // 2
    with copied_database.open("r+b") as stream:
        stream.seek(offset)
        original = stream.read(1)
        stream.seek(offset)
        stream.write(bytes([original[0] ^ 0xFF]))
    return copied_descriptor


@pytest.mark.anyio
async def test_corrupt_configured_database_refuses_without_packaged_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_descriptor = bundled_authority_descriptor_path()
    _copy_and_corrupt_published_database(source_descriptor, tmp_path)
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)

    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        with override_settings(cadrumo_authority_root=tmp_path):
            await _assert_all_advertised_authority_queries_refuse(adapter, "published_authority_invalid")
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_sdk_query_finishes_on_held_publication_across_descriptor_cutover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    publish_authority_artifact: Callable[[AuthorityArtifact], AuthorityDescriptor],
) -> None:
    first_artifact = _synthetic_artifact("mcp-first-publication")
    second_artifact = replace(first_artifact, identity_digest=synthetic_legal_identity("mcp-second-publication"))
    first = publish_authority_artifact(first_artifact)
    held_through_cutover: list[PinnedAuthorityOperation] = []

    def succeed(pinned: PinnedAuthorityOperation) -> None:
        assert pinned.pin() == first_pin
        second = publish_authority_artifact(second_artifact)
        assert second.logical_generation != first.logical_generation
        assert pinned.profile_decode_context().generation == first_pin
        held_through_cutover.append(pinned)

    authority = _SucceededWhileHeld(tmp_path / _DESCRIPTOR_NAME, succeed=succeed)
    with authority.operation() as initial:
        first_pin = initial.pin()
        expected_entries = registry_support_matrix(operation=initial).model_dump(mode="json")["entries"]
    assert expected_entries

    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", authority)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            authority.armed = True
            result = await client.call_tool("authority", {"query": "support"})
            assert result.is_error is False
            assert len(held_through_cutover) == 1, "the successor was published while the query held its pin"
            assert isinstance(result.structured_content, dict)
            assert result.structured_content["outcome"] == "published"
            assert result.structured_content["logical_generation"] == first_pin.logical_generation
            assert result.structured_content["reader_incarnation"] == first_pin.reader_incarnation
            assert result.structured_content["report"]["entries"] == expected_entries
            current = await client.call_tool("authority", {"query": "support"})
            assert current.is_error is False
            assert isinstance(current.structured_content, dict)
            assert current.structured_content["logical_generation"] == second_artifact.identity_digest
            assert current.structured_content["reader_incarnation"] != first_pin.reader_incarnation
        with authority.operation() as successor, pytest.raises(RegistrySnapshotError, match="generation boundary"):
            successor.load(SnapshotGlobalsComponentQuery(), pin=first_pin)
    finally:
        await adapter.close()
        authority.close()

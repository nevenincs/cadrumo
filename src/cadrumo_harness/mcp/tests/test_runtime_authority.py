"""MCP authority queries retain canonical registry data and publication identity."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path
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
    AuthorityGenerationPin,
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
from cadrumo_harness.mcp import authority_query as mcp_authority
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DESCRIPTOR_NAME = "authority.current.json"


async def _assert_all_advertised_authority_queries_refuse(adapter: RuntimeMcpAdapter, code: str) -> None:
    requests = {
        "modelos": {},
        "support": {},
        "bindings": {"modelo": "100", "filing_year": 2024},
        "describe": {"modelo": "100", "filing_year": 2024, "period": "0A"},
        "casillas": {"modelo": "100", "filing_year": 2024, "period": "0A"},
        "casilla": {"modelo": "100", "filing_year": 2024, "period": "0A", "casilla": "0505"},
        "formulas": {"modelo": "100", "filing_year": 2024, "period": "0A"},
    }
    async with connected_server_and_client_session(build_server(adapter)) as client:
        tools = (await client.list_tools()).tools
        authority_tool = next(tool for tool in tools if tool.name == "authority")
        queries = authority_tool.input_schema["properties"]["query"]["enum"]
        assert set(queries) == set(requests)
        for query in queries:
            refused = await client.call_tool("authority", {"query": query, **requests[query]})
            assert refused.is_error is True
            assert refused.structured_content == {"outcome": "refused", "code": code}
    assert adapter.client is None


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

        with bundled_indexed_authority().operation() as operation:
            canonical_support = registry_support_matrix(operation=operation).model_dump(mode="json")
        support = await adapter.call("authority", {"query": "support"})

        assert support["outcome"] == "published"
        assert support["report"] == canonical_support
        assert adapter.client is None
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_authority_response_provenance_matches_the_pin_passed_to_the_real_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_query = mcp_authority.registry_describe_modelo_for_registry_scope
    observed_pins: list[AuthorityGenerationPin] = []

    def record_pin_and_run_query(
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None,
        operation: PinnedAuthorityOperation,
    ) -> object:
        observed_pins.append(operation.pin())
        return canonical_query(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
            operation=operation,
        )

    monkeypatch.setattr(mcp_authority, "registry_describe_modelo_for_registry_scope", record_pin_and_run_query)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        result = await adapter.call(
            "authority",
            {"query": "describe", "modelo": "100", "filing_year": 2024, "period": "0A"},
        )
    finally:
        await adapter.close()

    assert result["outcome"] == "published"
    assert len(observed_pins) == 1
    assert result["logical_generation"] == observed_pins[0].logical_generation
    assert result["reader_incarnation"] == observed_pins[0].reader_incarnation


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
    with bundled_indexed_authority().operation() as packaged:
        profile_schema = packaged.profile_schema()
        directory = packaged.modelo_directory("130")
    modelo = minimal_modelo(minimal_revision()).model_copy(
        update={
            "title_localization_key": directory.modelo.title_localization_key,
            "official_name_localization_key": directory.modelo.official_name_localization_key,
        }
    )
    first_artifact = AuthorityArtifact(
        modelos=(modelo,),
        catalogues=minimal_catalogues(),
        identity_digest=synthetic_legal_identity("mcp-first-publication"),
        profile_schema=profile_schema,
    )
    second_artifact = replace(first_artifact, identity_digest=synthetic_legal_identity("mcp-second-publication"))
    first = publish_authority_artifact(first_artifact)
    authority = IndexedRegistryAuthority(tmp_path / _DESCRIPTOR_NAME)
    canonical_query = mcp_authority.registry_support_matrix
    with authority.operation() as initial:
        first_pin = initial.pin()
        expected = canonical_query(operation=initial).model_dump(mode="json")

    def cut_over_and_query(*, operation: PinnedAuthorityOperation) -> object:
        assert operation.pin() == first_pin
        second = publish_authority_artifact(second_artifact)
        assert second.logical_generation != first.logical_generation
        assert operation.profile_decode_context().generation == first_pin
        return canonical_query(operation=operation)

    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", authority)
    monkeypatch.setattr(mcp_authority, "registry_support_matrix", cut_over_and_query)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            result = await client.call_tool("authority", {"query": "support"})
            assert result.is_error is False
            assert result.structured_content == {
                "outcome": "published",
                "logical_generation": first_pin.logical_generation,
                "reader_incarnation": first_pin.reader_incarnation,
                "report": expected,
            }
            monkeypatch.setattr(mcp_authority, "registry_support_matrix", canonical_query)
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

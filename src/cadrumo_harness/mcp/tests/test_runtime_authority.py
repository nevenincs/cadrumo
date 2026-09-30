"""MCP authority queries retain canonical registry data and publication identity."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.modelo.registry_discovery import registry_support_matrix
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry import authority as authority_module
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityGenerationPin
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.server import RuntimeMcpAdapter

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DESCRIPTOR_NAME = "authority.current.json"


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
    canonical_query = mcp_server.registry_describe_modelo_for_registry_scope
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

    monkeypatch.setattr(mcp_server, "registry_describe_modelo_for_registry_scope", record_pin_and_run_query)
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
            result = await adapter.call("authority", {"query": "support"})
    finally:
        await adapter.close()

    assert result == {"outcome": "refused", "code": "published_authority_unavailable"}


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
    source_descriptor = authority_module.bundled_authority_descriptor_path()
    _copy_and_corrupt_published_database(source_descriptor, tmp_path)
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)

    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        with override_settings(cadrumo_authority_root=tmp_path):
            result = await adapter.call("authority", {"query": "support"})
    finally:
        await adapter.close()

    assert result == {"outcome": "refused", "code": "published_authority_invalid"}

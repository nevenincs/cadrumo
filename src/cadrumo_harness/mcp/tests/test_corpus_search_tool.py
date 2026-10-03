"""MCP corpus grounding search over the shipped corpus, handbook and published citations."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.corpus_search import runtime as corpus_runtime
from cadrumo.application.corpus_search.citation_lookup import bundled_citation_lookup
from cadrumo.application.corpus_search.lexical_index import bundled_corpus_html_root
from cadrumo.application.corpus_search.models import RetrievalResponse
from cadrumo.application.corpus_search.terminology import search_terminology
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry import authority as authority_module
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityGenerationPin
from cadrumo_harness.mcp import corpus_query as mcp_corpus
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# LGT art. 27 carries the recargo for late filing; the other article is a
# distractor that shares no recargo vocabulary.
_SAMPLE_STEMS = ("ley-58-2003-art-27", "ley-27-2014-art-7")
_CITATION_ID = "ley-58-2003:art-27.2"


@pytest.fixture
def sample_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Serve a small real corpus subset through an isolated index cache."""
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    for stem in _SAMPLE_STEMS:
        name = f"{stem}.html.extracted.json"
        shutil.copy2(bundled_corpus_html_root() / name, corpus_root / name)
    monkeypatch.setattr(corpus_runtime, "bundled_corpus_html_root", lambda: corpus_root)
    with override_settings(cadrumo_corpus_search_cache_dir=tmp_path / "index"):
        yield tmp_path / "index"


@pytest.mark.anyio
@pytest.mark.usefixtures("sample_corpus")
async def test_unauthenticated_connection_grounds_a_query_in_corpus_and_terminology() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            schema = tools["corpus_search"].input_schema
            assert schema["required"] == ["query"]
            assert schema["properties"]["limit"] == {"type": "integer", "minimum": 1, "maximum": 50}

            result = await client.call_tool("corpus_search", {"query": "recargo", "limit": 3})

        assert result.is_error is False
        found = result.structured_content
        assert found is not None
        assert found["outcome"] == "found"
        retrieval = RetrievalResponse.model_validate_json(json.dumps(found["retrieval"]))
        assert retrieval.mode == "lexical_only"
        assert 0 < len(retrieval.hits) <= 3
        assert {hit.corpus_ref.partition("#")[0] for hit in retrieval.hits} == {
            "corpus/normatives/html/ley-58-2003-art-27.html"
        }
        assert all("recargo" in hit.text.lower() for hit in retrieval.hits)
        with bundled_indexed_authority().operation() as operation:
            expected = corpus_runtime.search_corpus("recargo", operation=operation, limit=3)
            assert found["logical_generation"] == operation.pin().logical_generation
        assert retrieval == expected

        terminology = [hit.model_dump(mode="json") for hit in search_terminology("recargo", limit=3)]
        assert terminology
        assert "iva-recargo-equivalencia" in {hit["concept_id"] for hit in terminology}
        assert found["terminology"] == terminology
        assert adapter.client is None
    finally:
        await adapter.close()


@pytest.mark.anyio
@pytest.mark.usefixtures("sample_corpus")
async def test_exact_citation_returns_published_verbatim_evidence() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        result = await adapter.call("corpus_search", {"query": _CITATION_ID})
    finally:
        await adapter.close()

    assert result["outcome"] == "found"
    retrieval = RetrievalResponse.model_validate_json(json.dumps(result["retrieval"]))
    assert retrieval.mode == "citation"
    assert retrieval.hits == ()
    assert retrieval.citation is not None
    with bundled_indexed_authority().operation() as operation:
        published = bundled_citation_lookup((_CITATION_ID,), operation=operation).resolve(_CITATION_ID)
    assert retrieval.citation == published
    assert "extempor" in retrieval.citation.verbatim_text.lower()


@pytest.mark.anyio
@pytest.mark.usefixtures("sample_corpus")
async def test_reported_generation_is_the_pin_the_citation_lookup_used(monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = mcp_corpus.search_corpus
    observed: list[AuthorityGenerationPin] = []

    def record_pin(query: str, *, operation: PinnedAuthorityOperation, limit: int) -> RetrievalResponse:
        observed.append(operation.pin())
        return canonical(query, operation=operation, limit=limit)

    monkeypatch.setattr(mcp_corpus, "search_corpus", record_pin)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        result = await adapter.call("corpus_search", {"query": _CITATION_ID})
    finally:
        await adapter.close()

    assert result["outcome"] == "found"
    assert len(observed) == 1
    assert result["logical_generation"] == observed[0].logical_generation
    assert result["reader_incarnation"] == observed[0].reader_incarnation


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("args", "code"),
    (
        ({"query": "   "}, "query_empty"),
        ({"query": "¿?"}, "query_has_no_searchable_terms"),
        ({"query": "recargo", "limit": 0}, "invalid_request"),
        ({"query": "recargo", "limit": 51}, "invalid_request"),
        ({"query": "recargo", "locale": "en"}, "invalid_request"),
        ({}, "invalid_request"),
    ),
)
@pytest.mark.usefixtures("sample_corpus")
async def test_invalid_corpus_queries_refuse_with_typed_codes(args: dict[str, object], code: str) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            refused = await client.call_tool("corpus_search", args)
        assert refused.is_error is True
        assert refused.structured_content == {"outcome": "refused", "code": code}
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_missing_published_authority_refuses_before_any_corpus_index_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_corpus: Path
) -> None:
    unpublished = tmp_path / "unpublished"
    unpublished.mkdir()
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        with override_settings(cadrumo_authority_root=unpublished):
            async with connected_server_and_client_session(build_server(adapter)) as client:
                refused = await client.call_tool("corpus_search", {"query": "recargo"})
        assert refused.is_error is True
        assert refused.structured_content == {"outcome": "refused", "code": "published_authority_unavailable"}
    finally:
        await adapter.close()
    assert not sample_corpus.exists()

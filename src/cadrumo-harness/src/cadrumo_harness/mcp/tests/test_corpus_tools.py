"""Real-behavior tests for the corpus grounding tool."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from cadrumo.application.corpus_search import (
    CitationResolution,
    RetrievalHit,
    RetrievalMode,
    RetrievalResponse,
    build_lexical_index,
    bundled_corpus_html_root,
    corpus_index_path,
    iter_corpus_chunks,
)
from cadrumo.core.config import override_settings

from .._corpus_tools import (
    CORPUS_SEARCH_TOOL,
    CorpusCitationResult,
    CorpusSearchPayload,
    build_corpus_search_payload,
    build_corpus_search_tool,
    corpus_search_payload_from_response,
    corpus_uri,
    render_corpus_search_text,
)
from .._resources import read_harness_resource

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _hit(chunk_id: str, score: float) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        corpus_ref=f"corpus/normatives/html/{chunk_id}.html#a1",
        doc_title="Artículo de prueba",
        text="  Los recargos por declaración extemporánea son prestaciones accesorias.  ",
        score=score,
        rank=0,
        lexical_rank=0,
    )


def test_payload_maps_ranked_hits_with_corpus_uris() -> None:
    response = RetrievalResponse(
        query="recargo",
        mode=RetrievalMode.LEXICAL_ONLY,
        hits=(_hit("a", 0.5), _hit("b", 0.25)),
    )
    payload = corpus_search_payload_from_response(response)
    assert payload.mode is RetrievalMode.LEXICAL_ONLY
    assert len(payload.results) == 2
    assert payload.results[0].uri == corpus_uri("corpus/normatives/html/a.html#a1")
    assert payload.results[0].snippet.startswith("Los recargos")
    assert payload.citation is None


def test_payload_maps_citation_short_circuit() -> None:
    resolution = CitationResolution(
        citation_id="ley-58-2003:art-27.2",
        document_id="BOE-A-2003-23186",
        kind="ley",
        corpus_ref="corpus/normatives/html/ley-58-2003-art-27.html#a27-2",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a27",
        anchor="a27-2",
        verbatim_text="Los recargos por declaración extemporánea…",
    )
    response = RetrievalResponse(query="ley-58-2003:art-27.2", mode=RetrievalMode.CITATION, citation=resolution)
    payload = corpus_search_payload_from_response(response)
    assert payload.mode is RetrievalMode.CITATION
    assert payload.results == ()
    assert payload.citation is not None
    assert payload.citation.document_id == "BOE-A-2003-23186"
    assert payload.citation.uri == corpus_uri("ley-58-2003:art-27.2")


def _citation_result() -> CorpusCitationResult:
    return CorpusCitationResult(
        citation_id="ley-58-2003:art-27.2",
        document_id="BOE-A-2003-23186",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a27",
        uri=corpus_uri("ley-58-2003:art-27.2"),
        snippet="Los recargos por declaración extemporánea…",
    )


def test_citation_payload_without_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        CorpusSearchPayload(query="ley-58-2003:art-27.2", mode=RetrievalMode.CITATION, citation=None)


def test_citation_payload_carrying_lexical_results_is_refused() -> None:
    from .._corpus_tools import CorpusSearchResultRow

    with pytest.raises(ValidationError):
        CorpusSearchPayload(
            query="ley-58-2003:art-27.2",
            mode=RetrievalMode.CITATION,
            citation=_citation_result(),
            results=(
                CorpusSearchResultRow(
                    corpus_ref="corpus/normatives/html/a.html#a1",
                    title="Artículo de prueba",
                    snippet="texto",
                    score=0.5,
                    uri=corpus_uri("corpus/normatives/html/a.html#a1"),
                ),
            ),
        )


def test_lexical_only_payload_carrying_a_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        CorpusSearchPayload(query="recargo", mode=RetrievalMode.LEXICAL_ONLY, citation=_citation_result())


def test_render_text_lists_results_and_uris() -> None:
    response = RetrievalResponse(query="recargo", mode=RetrievalMode.LEXICAL_ONLY, hits=(_hit("a", 0.5),))
    text = render_corpus_search_text(corpus_search_payload_from_response(response))
    assert "corpus results for 'recargo'" in text
    assert "cadrumo://corpus/" in text


def test_tool_descriptor_is_read_only_with_query_input() -> None:
    tool = cast("Any", build_corpus_search_tool())
    assert tool.name == CORPUS_SEARCH_TOOL
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False
    assert "query" in tool.input_schema["required"]
    assert tool.input_schema["additionalProperties"] is False


def _seed_small_index(source_stem: str) -> None:
    # Pre-seed the runtime cache index with a small real subset so the tool test
    # does not pay the full-corpus first-build cost (that build is a first-run
    # concern, not under test here); the bundled citation lookup resolves the
    # citation query regardless of index contents.
    database_path = corpus_index_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_dir = database_path.parent / "src"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    source = bundled_corpus_html_root()
    for suffix in (".html.extracted.json", ".html.extracted.md"):
        origin = source / f"{source_stem}{suffix}"
        if origin.is_file():
            shutil.copy2(origin, corpus_dir / origin.name)
    build_lexical_index(database_path, iter_corpus_chunks(corpus_dir))


def test_build_payload_runs_real_retrieval_citation(tmp_path: Path) -> None:
    # End-to-end through the runtime service and a real (pre-seeded) index; the
    # citation query short-circuits to the bundled verbatim text.
    with override_settings(cadrumo_local_storage_root=tmp_path):
        _seed_small_index("ley-58-2003-art-27")
        payload = build_corpus_search_payload("ley-58-2003:art-27.2", limit=5)
    assert payload.mode is RetrievalMode.CITATION
    assert payload.citation is not None
    assert "extempor" in payload.citation.snippet.lower()


def test_citation_uri_round_trips_from_search_payload_to_resource_resolver() -> None:
    resolution = CitationResolution(
        citation_id="ley-58-2003:art-27.2",
        document_id="BOE-A-2003-23186",
        kind="ley",
        corpus_ref="corpus/normatives/html/ley-58-2003-art-27.html#a27-2",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a27",
        anchor="a27-2",
        verbatim_text="Los recargos por declaración extemporánea…",
    )
    response = RetrievalResponse(
        query=resolution.citation_id,
        mode=RetrievalMode.CITATION,
        citation=resolution,
    )
    payload = corpus_search_payload_from_response(response)
    assert payload.citation is not None

    resource = read_harness_resource(payload.citation.uri)

    assert resource.ref.uri == payload.citation.uri
    assert "extempor" in resource.text.lower()


def test_build_payload_runs_real_lexical_retrieval(tmp_path: Path) -> None:
    # A free-text query over the pre-seeded index returns ranked hits with
    # corpus URIs. The shipped surface has one retrieval shape on every host —
    # no extra to probe, no model to resolve — so this needs no environment
    # seam to stay deterministic.
    with override_settings(cadrumo_local_storage_root=tmp_path):
        _seed_small_index("ley-58-2003-art-27")
        payload = build_corpus_search_payload("recargo declaración extemporánea", limit=5)
    assert payload.mode is RetrievalMode.LEXICAL_ONLY
    assert payload.results
    assert payload.results[0].uri.startswith("cadrumo://corpus/")

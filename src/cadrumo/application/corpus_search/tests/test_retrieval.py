"""Real-behavior tests for corpus retrieval.

The FTS5 lexical ranking, the citation short-circuit, and the input boundaries
are exercised over a small real corpus index. The retrieval surface ships no
semantic half, so there is no second side to cover and no degraded mode to
distinguish from the shipped one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ..errors import CorpusSearchInputError
from .._lexical_index import build_lexical_index, iter_corpus_chunks
from .._models import CitationResolution, RetrievalHit, RetrievalMode, RetrievalResponse
from .._retrieval import run_retrieval
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _index_and_chunks(tmp_path: Path) -> tuple[Path, list[str]]:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunks = list(iter_corpus_chunks(corpus))
    database_path = tmp_path / "index.sqlite"
    build_lexical_index(database_path, chunks)
    return database_path, [chunk.chunk_id for chunk in chunks]


def test_ranked_lexical_hits_for_a_prose_query(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    response = run_retrieval("recargo declaración extemporánea", database_path=database_path, limit=5)
    assert response.mode is RetrievalMode.LEXICAL_ONLY
    assert response.hits
    # The ref is ``path#anchor``: the citation resolver splits the fragment off
    # before opening the file, so both halves are asserted here -- a dropped or
    # altered anchor would still resolve to a file but to the wrong unit.
    assert response.hits[0].corpus_ref == "corpus/normatives/html/ley-58-2003-art-27.html#a27"
    assert response.hits[0].lexical_rank == 0
    # Rank mirrors the lexical order and the score is a positive, strictly
    # decreasing BM25 relevance, so the page is ordered best-first.
    assert [hit.rank for hit in response.hits] == list(range(len(response.hits)))
    scores = [hit.score for hit in response.hits]
    assert all(score > 0.0 for score in scores)
    assert scores == sorted(scores, reverse=True)


def test_limit_caps_the_returned_page(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    unbounded = run_retrieval("declaración", database_path=database_path, limit=50)
    assert len(unbounded.hits) > 1, "fixture must match more than one chunk for the cap to mean anything"
    capped = run_retrieval("declaración", database_path=database_path, limit=1)
    assert len(capped.hits) == 1
    assert capped.hits[0].chunk_id == unbounded.hits[0].chunk_id


def test_citation_short_circuit(tmp_path: Path) -> None:
    from .._citation_lookup import bundled_citation_lookup

    database_path, _ids = _index_and_chunks(tmp_path)
    response = run_retrieval(
        "ley-58-2003:art-27.2",
        database_path=database_path,
        citation_lookup=bundled_citation_lookup(),
        limit=5,
    )
    assert response.mode is RetrievalMode.CITATION
    assert response.citation is not None
    assert response.citation.document_id == "BOE-A-2003-23186"
    assert "extempor" in response.citation.verbatim_text.lower()
    assert response.hits == ()


def test_empty_query_refused(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        run_retrieval("   ", database_path=database_path)


def test_nonpositive_limit_refused(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        run_retrieval("recargo", database_path=database_path, limit=0)


def _citation() -> CitationResolution:
    return CitationResolution(
        citation_id="ley-58-2003:art-27.2",
        document_id="BOE-A-2003-23186",
        kind="ley",
        corpus_ref="corpus/normatives/html/ley-58-2003-art-27.html#a27-2",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a27",
        anchor="a27-2",
        verbatim_text="Los recargos por declaración extemporánea…",
    )


def _hit() -> RetrievalHit:
    return RetrievalHit(
        chunk_id="a",
        corpus_ref="corpus/normatives/html/a.html#a1",
        doc_title="Artículo de prueba",
        text="texto de prueba",
        score=0.5,
        rank=0,
        lexical_rank=0,
    )


def test_citation_response_without_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        RetrievalResponse(query="ley-58-2003:art-27.2", mode=RetrievalMode.CITATION, citation=None)


def test_citation_response_carrying_lexical_hits_is_refused() -> None:
    with pytest.raises(ValidationError):
        RetrievalResponse(
            query="ley-58-2003:art-27.2",
            mode=RetrievalMode.CITATION,
            citation=_citation(),
            hits=(_hit(),),
        )


def test_lexical_only_response_carrying_a_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        RetrievalResponse(query="recargo", mode=RetrievalMode.LEXICAL_ONLY, citation=_citation())


def test_valid_citation_and_lexical_responses_round_trip() -> None:
    citation_response = RetrievalResponse(
        query="ley-58-2003:art-27.2", mode=RetrievalMode.CITATION, citation=_citation()
    )
    assert citation_response.citation is not None
    assert citation_response.hits == ()

    lexical_response = RetrievalResponse(query="recargo", mode=RetrievalMode.LEXICAL_ONLY, hits=(_hit(),))
    assert lexical_response.citation is None
    assert lexical_response.hits == (_hit(),)

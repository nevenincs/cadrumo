"""Real-behavior tests for corpus retrieval.

The FTS5 lexical ranking, the citation short-circuit, and the input boundaries
are exercised over a small real corpus index. The retrieval surface ships no
semantic half, so there is no second side to cover and no degraded mode to
distinguish from the shipped one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._errors import CorpusSearchInputError
from .._lexical_index import build_lexical_index, iter_corpus_chunks
from .._models import RetrievalMode
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
    assert response.hits[0].corpus_ref.endswith("ley-58-2003-art-27.html")
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

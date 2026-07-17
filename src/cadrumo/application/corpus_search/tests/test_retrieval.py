"""Real-behavior tests for hybrid retrieval and RRF fusion.

The FTS5 lexical, citation short-circuit, and input boundaries are exercised
over a small real corpus index. The semantic side is covered separately by
``test_hybrid_real_model_recall.py`` through the pinned production model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._errors import CorpusSearchInputError
from .._lexical_index import build_lexical_index, iter_corpus_chunks
from .._models import RetrievalMode
from .._retrieval import hybrid_search
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _index_and_chunks(tmp_path: Path) -> tuple[Path, list[str]]:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunks = list(iter_corpus_chunks(corpus))
    database_path = tmp_path / "index.sqlite"
    build_lexical_index(database_path, chunks)
    return database_path, [chunk.chunk_id for chunk in chunks]


def test_lexical_only_when_no_embeddings(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    response = hybrid_search("recargo declaración extemporánea", database_path=database_path, limit=5)
    assert response.mode is RetrievalMode.LEXICAL_ONLY
    assert response.hits
    assert response.hits[0].corpus_ref.endswith("ley-58-2003-art-27.html")
    assert response.hits[0].semantic_rank is None
    assert response.hits[0].lexical_rank == 0


def test_citation_short_circuit(tmp_path: Path) -> None:
    from .._citation_lookup import bundled_citation_lookup

    database_path, _ids = _index_and_chunks(tmp_path)
    response = hybrid_search(
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
        hybrid_search("   ", database_path=database_path)


def test_nonpositive_limit_refused(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        hybrid_search("recargo", database_path=database_path, limit=0)

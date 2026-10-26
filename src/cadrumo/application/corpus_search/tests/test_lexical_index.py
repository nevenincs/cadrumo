"""Real-behavior tests for the FTS5 lexical corpus index."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..errors import CorpusSearchInputError
from ..lexical_index import build_lexical_index, iter_corpus_chunks, search_lexical
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _sample_index(tmp_path: Path) -> Path:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunks = list(iter_corpus_chunks(corpus))
    assert chunks, "sample corpus produced no chunks"
    database_path = tmp_path / "index.sqlite"
    result = build_lexical_index(database_path, chunks)
    assert result.chunk_count == len(chunks)
    assert result.document_count == 3
    return database_path


def test_chunk_ids_are_stable_and_unique(tmp_path: Path) -> None:
    corpus = build_sample_corpus(tmp_path / "corpus")
    first = [chunk.chunk_id for chunk in iter_corpus_chunks(corpus)]
    second = [chunk.chunk_id for chunk in iter_corpus_chunks(corpus)]
    assert first == second, "chunk ids must be deterministic across passes"
    assert len(first) == len(set(first)), "chunk ids must be unique"


def test_chunks_carry_corpus_ref_provenance(tmp_path: Path) -> None:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunks = list(iter_corpus_chunks(corpus))
    art27 = [c for c in chunks if c.source_path.endswith("ley-58-2003-art-27.html")]
    assert art27, "expected chunks from the LGT art. 27 source"
    for chunk in art27:
        assert chunk.corpus_ref.startswith("corpus/normatives/html/ley-58-2003-art-27.html")
        assert chunk.text.strip()


def test_search_finds_recargo_extemporanea(tmp_path: Path) -> None:
    database_path = _sample_index(tmp_path)
    hits = search_lexical(database_path, "recargo declaración extemporánea", limit=5)
    assert hits, "expected lexical hits for the recargo query"
    assert hits[0].corpus_ref.startswith("corpus/normatives/html/ley-58-2003-art-27.html")
    assert "extempor" in hits[0].text.lower()
    assert [hit.rank for hit in hits] == list(range(len(hits)))


def test_search_folds_diacritics(tmp_path: Path) -> None:
    database_path = _sample_index(tmp_path)
    # Query without the accent must still match "declaración" via the
    # unicode61 remove_diacritics 2 tokenizer.
    accented = search_lexical(database_path, "declaración", limit=5)
    folded = search_lexical(database_path, "declaracion", limit=5)
    assert accented, "accented query returned nothing"
    assert {hit.chunk_id for hit in folded} == {hit.chunk_id for hit in accented}


def test_search_stemmed_column_recovers_inflection(tmp_path: Path) -> None:
    database_path = _sample_index(tmp_path)
    # "extemporáneas" (plural) is not a literal token in the corpus; the
    # snowball-stemmed column recovers it against "extemporánea".
    hits = search_lexical(database_path, "recargos extemporáneas", limit=5)
    assert hits, "stemmed recall should recover the inflected query"
    art27 = [hit for hit in hits if hit.corpus_ref.partition("#")[0].endswith("ley-58-2003-art-27.html")]
    assert art27, "stemmed recall should reach the LGT art. 27 document"
    # Pin the whole ``path#anchor`` ref, not just the path: the citation
    # resolver splits the fragment off before opening the file, so a dropped
    # anchor still names a readable file but the wrong extracted unit.
    assert {hit.corpus_ref for hit in art27} == {"corpus/normatives/html/ley-58-2003-art-27.html#a27"}


def test_empty_query_is_refused(tmp_path: Path) -> None:
    database_path = _sample_index(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        search_lexical(database_path, "   ", limit=5)


def test_non_positive_limit_is_refused(tmp_path: Path) -> None:
    database_path = _sample_index(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        search_lexical(database_path, "recargo", limit=0)


def test_bundled_corpus_yields_chunks() -> None:
    # The real bundled corpus (the shippable extracted triples) must yield
    # a non-trivial chunk set, or the grounding surface has nothing to index.
    count = sum(1 for _ in iter_corpus_chunks())
    assert count > 500, f"bundled corpus produced only {count} chunks"

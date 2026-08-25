"""Build-time FTS5 lexical index over the bundled BOE/AEAT corpus.

The index is the ranking half of the grounding surface, alongside the
exact-citation lookup. It is built from the already-bundled
``*.extracted.json`` corpus triples (the same triples the registry legal
catalogue grounds against, read through the :mod:`~core.resources`
boundary) into a caller-supplied SQLite path. No dependency beyond the
standard library ``sqlite3`` (FTS5 is present in every standard CPython
build) and the core ``snowballstemmer`` (a pure-Python Spanish Snowball
stemmer) is required, so this module imports and runs on every install.

Two searchable columns ride each chunk: ``text_folded`` (searched with
the ``unicode61 remove_diacritics 2`` tokenizer, so ``recargo`` matches
``recárgo`` and accents fold) and ``text_stemmed`` (the same prose
pre-stemmed with the Spanish Snowball stemmer, so ``declaraciones``
matches ``declaración``). FTS5's built-in ``porter`` stemmer is
English-only, which is why the Spanish stem rides its own precomputed
column.

Exact citation lookup ("art. 27.2 LGT") does NOT go through this index;
it is a structured key lookup over the registry legal catalogue (see
:mod:`~application.corpus_search._citation_lookup`). This index covers
in-prose concept recall.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

from ...core import (
    STR_KEYED_MAPPING_ADAPTER,
    fts_or_group,
    spanish_stemmer,
    spanish_word_tokens,
    stem_spanish_terms,
    stem_spanish_text,
)
from ...core.directory_scan import (
    scan_directory,
)
from ...core.external_constants import UTF_8_ENCODING
from ...core.resources import bundled_path
from ._models import CorpusChunk, CorpusDocument, CorpusIndexBuildResult, LexicalSearchHit

_CORPUS_HTML_PARTS = ("corpus", "normatives", "html")
_CORPUS_REF_PREFIX = "corpus/normatives/html"
_EXTRACTED_JSON_SUFFIX = ".html.extracted.json"

# Chunk sizing (characters). Prose is accumulated paragraph-by-paragraph
# toward the target and flushed before it would exceed the hard cap, so a
# chunk stays a coherent, retrievable span rather than a single sentence
# or a whole multi-page article.
_CHUNK_TARGET = 1200
_CHUNK_HARD_MAX = 1500


def bundled_corpus_html_root() -> Path:
    """Return the on-disk path of the bundled normatives HTML corpus."""
    return bundled_path(*_CORPUS_HTML_PARTS)


def iter_corpus_chunks(corpus_root: Path | None = None) -> Iterator[CorpusChunk]:
    """Yield deterministic :class:`CorpusChunk` records from the corpus.

    The corpus is walked in sorted filename order, and each extracted unit
    is split into paragraph-bounded chunks, so the same corpus always
    yields the same chunk sequence with the same ids.

    Args:
        corpus_root: Directory holding the ``*.html.extracted.json``
            triples. Defaults to the package-bundled corpus.

    Yields:
        One :class:`CorpusChunk` per prose chunk, in document then unit
        then chunk order.
    """
    root = corpus_root or bundled_corpus_html_root()
    for json_path in scan_directory(root, pattern="*" + _EXTRACTED_JSON_SUFFIX):
        yield from _chunks_for_source(json_path)


def _chunks_for_source(json_path: Path) -> Iterator[CorpusChunk]:
    payload = json.loads(json_path.read_text(encoding=UTF_8_ENCODING))
    units = payload.get("units") or ()
    if not units:
        return
    html_name = json_path.name.removesuffix(".extracted.json")
    html_stem = html_name.removesuffix(".html")
    corpus_ref_base = f"{_CORPUS_REF_PREFIX}/{html_name}"
    doc_title = _document_title(units, fallback=html_stem)
    global_ordinal = 0
    for unit_ordinal, unit in enumerate(units):
        text = (unit.get("text") or "").strip()
        if not text:
            continue
        anchor = _clean_anchor(unit.get("anchor"))
        section = _clean_optional(unit.get("section")) or _clean_optional(unit.get("title"))
        corpus_ref = corpus_ref_base + (f"#{anchor}" if anchor else "")
        for chunk_ordinal, chunk_text in enumerate(_chunk_prose(text)):
            yield CorpusChunk(
                chunk_id=f"{html_stem}:{unit_ordinal:03d}:{chunk_ordinal:02d}",
                corpus_ref=corpus_ref,
                source_path=f"{_CORPUS_REF_PREFIX}/{html_name}",
                doc_title=doc_title,
                section=section,
                anchor=anchor,
                ordinal=global_ordinal,
                text=chunk_text,
            )
            global_ordinal += 1


def _document_title(units: Iterable[object], *, fallback: str) -> str:
    for unit in units:
        if not isinstance(unit, dict):
            continue
        title = _clean_optional(STR_KEYED_MAPPING_ADAPTER.validate_python(unit).get("title"))
        if title:
            return title
    return fallback


def _clean_optional(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _clean_anchor(value: object) -> str | None:
    anchor = _clean_optional(value)
    if anchor is None:
        return None
    return anchor.lstrip("#") or None


def _chunk_prose(text: str) -> list[str]:
    paragraphs = [para.strip() for para in text.split("\n") if para.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        for piece in _split_oversized(para):
            piece_len = len(piece)
            if current and current_len + piece_len + 1 > _CHUNK_HARD_MAX:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(piece)
            current_len += piece_len + 1
            if current_len >= _CHUNK_TARGET:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
    if current:
        chunks.append("\n".join(current))
    return chunks


def _split_oversized(paragraph: str) -> list[str]:
    if len(paragraph) <= _CHUNK_HARD_MAX:
        return [paragraph]
    pieces: list[str] = []
    words = paragraph.split(" ")
    current: list[str] = []
    current_len = 0
    for word in words:
        word_len = len(word)
        if current and current_len + word_len + 1 > _CHUNK_HARD_MAX:
            pieces.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += word_len + 1
    if current:
        pieces.append(" ".join(current))
    return pieces


def build_lexical_index(
    database_path: Path,
    chunks: Iterable[CorpusChunk],
) -> CorpusIndexBuildResult:
    """Build the FTS5 lexical index at ``database_path`` from ``chunks``.

    The database is created fresh (any existing tables are dropped) so the
    build is deterministic and idempotent: the same corpus produces a
    byte-stable chunk id sequence and an equivalent index.

    Args:
        database_path: SQLite file to (re)build. Parent directories must
            exist.
        chunks: The chunk sequence to index, typically
            :func:`iter_corpus_chunks`.

    Returns:
        A :class:`CorpusIndexBuildResult` with the document and chunk counts.
    """
    stemmer = spanish_stemmer()
    connection = sqlite3.connect(database_path)
    try:
        _create_schema(connection)
        chunk_counts: dict[str, int] = {}
        titles: dict[str, str] = {}
        chunk_count = 0
        for rowid, chunk in enumerate(chunks, start=1):
            connection.execute(
                "INSERT INTO chunks"
                "(rowid, chunk_id, corpus_ref, source_path, doc_title, section, anchor, ordinal, text)"
                " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rowid,
                    chunk.chunk_id,
                    chunk.corpus_ref,
                    chunk.source_path,
                    chunk.doc_title,
                    chunk.section,
                    chunk.anchor,
                    chunk.ordinal,
                    chunk.text,
                ),
            )
            connection.execute(
                "INSERT INTO chunks_fts(rowid, text_folded, text_stemmed) VALUES(?, ?, ?)",
                (rowid, chunk.text, stem_spanish_text(stemmer, chunk.text)),
            )
            chunk_counts[chunk.source_path] = chunk_counts.get(chunk.source_path, 0) + 1
            titles.setdefault(chunk.source_path, chunk.doc_title)
            chunk_count += 1
        for source_path in sorted(chunk_counts):
            document = CorpusDocument(
                corpus_ref=source_path,
                source_path=source_path,
                title=titles[source_path],
                chunk_count=chunk_counts[source_path],
            )
            connection.execute(
                "INSERT INTO documents(corpus_ref, source_path, title, chunk_count) VALUES(?, ?, ?, ?)",
                (document.corpus_ref, document.source_path, document.title, document.chunk_count),
            )
        connection.commit()
    finally:
        connection.close()
    return CorpusIndexBuildResult(
        database_path=Path(database_path).as_posix(),
        document_count=len(chunk_counts),
        chunk_count=chunk_count,
    )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS chunks_fts")
    connection.execute("DROP TABLE IF EXISTS chunks")
    connection.execute("DROP TABLE IF EXISTS documents")
    connection.execute(
        "CREATE TABLE chunks("
        "rowid INTEGER PRIMARY KEY, chunk_id TEXT NOT NULL, corpus_ref TEXT NOT NULL,"
        " source_path TEXT NOT NULL, doc_title TEXT NOT NULL, section TEXT, anchor TEXT,"
        " ordinal INTEGER NOT NULL, text TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE documents("
        "corpus_ref TEXT PRIMARY KEY, source_path TEXT NOT NULL, title TEXT NOT NULL, chunk_count INTEGER NOT NULL)"
    )
    connection.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "text_folded, text_stemmed, tokenize = 'unicode61 remove_diacritics 2')"
    )


def search_lexical(
    database_path: Path,
    query: str,
    *,
    limit: int = 10,
) -> tuple[LexicalSearchHit, ...]:
    """Return the top lexical-search hits for ``query``.

    The query is matched against both the diacritic-folded column (raw
    terms) and the Spanish-stemmed column (stemmed terms), unioned, and
    ranked by FTS5 BM25. This is the ranking primitive the retrieval
    module wraps with the exact-citation short-circuit; nothing is fused
    on top of it.

    Args:
        database_path: A lexical index built by :func:`build_lexical_index`.
        query: Free-text query.
        limit: Maximum number of hits to return.

    Returns:
        Up to ``limit`` :class:`LexicalSearchHit` records, best first.

    Raises:
        CorpusSearchInputError: If ``query`` carries no searchable terms or
            ``limit`` is not positive.
    """
    from .errors import CorpusSearchInputError

    if limit <= 0:
        raise CorpusSearchInputError(
            reason="limit_not_positive",
            context={"limit": limit},
        )
    folded_terms = spanish_word_tokens(query)
    if not folded_terms:
        raise CorpusSearchInputError(
            reason="query_has_no_searchable_terms",
            context={"query": query},
        )
    stemmed_terms = stem_spanish_terms(spanish_stemmer(), folded_terms)
    match_expression = f"text_folded : ({fts_or_group(folded_terms)}) OR text_stemmed : ({fts_or_group(stemmed_terms)})"
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(
            "SELECT c.chunk_id, c.corpus_ref, c.doc_title, c.section, c.anchor, c.text,"
            " bm25(chunks_fts) AS score"
            " FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid"
            " WHERE chunks_fts MATCH ? ORDER BY score, c.rowid LIMIT ?",
            (match_expression, limit),
        ).fetchall()
    finally:
        connection.close()
    return tuple(
        LexicalSearchHit(
            chunk_id=row[0],
            corpus_ref=row[1],
            doc_title=row[2],
            section=row[3],
            anchor=row[4],
            rank=rank,
            score=-float(row[6]),
            text=row[5],
        )
        for rank, row in enumerate(rows)
    )


__all__ = [
    "build_lexical_index",
    "bundled_corpus_html_root",
    "iter_corpus_chunks",
    "search_lexical",
]

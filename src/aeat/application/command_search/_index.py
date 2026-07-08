"""FTS5 lexical command index with a pure-Python degraded fallback.

Builds an in-memory SQLite FTS5 index over the command corpus and ranks a
free-text query by BM25 across two columns - a diacritic-folded column (so
``recargo`` matches ``recárgo``) and a Spanish-Snowball-stemmed column (so
``declaraciones`` matches ``declaración``) - unioned, exactly as the corpus
grounding index does. When FTS5 or the stemmer is unavailable the index falls
back to a deterministic token-overlap scorer over the same folded text, so the
``search`` meta-tool always ranks better than a bare substring match and never
hard-fails on a minimal install.

The index is SDK-independent and pure (it takes plain command documents), so it
is unit-tested directly without the MCP transport.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


class CommandDoc(BaseModel):
    """One command's searchable document.

    ``text`` is the concatenation of the fields a query should match - the
    command key, tool name, human description, per-verb help, and toolset - so
    a query token hitting any of them contributes to the rank.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    text: str = Field(min_length=1)


class CommandHit(BaseModel):
    """One ranked command match."""

    model_config = _STRICT_FROZEN

    command_key: str
    tool_name: str
    rank: int = Field(ge=0)
    score: float


def _spanish_stemmer() -> object | None:
    try:
        import snowballstemmer
    except ModuleNotFoundError:
        return None
    return snowballstemmer.stemmer("spanish")


def _stem_terms(stemmer: object | None, terms: Sequence[str]) -> list[str]:
    if stemmer is None or not terms:
        return list(terms)
    return list(stemmer.stemWords(list(terms)))  # type: ignore[attr-defined]


def _fts5_available() -> bool:
    try:
        connection = sqlite3.connect(":memory:")
    except sqlite3.Error:
        return False
    try:
        connection.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        connection.close()


def _fts_or_group(terms: Iterable[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return " OR ".join(f'"{term}"' for term in unique)


class CommandIndex:
    """A searchable index over the command corpus.

    Prefers an in-memory FTS5 index ranked by BM25; falls back to a
    deterministic token-overlap scorer over the folded text when FTS5 or the
    Spanish stemmer is unavailable. Either way :meth:`search` returns ranked
    :class:`CommandHit` records for a free-text query.
    """

    def __init__(self, docs: Sequence[CommandDoc]) -> None:
        self._docs = tuple(docs)
        self._stemmer = _spanish_stemmer()
        self._connection: sqlite3.Connection | None = None
        if _fts5_available():
            self._connection = self._build_fts(self._docs)

    def _build_fts(self, docs: Sequence[CommandDoc]) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.execute(
            "CREATE TABLE commands(rowid INTEGER PRIMARY KEY, command_key TEXT NOT NULL, tool_name TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE VIRTUAL TABLE commands_fts USING fts5("
            "text_folded, text_stemmed, tokenize = 'unicode61 remove_diacritics 2')"
        )
        for rowid, doc in enumerate(docs, start=1):
            connection.execute(
                "INSERT INTO commands(rowid, command_key, tool_name) VALUES(?, ?, ?)",
                (rowid, doc.command_key, doc.tool_name),
            )
            folded = doc.text.lower()
            stemmed = " ".join(_stem_terms(self._stemmer, _WORD_RE.findall(folded)))
            connection.execute(
                "INSERT INTO commands_fts(rowid, text_folded, text_stemmed) VALUES(?, ?, ?)",
                (rowid, doc.text, stemmed),
            )
        connection.commit()
        return connection

    def search(self, query: str, *, limit: int = 20) -> tuple[CommandHit, ...]:
        """Return up to ``limit`` ranked command hits for ``query``.

        A blank query or one with no searchable terms returns no hits. The FTS5
        path ranks by BM25 across the folded and stemmed columns; the degraded
        path scores by unique-term overlap over the folded text.
        """
        folded_terms = _WORD_RE.findall(query.lower())
        if not folded_terms or limit <= 0:
            return ()
        if self._connection is not None:
            return self._search_fts(folded_terms, limit=limit)
        return self._search_degraded(folded_terms, limit=limit)

    def _search_fts(self, folded_terms: Sequence[str], *, limit: int) -> tuple[CommandHit, ...]:
        assert self._connection is not None
        stemmed_terms = _stem_terms(self._stemmer, folded_terms)
        match = f"text_folded : ({_fts_or_group(folded_terms)}) OR text_stemmed : ({_fts_or_group(stemmed_terms)})"
        rows = self._connection.execute(
            "SELECT c.command_key, c.tool_name, bm25(commands_fts) AS score"
            " FROM commands_fts JOIN commands c ON c.rowid = commands_fts.rowid"
            " WHERE commands_fts MATCH ? ORDER BY score, c.rowid LIMIT ?",
            (match, limit),
        ).fetchall()
        return tuple(
            CommandHit(command_key=row[0], tool_name=row[1], rank=rank, score=-float(row[2]))
            for rank, row in enumerate(rows)
        )

    def _search_degraded(self, folded_terms: Sequence[str], *, limit: int) -> tuple[CommandHit, ...]:
        wanted = set(folded_terms)
        scored: list[tuple[int, int, CommandDoc]] = []
        for ordinal, doc in enumerate(self._docs):
            doc_terms = set(_WORD_RE.findall(doc.text.lower()))
            overlap = len(wanted & doc_terms)
            if overlap:
                scored.append((overlap, ordinal, doc))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(
            CommandHit(command_key=doc.command_key, tool_name=doc.tool_name, rank=rank, score=float(overlap))
            for rank, (overlap, _ordinal, doc) in enumerate(scored[:limit])
        )


def build_command_index(docs: Iterable[CommandDoc]) -> CommandIndex:
    """Build a :class:`CommandIndex` from the command documents."""
    return CommandIndex(tuple(docs))

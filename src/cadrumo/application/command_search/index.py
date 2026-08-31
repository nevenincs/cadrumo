"""Lexical command index: per-column BM25 over the command corpus.

Ranks a free-text query against the command corpus so the ``search`` meta-tool
bridges the operator's natural vocabulary to a command's own tokens:

* a per-column FTS5 lexical index that weights the command KEY and TOOL NAME
  above curated OUTCOME ALIASES above the human DESCRIPTION above the per-verb
  HELP, so a homonym token in a low-value column no longer outranks the correct
  command whose key carries it (the ``import`` mis-rank the review found);
* Spanish stemming and diacritics folding on every column, so a morphological
  or accent variant still recalls its command.

When SQLite FTS5 is unavailable :meth:`CommandIndex.search` degrades cleanly to
a pure-Python token-overlap scorer, so a minimal install always ranks better
than a bare substring match and never hard-fails. The index loads no model and
reaches no network on any install.

The index is SDK-independent and pure (it takes plain command documents), so it
is unit-tested directly without any consuming transport.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from ...core.spanish_stemming import SpanishStemmer, spanish_stemmer, spanish_word_tokens, stem_spanish_terms
from ...core.fts_query import fts_or_group

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: Query tokens shorter than this carry no discriminative signal (the article
#: ``a``, the conjunctions ``y``/``o``, a stray ``I``) yet spuriously match a
#: long help column, so they are dropped from the query before ranking.
_MIN_TERM_LEN = 2

#: Per-column BM25 weights, descending by discriminative value: the command key
#: and tool name carry the verb-level vocabulary and rank highest; curated
#: outcome aliases rank the composite verbs on outcome-phrased queries; the human
#: description ranks above the per-verb CLI help, which is the noisiest column.
_BM25_WEIGHT_KEY = 8.0
_BM25_WEIGHT_DESCRIPTION = 4.0
_BM25_WEIGHT_ALIASES = 6.0
_BM25_WEIGHT_HELP = 1.0


class CommandDoc(BaseModel):
    """One command's searchable document, split into weighted columns.

    The four tiers rank a query hit by WHERE it lands: ``key_and_name`` (the
    command key tokens and tool name) is the most discriminative, ``aliases``
    carries curated outcome vocabulary for composite verbs, ``description`` is
    the human summary, and ``help`` is the per-verb CLI help — the noisiest
    tier. Each tier becomes its own BM25-weighted FTS5 column; a query token
    hitting the key ranks above the same token hitting the help.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    key_and_name: str = Field(min_length=1)
    description: str = ""
    aliases: str = ""
    help: str = ""

    @property
    def combined_text(self) -> str:
        """The union of every tier, for the degraded token-overlap fallback."""
        parts = (self.key_and_name, self.description, self.aliases, self.help)
        return " ".join(part for part in parts if part)


class CommandHit(BaseModel):
    """One ranked command match."""

    model_config = _STRICT_FROZEN

    command_key: str
    tool_name: str
    rank: int = Field(ge=0)
    score: float


def _column_text(stemmer: SpanishStemmer, raw: str) -> str:
    """Store a tier as raw plus stemmed text so one column matches both forms.

    Keeps the raw (diacritics-folded by the tokenizer) text alongside its
    Spanish-stemmed tokens, so one column matches both an exact/accented query
    term and a morphological variant without a second column per tier.
    """
    stemmed = " ".join(stem_spanish_terms(stemmer, spanish_word_tokens(raw)))
    return f"{raw} {stemmed}".strip()


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


class CommandIndex:
    """A lexical searchable index over the command corpus.

    Ranks by per-column FTS5 BM25, degrading cleanly to a pure-Python
    token-overlap scorer when FTS5 is absent, so a minimal install keeps a
    working ``search``. :meth:`search` returns ranked :class:`CommandHit`
    records for a free-text query.
    """

    def __init__(self, docs: Sequence[CommandDoc]) -> None:
        """Build the index over ``docs``, keeping them in their given order."""
        self._docs = tuple(docs)
        self._stemmer = spanish_stemmer()
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
            "key_and_name, description, aliases, help, tokenize = 'unicode61 remove_diacritics 2')"
        )
        for rowid, doc in enumerate(docs, start=1):
            connection.execute(
                "INSERT INTO commands(rowid, command_key, tool_name) VALUES(?, ?, ?)",
                (rowid, doc.command_key, doc.tool_name),
            )
            connection.execute(
                "INSERT INTO commands_fts(rowid, key_and_name, description, aliases, help) VALUES(?, ?, ?, ?, ?)",
                (
                    rowid,
                    _column_text(self._stemmer, doc.key_and_name),
                    _column_text(self._stemmer, doc.description),
                    _column_text(self._stemmer, doc.aliases),
                    _column_text(self._stemmer, doc.help),
                ),
            )
        connection.commit()
        return connection

    def search(self, query: str, *, limit: int = 20) -> tuple[CommandHit, ...]:
        """Return up to ``limit`` ranked command hits for ``query``.

        A blank query or one with no searchable terms returns no hits. The
        matching commands are ranked by per-column BM25, or by token overlap
        when FTS5 is absent. ``score`` is the reciprocal of the one-based rank,
        so it is positive and strictly decreasing across the page on either
        path (the two paths' own scales are not comparable, so neither is
        surfaced raw).
        """
        folded_terms = [term for term in spanish_word_tokens(query) if len(term) >= _MIN_TERM_LEN]
        if not folded_terms or limit <= 0:
            return ()
        ranked_keys = self._lexical_ranked_keys(folded_terms)[:limit]
        tool_name_by_key = {doc.command_key: doc.tool_name for doc in self._docs}
        return tuple(
            CommandHit(
                command_key=key,
                tool_name=tool_name_by_key[key],
                rank=rank,
                score=1.0 / (rank + 1),
            )
            for rank, key in enumerate(ranked_keys)
        )

    def _lexical_ranked_keys(self, folded_terms: Sequence[str]) -> list[str]:
        """Return the lexically-matched command keys, best first (the candidate set)."""
        if self._connection is not None:
            return self._search_fts_keys(folded_terms)
        return self._search_degraded_keys(folded_terms)

    def _search_fts_keys(self, folded_terms: Sequence[str]) -> list[str]:
        assert self._connection is not None
        stemmed_terms = stem_spanish_terms(self._stemmer, folded_terms)
        match = fts_or_group([*folded_terms, *stemmed_terms])
        if not match:
            return []
        # The per-column BM25 weights ride as bind parameters (the column order is
        # key_and_name, description, aliases, help), so no value is interpolated
        # into the SQL text.
        rows = self._connection.execute(
            "SELECT c.command_key, bm25(commands_fts, ?, ?, ?, ?) AS score"
            " FROM commands_fts JOIN commands c ON c.rowid = commands_fts.rowid"
            " WHERE commands_fts MATCH ? ORDER BY score, c.rowid",
            (_BM25_WEIGHT_KEY, _BM25_WEIGHT_DESCRIPTION, _BM25_WEIGHT_ALIASES, _BM25_WEIGHT_HELP, match),
        ).fetchall()
        return [row[0] for row in rows]

    def _search_degraded_keys(self, folded_terms: Sequence[str]) -> list[str]:
        wanted = set(folded_terms)
        scored: list[tuple[int, int, str]] = []
        for ordinal, doc in enumerate(self._docs):
            doc_terms = set(spanish_word_tokens(doc.combined_text))
            overlap = len(wanted & doc_terms)
            if overlap:
                scored.append((overlap, ordinal, doc.command_key))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [command_key for _overlap, _ordinal, command_key in scored]


def build_command_index(docs: Iterable[CommandDoc]) -> CommandIndex:
    """Build a :class:`CommandIndex` from the command documents."""
    return CommandIndex(tuple(docs))

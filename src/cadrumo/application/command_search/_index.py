"""Hybrid command index: per-column BM25 lexical + model2vec semantic, RRF-fused.

Ranks a free-text query against the command corpus so the ``search`` meta-tool
bridges the operator's natural vocabulary to a command's own tokens. Three
cooperating parts, the same shape the corpus grounding search uses:

* a per-column FTS5 lexical index that weights the command KEY and TOOL NAME
  above curated OUTCOME ALIASES above the human DESCRIPTION above the per-verb
  HELP, so a homonym token in a low-value column no longer outranks the correct
  command whose key carries it (the ``import`` mis-rank the review found);
* a model2vec semantic side (behind the capability-gated ``cadrumo[search]``
  extra, reused through the ``corpus_search`` public facade) that embeds the
  command docs and the query into one vector space and cosine-ranks them, so a
  concept query reaches the right verb across a Spanish/English or
  concept/verb vocabulary gap the stemmer cannot bridge;
* Reciprocal Rank Fusion (RRF, ``k=60``) over the two rankings.

The semantic side is a strict enhancement: when the ``search`` extra (or SQLite
FTS5) is absent, :meth:`CommandIndex.search` degrades cleanly — FTS5 BM25 alone,
then a pure-Python token-overlap scorer — so a minimal install always ranks
better than a bare substring match and never hard-fails.

The index is SDK-independent and pure (it takes plain command documents), so it
is unit-tested directly without the MCP transport.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from ..corpus_search import (
    CorpusSearchDependencyError,
    CorpusSearchInputError,
    QueryEmbedder,
    search_extra_available,
)

if TYPE_CHECKING:
    import numpy as np

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_WORD_RE = re.compile(r"\w+", re.UNICODE)

#: Query tokens shorter than this carry no discriminative signal (the article
#: ``a``, the conjunctions ``y``/``o``, a stray ``I``) yet spuriously match a
#: long help column, so they are dropped from the query before ranking.
_MIN_TERM_LEN = 2

#: RRF damping constant. The canonical k=60 keeps a strong hit on one ranker
#: from being drowned by the other ranker's long tail.
RRF_K = 60

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
        """The union of every tier, for the semantic embedding and token fallback."""
        parts = (self.key_and_name, self.description, self.aliases, self.help)
        return " ".join(part for part in parts if part)


class CommandHit(BaseModel):
    """One ranked command match."""

    model_config = _STRICT_FROZEN

    command_key: str
    tool_name: str
    rank: int = Field(ge=0)
    score: float


class _SpanishStemmer(Protocol):
    """The optional stemmer method consumed by the command index."""

    def stemWords(self, words: list[str]) -> list[str]: ...  # noqa: N802 - third-party API


def _spanish_stemmer() -> _SpanishStemmer | None:
    try:
        import snowballstemmer
    except ModuleNotFoundError:
        return None
    # CAST-RATIONALE-SPANISH-STEMMER-PROTOCOL: snowballstemmer ships no static
    # return protocol, while this boundary consumes only its stemWords method.
    return cast(  # nosemgrep: no-cast-in-domain-application reason: untyped library result satisfies _SpanishStemmer.
        "_SpanishStemmer",
        snowballstemmer.stemmer("spanish"),
    )


def _stem_terms(stemmer: _SpanishStemmer | None, terms: Sequence[str]) -> list[str]:
    if stemmer is None or not terms:
        return list(terms)
    return list(stemmer.stemWords(list(terms)))


def _column_text(stemmer: _SpanishStemmer | None, raw: str) -> str:
    """Store a tier as raw plus stemmed text so one column matches both forms.

    Keeps the raw (diacritics-folded by the tokenizer) text alongside its
    Spanish-stemmed tokens, so one column matches both an exact/accented query
    term and a morphological variant without a second column per tier.
    """
    folded = raw.lower()
    stemmed = " ".join(_stem_terms(stemmer, _WORD_RE.findall(folded)))
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
    """A hybrid searchable index over the command corpus.

    Fuses a per-column FTS5 BM25 lexical ranking with a model2vec semantic
    cosine ranking via RRF; both degrade cleanly (FTS5-only, then token-overlap
    only) so a minimal install keeps a working ``search``. :meth:`search`
    returns ranked :class:`CommandHit` records for a free-text query.
    """

    def __init__(
        self,
        docs: Sequence[CommandDoc],
        *,
        query_embedder: QueryEmbedder | None = None,
        enable_semantic: bool = True,
    ) -> None:
        self._docs = tuple(docs)
        self._stemmer = _spanish_stemmer()
        self._connection: sqlite3.Connection | None = None
        if _fts5_available():
            self._connection = self._build_fts(self._docs)
        # The semantic side is off unless the ``search`` extra is present AND
        # there is a corpus to embed; the doc matrix is built lazily on the first
        # search so an index that is never searched pays no model-load cost.
        self._semantic_enabled = enable_semantic and bool(self._docs) and search_extra_available()
        self._semantic_ready = False
        self._embedder = query_embedder
        self._doc_matrix: np.ndarray | None = None

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
        lexical side ranks the matching commands (per-column BM25, or
        token-overlap when FTS5 is absent); the semantic side re-ranks that
        candidate set by cosine similarity when the ``search`` extra is present;
        the two rankings are RRF-fused. When the semantic side is unavailable the
        fused order is exactly the lexical order.
        """
        folded_terms = [term for term in _WORD_RE.findall(query.lower()) if len(term) >= _MIN_TERM_LEN]
        if not folded_terms or limit <= 0:
            return ()
        lexical_keys = self._lexical_ranked_keys(folded_terms)
        if not lexical_keys:
            return ()
        semantic_rank_by_key = self._semantic_rank_by_key(query)
        fused = self._reciprocal_rank_fusion(lexical_keys, semantic_rank_by_key)[:limit]
        tool_name_by_key = {doc.command_key: doc.tool_name for doc in self._docs}
        return tuple(
            CommandHit(command_key=key, tool_name=tool_name_by_key[key], rank=rank, score=score)
            for rank, (key, score) in enumerate(fused)
        )

    def _lexical_ranked_keys(self, folded_terms: Sequence[str]) -> list[str]:
        """Return the lexically-matched command keys, best first (the candidate set)."""
        if self._connection is not None:
            return self._search_fts_keys(folded_terms)
        return self._search_degraded_keys(folded_terms)

    def _search_fts_keys(self, folded_terms: Sequence[str]) -> list[str]:
        assert self._connection is not None
        stemmed_terms = _stem_terms(self._stemmer, folded_terms)
        match = _fts_or_group([*folded_terms, *stemmed_terms])
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
            doc_terms = set(_WORD_RE.findall(doc.combined_text.lower()))
            overlap = len(wanted & doc_terms)
            if overlap:
                scored.append((overlap, ordinal, doc.command_key))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [command_key for _overlap, _ordinal, command_key in scored]

    def _semantic_rank_by_key(self, query: str) -> dict[str, int]:
        """Return the cosine rank of every doc for ``query``, or ``{}`` when off.

        Degrades to an empty ranking whenever the semantic side cannot run — the
        ``search`` extra absent, no embeddable corpus, or a live embed refusal —
        so :meth:`search` falls back to the lexical order.
        """
        if not self._semantic_enabled:
            return {}
        self._ensure_semantic_matrix()
        if self._doc_matrix is None or self._embedder is None:
            return {}
        import numpy as np

        try:
            query_vector = self._embedder.embed_query(query)
        except (CorpusSearchDependencyError, CorpusSearchInputError):
            return {}
        query_unit = _l2_normalise(np.asarray(query_vector, dtype=np.float32).reshape(1, -1))[0]
        similarities = self._doc_matrix @ query_unit
        order = np.argsort(-similarities)
        return {self._docs[int(index)].command_key: rank for rank, index in enumerate(order)}

    def _ensure_semantic_matrix(self) -> None:
        if self._semantic_ready:
            return
        self._semantic_ready = True
        import numpy as np

        try:
            embedder = self._embedder if self._embedder is not None else QueryEmbedder()
            vectors = [embedder.embed_query(doc.combined_text) for doc in self._docs]
        except (CorpusSearchDependencyError, CorpusSearchInputError):
            self._semantic_enabled = False
            return
        self._embedder = embedder
        self._doc_matrix = _l2_normalise(np.asarray(np.vstack(vectors), dtype=np.float32))

    def _reciprocal_rank_fusion(
        self,
        lexical_keys: Sequence[str],
        semantic_rank_by_key: dict[str, int],
    ) -> list[tuple[str, float]]:
        """RRF-fuse the lexical and semantic rankings over the lexical candidate set.

        The candidate universe is the lexically-matched commands; the semantic
        side contributes its rank for those candidates (so it re-orders them,
        breaking homonym ties, without ballooning the matched set the overflow
        signal counts). Ties break deterministically by lexical rank then key.
        """
        lexical_rank_by_key = {key: rank for rank, key in enumerate(lexical_keys)}
        scores: dict[str, float] = {}
        for key, lexical_rank in lexical_rank_by_key.items():
            score = 1.0 / (RRF_K + lexical_rank + 1)
            semantic_rank = semantic_rank_by_key.get(key)
            if semantic_rank is not None:
                score += 1.0 / (RRF_K + semantic_rank + 1)
            scores[key] = score
        return sorted(
            scores.items(),
            key=lambda item: (-item[1], lexical_rank_by_key[item[0]], item[0]),
        )


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def build_command_index(
    docs: Iterable[CommandDoc],
    *,
    query_embedder: QueryEmbedder | None = None,
    enable_semantic: bool = True,
) -> CommandIndex:
    """Build a :class:`CommandIndex` from the command documents."""
    return CommandIndex(tuple(docs), query_embedder=query_embedder, enable_semantic=enable_semantic)

"""Typed records for the on-host corpus-search grounding surface.

Every record is a strict, frozen pydantic v2 model. The surface never
exposes a bare ``dict`` for a chunk, a search hit, or a citation
resolution: the console grounds an operator against verbatim legal text,
so the provenance carried alongside each result (corpus_ref, source
path, document id, permalink) is contract, not decoration.

See Also:
    :func:`~application.corpus_search.search_corpus`
        Runtime service that returns :class:`~application.corpus_search.RetrievalResponse`.
    :func:`~entrypoints.mcp._corpus_tools.corpus_search_payload_from_response`
        MCP transport mapper that preserves the typed retrieval provenance.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RetrievalMode(StrEnum):
    """How a retrieval response was produced.

    ``CITATION`` — the query was an exact citation id, short-circuited to the
    structured lookup; ``HYBRID`` — lexical FTS5 fused with semantic cosine;
    ``LEXICAL_ONLY`` — the degraded no-model mode (search extra absent or no
    precomputed vectors supplied).
    """

    CITATION = "citation"
    HYBRID = "hybrid"
    LEXICAL_ONLY = "lexical_only"


class CorpusChunk(BaseModel):
    """One retrievable prose chunk extracted from the bundled corpus.

    A chunk is a paragraph-bounded slice of a single extracted unit (an
    article or disposition). ``chunk_id`` is deterministic given the same
    corpus, so a rebuilt index re-mints byte-identical ids and the shipped
    embedding matrix stays row-aligned with the lexical index.
    """

    model_config = _STRICT_FROZEN

    chunk_id: _Text
    corpus_ref: _Text
    source_path: _Text
    doc_title: _Text
    section: str | None = None
    anchor: str | None = None
    ordinal: int = Field(ge=0)
    text: _Text


class CorpusDocument(BaseModel):
    """Metadata for one extracted corpus source file in the lexical index."""

    model_config = _STRICT_FROZEN

    corpus_ref: _Text
    source_path: _Text
    title: _Text
    chunk_count: int = Field(ge=0)


class LexicalSearchHit(BaseModel):
    """One ranked lexical-search result over the FTS5 index."""

    model_config = _STRICT_FROZEN

    chunk_id: _Text
    corpus_ref: _Text
    doc_title: _Text
    section: str | None = None
    anchor: str | None = None
    rank: int = Field(ge=0)
    score: float
    text: _Text


class CitationResolution(BaseModel):
    """A citation id resolved to catalogue metadata plus verbatim text.

    The metadata is projected from the registry legal catalogue (the
    single citation authority); ``verbatim_text`` is read from the bundled
    extracted corpus the citation's ``corpus_ref`` points at.
    """

    model_config = _STRICT_FROZEN

    citation_id: _Text
    document_id: _Text
    kind: _Text
    corpus_ref: _Text
    permalink: _Text
    article: str | None = None
    section: str | None = None
    anchor: str | None = None
    verbatim_text: _Text


class SimilarChunk(BaseModel):
    """One cosine-nearest chunk for the more-like-this primitive."""

    model_config = _STRICT_FROZEN

    chunk_id: _Text
    rank: int = Field(ge=0)
    similarity: float


class CorpusIndexBuildResult(BaseModel):
    """Summary of one lexical-index build."""

    model_config = _STRICT_FROZEN

    database_path: _Text
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class CorpusEmbeddingBuildResult(BaseModel):
    """Summary of one build-time embedding precompute."""

    model_config = _STRICT_FROZEN

    matrix_path: _Text
    chunk_ids_path: _Text
    chunk_count: int = Field(ge=0)
    dimensions: int = Field(ge=1)
    embedding_model_id: _Text
    embedding_model_revision: _Text


class RetrievalHit(BaseModel):
    """One fused hybrid-retrieval result over the corpus.

    ``text`` is the verbatim chunk prose (the snippet source); ``corpus_ref``
    grounds it in the bundled source (and is the ``cadrumo://corpus/{ref}`` key
    that resolves the full verbatim text). ``score`` is the fused RRF score;
    ``lexical_rank`` / ``semantic_rank`` record the per-side contribution
    (``None`` when a side did not surface the chunk).
    """

    model_config = _STRICT_FROZEN

    chunk_id: _Text
    corpus_ref: _Text
    doc_title: _Text
    text: _Text
    score: float = Field(ge=0.0)
    rank: int = Field(ge=0)
    lexical_rank: int | None = None
    semantic_rank: int | None = None


class RetrievalResponse(BaseModel):
    """The typed result of one corpus retrieval.

    ``mode`` records how the response was produced (citation short-circuit,
    hybrid, or lexical-only degraded). ``citation`` carries the resolved
    citation when ``mode`` is ``CITATION``; otherwise ``hits`` carries the
    ranked results.
    """

    model_config = _STRICT_FROZEN

    query: _Text
    mode: RetrievalMode
    hits: tuple[RetrievalHit, ...] = ()
    citation: CitationResolution | None = None


__all__ = [
    "CitationResolution",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusEmbeddingBuildResult",
    "CorpusIndexBuildResult",
    "LexicalSearchHit",
    "RetrievalHit",
    "RetrievalMode",
    "RetrievalResponse",
    "SimilarChunk",
]

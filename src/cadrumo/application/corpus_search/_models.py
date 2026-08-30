"""Typed records for the on-host corpus-search grounding surface.

Every record is a strict, frozen pydantic v2 model. The surface never
exposes a bare ``dict`` for a chunk, a search hit, or a citation
resolution: the console grounds an operator against verbatim legal text,
so the provenance carried alongside each result (corpus_ref, source
path, document id, permalink) is contract, not decoration.

See Also:
    :func:`~application.corpus_search.search_corpus`
        Runtime service that returns :class:`~application.corpus_search.RetrievalResponse`.

Notes:
    External adapters may project this response while preserving its typed
    retrieval provenance.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RetrievalMode(StrEnum):
    """How a retrieval response was produced.

    ``CITATION`` — the query was an exact citation id, short-circuited to the
    structured lookup; ``LEXICAL_ONLY`` — the ranked FTS5 lexical search over
    the bundled corpus. These are the only two shapes the product ships: the
    shipped retrieval surface loads no model and computes no vectors.
    """

    CITATION = "citation"
    LEXICAL_ONLY = "lexical_only"


class CorpusChunk(BaseModel):
    """One retrievable prose chunk extracted from the bundled corpus.

    A chunk is a paragraph-bounded slice of a single extracted unit (an
    article or disposition). ``chunk_id`` is deterministic given the same
    corpus, so a rebuilt index re-mints byte-identical ids and a chunk id
    held across a rebuild still resolves.
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


class CorpusIndexBuildResult(BaseModel):
    """Summary of one lexical-index build."""

    model_config = _STRICT_FROZEN

    database_path: _Text
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class RetrievalHit(BaseModel):
    """One ranked lexical-retrieval result over the corpus.

    ``text`` is the verbatim chunk prose (the snippet source); ``corpus_ref``
    grounds it in the bundled source (and is the ``cadrumo://corpus/{ref}`` key
    that resolves the full verbatim text). ``score`` is the FTS5 BM25 relevance,
    sign-flipped so a larger value is a better match; ``lexical_rank`` is the
    hit's zero-based position in the lexical ranking.
    """

    model_config = _STRICT_FROZEN

    chunk_id: _Text
    corpus_ref: _Text
    doc_title: _Text
    text: _Text
    score: float = Field(ge=0.0)
    rank: int = Field(ge=0)
    lexical_rank: int | None = None


class RetrievalResponse(BaseModel):
    """The typed result of one corpus retrieval.

    ``mode`` records how the response was produced (citation short-circuit or
    ranked lexical search). ``citation`` carries the resolved citation when
    ``mode`` is ``CITATION``; otherwise ``hits`` carries the ranked results.
    """

    model_config = _STRICT_FROZEN

    query: _Text
    mode: RetrievalMode
    hits: tuple[RetrievalHit, ...] = ()
    citation: CitationResolution | None = None

    @model_validator(mode="after")
    def _mode_and_result_agree(self) -> RetrievalResponse:
        if self.mode is RetrievalMode.CITATION:
            if self.citation is None:
                raise ValueError("a CITATION response must carry a citation")
            if self.hits:
                raise ValueError("a CITATION response must not carry lexical hits")
        elif self.citation is not None:
            raise ValueError("a LEXICAL_ONLY response must not carry a citation")
        return self


__all__ = [
    "CitationResolution",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusIndexBuildResult",
    "LexicalSearchHit",
    "RetrievalHit",
    "RetrievalMode",
    "RetrievalResponse",
]

"""The ``cadrumo_corpus_search`` grounding tool: lexical search over the legal corpus.

The grounding surface reaches the model as a read-only console tool that
searches the bundled BOE/AEAT corpus and returns grounded hits — each carrying
its ``corpus_ref``, title, a verbatim snippet, the BM25 relevance score, and
a ``cadrumo://corpus/{ref}`` URI a resources-capable client can read to pull the
full verbatim text. An exact citation id short-circuits straight to the
resolved authoritative text. The search is fully offline: no model, no vectors,
no network.

Like ``_harness_tools`` / ``_resources``, this module is SDK-independent pure
functions over typed models: :func:`corpus_search_payload_from_response` and
:func:`render_corpus_search_text` carry no protocol detail and are unit-tested
directly, while :func:`build_corpus_search_tool` lazily adapts onto the MCP
SDK's ``Tool`` type so the module still imports (and the server refuses
gracefully) when the ``cadrumo[agent]`` extra is absent. The retrieval itself is
owned by the application service (:func:`~application.corpus_search.search_corpus`),
consumed through the package facade per ``aeat-architecture-boundaries``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.application.corpus_search import RetrievalMode, RetrievalResponse, search_corpus

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is an optional runtime dependency (``cadrumo[agent]``);
    # the real import stays deferred to inside the function body below.
    from mcp.types import Tool

#: The grounding tool's MCP name (the ``corpus.search`` verb, per the
#: ``cadrumo_<key>`` convention).
CORPUS_SEARCH_TOOL = "cadrumo_corpus_search"

_CORPUS_URI_PREFIX = "cadrumo://corpus/"
_SNIPPET_MAX = 280
_DEFAULT_LIMIT = 8
_MAX_LIMIT = 50

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


def corpus_uri(corpus_ref: str) -> str:
    """Render the ``cadrumo://corpus/<ref>`` URI for a corpus reference."""
    return f"{_CORPUS_URI_PREFIX}{corpus_ref}"


class CorpusSearchResultRow(BaseModel):
    """One grounded corpus hit surfaced to the model."""

    model_config = _STRICT_FROZEN

    corpus_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    score: float = Field(ge=0.0)
    uri: str = Field(min_length=1)


class CorpusCitationResult(BaseModel):
    """The short-circuit result when the query is an exact citation id."""

    model_config = _STRICT_FROZEN

    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    permalink: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    snippet: str = Field(min_length=1)


class CorpusSearchPayload(BaseModel):
    """The grounding tool's structured result.

    ``mode`` records how the response was produced (``citation`` /
    ``lexical_only``). For a citation query ``citation`` is populated and
    ``results`` is empty; otherwise ``results`` carries the ranked hits.
    """

    model_config = _STRICT_FROZEN

    query: str = Field(min_length=1)
    mode: RetrievalMode
    results: tuple[CorpusSearchResultRow, ...] = ()
    citation: CorpusCitationResult | None = None

    @model_validator(mode="after")
    def _mode_and_result_agree(self) -> CorpusSearchPayload:
        if self.mode is RetrievalMode.CITATION:
            if self.citation is None:
                raise ValueError("a CITATION payload must carry a citation")
            if self.results:
                raise ValueError("a CITATION payload must not carry lexical results")
        elif self.citation is not None:
            raise ValueError("a LEXICAL_ONLY payload must not carry a citation")
        return self


def _snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SNIPPET_MAX:
        return collapsed
    return collapsed[: _SNIPPET_MAX - 1].rstrip() + "…"


def corpus_search_payload_from_response(response: RetrievalResponse) -> CorpusSearchPayload:
    """Map a :class:`RetrievalResponse` to the tool's typed payload.

    Returns:
        A :class:`CorpusSearchPayload`.
    """
    if response.mode is RetrievalMode.CITATION:
        # RetrievalResponse's own validator guarantees a CITATION-mode response
        # always carries a resolved citation and no lexical hits.
        citation = response.citation
        assert citation is not None
        return CorpusSearchPayload(
            query=response.query,
            mode=response.mode,
            citation=CorpusCitationResult(
                citation_id=citation.citation_id,
                document_id=citation.document_id,
                permalink=citation.permalink,
                uri=corpus_uri(citation.citation_id),
                snippet=_snippet(citation.verbatim_text),
            ),
        )
    rows = tuple(
        CorpusSearchResultRow(
            corpus_ref=hit.corpus_ref,
            title=hit.doc_title,
            snippet=_snippet(hit.text),
            score=hit.score,
            uri=corpus_uri(hit.corpus_ref),
        )
        for hit in response.hits
    )
    return CorpusSearchPayload(query=response.query, mode=response.mode, results=rows)


def build_corpus_search_payload(query: str, *, limit: int = _DEFAULT_LIMIT) -> CorpusSearchPayload:
    """Run grounding retrieval for ``query`` and return the tool payload.

    Args:
        query: The free-text query or an exact citation id.
        limit: Maximum number of hits.

    Returns:
        A :class:`CorpusSearchPayload`.
    """
    return corpus_search_payload_from_response(search_corpus(query, limit=limit))


def render_corpus_search_text(payload: CorpusSearchPayload) -> str:
    """Render the payload as markdown for the tool's text content."""
    if payload.citation is not None:
        citation = payload.citation
        return "\n".join(
            [
                f"# corpus citation: {citation.citation_id}",
                f"- document: {citation.document_id}",
                f"- permalink: {citation.permalink}",
                f"- resource: {citation.uri}",
                "",
                citation.snippet,
            ]
        )
    if not payload.results:
        return f"No corpus results for '{payload.query}'."
    lines = [f"# corpus results for '{payload.query}' ({payload.mode.value})", ""]
    for index, row in enumerate(payload.results, start=1):
        lines += [
            f"{index}. {row.title} (score {row.score:.4f})",
            f"   {row.uri}",
            f"   {row.snippet}",
        ]
    return "\n".join(lines)


def build_corpus_search_tool() -> Tool:
    """Build the SDK ``Tool`` for the grounding search tool.

    Lazily imports the SDK types so the module imports without the
    ``cadrumo[agent]`` extra. Annotated ``readOnlyHint`` / ``idempotentHint``: it
    reads the bundled corpus and never mutates state.

    Returns:
        The ``cadrumo_corpus_search`` :class:`~mcp.types.Tool` object.
    """
    from mcp.types import Tool, ToolAnnotations

    return Tool(
        name=CORPUS_SEARCH_TOOL,
        description=(
            "Search the bundled BOE/AEAT legal corpus and terminology for grounding. "
            "Returns ranked hits with a verbatim snippet and a cadrumo://corpus/{ref} URI "
            "resolving the full authoritative text; an exact citation id resolves directly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concept, phrase, or exact citation id (e.g. 'ley-58-2003:art-27.2').",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIMIT,
                    "description": f"Maximum hits to return (default {_DEFAULT_LIMIT}).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(
            title="Search the legal corpus",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
        ),
    )


__all__ = [
    "CORPUS_SEARCH_TOOL",
    "CorpusCitationResult",
    "CorpusSearchPayload",
    "CorpusSearchResultRow",
    "build_corpus_search_payload",
    "build_corpus_search_tool",
    "corpus_search_payload_from_response",
    "corpus_uri",
    "render_corpus_search_text",
]

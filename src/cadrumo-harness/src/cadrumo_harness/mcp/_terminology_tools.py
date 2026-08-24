"""The ``cadrumo_terminology_search`` tool: look up taxpayer-facing tax vocabulary.

The grounding surface has a second half: the bundled Terminology Handbook,
the ratified taxpayer/operator vocabulary. This tool lets the model resolve a
plain-language term ("prorrata", "recargo de equivalencia") to its preferred
label, short description, and concept id, so the assistant explains a concept in
the taxpayer's own words rather than inventing a definition. Only
``approved``-lifecycle concepts are searched (the taxpayer-facing set), per the
``aeat-documentation`` rule the application service already
enforces.

Like ``_corpus_tools`` / ``_harness_tools``, this module is SDK-independent pure
functions over typed models; :func:`build_terminology_search_tool` lazily adapts
onto the MCP SDK's ``Tool`` type so the module imports (and the server refuses
gracefully) without the harness distribution's MCP runtime. The search itself is owned by the
application service (:func:`~application.corpus_search.search_terminology`),
consumed through the package facade per ``aeat-architecture-boundaries``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.corpus_search import TerminologyHit, search_terminology

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is supplied by the sibling harness distribution;
    # the real import stays deferred to inside the function body below.
    from mcp.types import Tool

#: The terminology tool's MCP name (the ``terminology.search`` verb).
TERMINOLOGY_SEARCH_TOOL = "cadrumo_terminology_search"

_DEFAULT_LIMIT = 8
_MAX_LIMIT = 25

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class TerminologyResultRow(BaseModel):
    """One terminology hit surfaced to the model."""

    model_config = _STRICT_FROZEN

    concept_id: str = Field(min_length=1)
    preferred_label: str = Field(min_length=1)
    short_description: str = ""
    matched_on: str = Field(min_length=1)


class TerminologySearchPayload(BaseModel):
    """The terminology tool's structured result."""

    model_config = _STRICT_FROZEN

    query: str = Field(min_length=1)
    results: tuple[TerminologyResultRow, ...] = ()


def terminology_payload_from_hits(query: str, hits: tuple[TerminologyHit, ...]) -> TerminologySearchPayload:
    """Map ranked terminology hits to the tool's typed payload.

    Returns:
        A :class:`TerminologySearchPayload`.
    """
    rows = tuple(
        TerminologyResultRow(
            concept_id=hit.concept_id,
            preferred_label=hit.preferred_label,
            short_description=hit.short_description,
            matched_on=hit.matched_on,
        )
        for hit in hits
    )
    return TerminologySearchPayload(query=query, results=rows)


def build_terminology_search_payload(
    query: str,
    *,
    locale: str = "es",
    limit: int = _DEFAULT_LIMIT,
) -> TerminologySearchPayload:
    """Run terminology search for ``query`` and return the tool payload.

    Returns:
        A :class:`TerminologySearchPayload`.
    """
    hits = search_terminology(query, locale=locale, limit=limit)
    return terminology_payload_from_hits(query, hits)


def render_terminology_search_text(payload: TerminologySearchPayload) -> str:
    """Render the payload as markdown for the tool's text content."""
    if not payload.results:
        return f"No terminology concept matches '{payload.query}'."
    lines = [f"# terminology matches for '{payload.query}'", ""]
    for index, row in enumerate(payload.results, start=1):
        lines.append(f"{index}. {row.preferred_label} ({row.concept_id})")
        if row.short_description:
            lines.append(f"   {row.short_description}")
    return "\n".join(lines)


def build_terminology_search_tool() -> Tool:
    """Build the SDK ``Tool`` for the terminology search tool.

    Lazily imports the SDK types so the module imports without the
    harness distribution's MCP runtime. Annotated ``readOnlyHint`` / ``idempotentHint``.

    Returns:
        The ``cadrumo_terminology_search`` :class:`~mcp.types.Tool` object.
    """
    from mcp.types import Tool, ToolAnnotations

    return Tool(
        name=TERMINOLOGY_SEARCH_TOOL,
        description=(
            "Look up a Spanish tax term in the bundled Terminology Handbook and return "
            "its preferred label, short description, and concept id, so you explain the "
            "concept in the taxpayer's own vocabulary rather than inventing a definition."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A tax term or concept in plain language (e.g. 'prorrata', 'recargo').",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIMIT,
                    "description": f"Maximum concepts to return (default {_DEFAULT_LIMIT}).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        annotations=ToolAnnotations(
            title="Search the tax terminology handbook",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
        ),
    )


__all__ = [
    "TERMINOLOGY_SEARCH_TOOL",
    "TerminologyResultRow",
    "TerminologySearchPayload",
    "build_terminology_search_payload",
    "build_terminology_search_tool",
    "render_terminology_search_text",
    "terminology_payload_from_hits",
]

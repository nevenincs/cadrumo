"""Sphinx rendering for annotations whose source text needs special handling."""

from __future__ import annotations

from typing import Any

_PYDANTIC_ALLOW_INF_NAN_URL = "https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan"
_MCP_SERVER_URL = "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/"


def _annotation_text(annotation: object) -> str | None:
    """Return source text for a postponed annotation or type object."""
    if isinstance(annotation, str):
        return annotation.strip().strip("'\"")
    name = getattr(annotation, "__name__", None)
    module = getattr(annotation, "__module__", None)
    if isinstance(name, str) and isinstance(module, str):
        return f"{module}.{name}"
    return None


def format_type_hint(annotation: Any, config: Any = None) -> str | None:
    """Format external types and regex-bearing annotations for Sphinx.

    Regex character classes inside ``Annotated[..., Field(pattern=...)]`` are
    source metadata, not cross-reference syntax. Literalizing just those full
    annotation strings keeps the declared constraints intact while preventing
    docutils from interpreting their square brackets as reference labels.
    """
    text = _annotation_text(annotation)
    if text is None:
        return None

    if text in {"AllowInfNan", "pydantic.types.AllowInfNan"}:
        return f"`AllowInfNan <{_PYDANTIC_ALLOW_INF_NAN_URL}>`_"
    if text == "mcp.server.lowlevel.server.Server":
        return f"`Server <{_MCP_SERVER_URL}>`_"

    if "pattern=" in text and "[" in text and "]" in text and any(
        marker in text for marker in ("Field(", "StringConstraints(")
    ):
        return f"``{text}``"
    return None

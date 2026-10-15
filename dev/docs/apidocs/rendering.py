"""Sphinx rendering for annotations whose source text needs special handling."""

from __future__ import annotations

from typing import Annotated, Any, ForwardRef, get_args, get_origin

_PYDANTIC_ALLOW_INF_NAN_URL = (
    "https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan"
)
_MCP_SERVER_URL = "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/"


def _annotation_text(annotation: object) -> str | None:
    """Return source text for a postponed annotation or type object."""
    if isinstance(annotation, str):
        return annotation.strip().strip("'\"")
    if isinstance(annotation, ForwardRef):
        return annotation.__forward_arg__.strip().strip("'\"")
    forward_arg = getattr(annotation, "__forward_arg__", None)
    if isinstance(forward_arg, str):
        return forward_arg.strip().strip("'\"")
    name = getattr(annotation, "__name__", None)
    module = getattr(annotation, "__module__", None)
    if isinstance(name, str) and isinstance(module, str):
        return f"{module}.{name}"
    annotation_type = type(annotation)
    name = getattr(annotation_type, "__name__", None)
    module = getattr(annotation_type, "__module__", None)
    if isinstance(name, str) and isinstance(module, str):
        return f"{module}.{name}"
    return None


def external_type_url(annotation: object) -> str | None:
    """Return the canonical external documentation URL for a known type."""
    text = _annotation_text(annotation)
    if text in {"AllowInfNan", "pydantic.types.AllowInfNan"}:
        return _PYDANTIC_ALLOW_INF_NAN_URL
    if text in {"Server", "mcp.server.Server", "mcp.server.lowlevel.server.Server"}:
        return _MCP_SERVER_URL
    return None


def _annotated_parts(annotation: object) -> tuple[object, str] | None:
    """Return the base and metadata text of a runtime or postponed Annotated."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if len(args) > 1:
            return args[0], ", ".join(str(item) for item in args[1:])

    text = _annotation_text(annotation)
    if text is None:
        return None
    start = text.find("[")
    if start < 0 or text[:start].rsplit(".", 1)[-1] != "Annotated" or not text.endswith("]"):
        return None

    parts: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    part_start = start + 1
    for index in range(start + 1, len(text) - 1):
        character = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "'\"":
            quote = character
        elif character in "[({":
            depth += 1
        elif character in "])}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(text[part_start:index].strip())
            part_start = index + 1
    parts.append(text[part_start:-1].strip())
    if len(parts) < 2 or not parts[0]:
        return None
    return parts[0], ", ".join(parts[1:])


def _base_reference(base: object) -> str | None:
    """Render a base type as a normal Python cross-reference when possible."""
    if isinstance(base, str):
        text = base.strip().strip("'\"")
    else:
        text = _annotation_text(base) or ""
        if isinstance(base, type) and base.__module__ == "builtins":
            return base.__qualname__
        if isinstance(base, type):
            return f":py:class:`~{base.__module__}.{base.__qualname__}`"
    if not text or any(character in text for character in "[](),"):
        return None
    if text in {"str", "int", "float", "bool", "bytes", "None", "NoneType"}:
        return text
    return f":py:class:`{text}`"


def _format_annotated(annotation: object) -> str | None:
    """Keep an Annotated base reference while treating metadata as source text."""
    parts = _annotated_parts(annotation)
    if parts is None:
        return None
    base, metadata = parts
    has_regex = "pattern=" in metadata
    has_non_finite_policy = any(
        _annotation_text(item) == "pydantic.types.AllowInfNan" for item in get_args(annotation)[1:]
    ) if get_origin(annotation) is Annotated else "AllowInfNan" in metadata
    if not (has_regex or has_non_finite_policy):
        return None
    rendered_base = _base_reference(base)
    if rendered_base is None:
        return None
    return f"{rendered_base} ``{metadata}``"


def format_type_hint(annotation: Any, config: Any = None) -> str | None:
    """Format external types and Annotated field metadata for Sphinx.

    Metadata is rendered as source text, while its base remains a Python type
    reference. This keeps regex character classes out of docutils's reference
    syntax without hiding unresolved first-party base types.
    """
    annotated = _format_annotated(annotation)
    if annotated is not None:
        return annotated

    url = external_type_url(annotation)
    if url is None:
        return None
    text = _annotation_text(annotation)
    if text is None:
        return None
    label = text.rsplit(".", 1)[-1]
    return f"`{label} <{url}>`_"

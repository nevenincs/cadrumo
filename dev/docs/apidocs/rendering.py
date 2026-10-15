"""Sphinx rendering for annotations whose source text needs special handling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Any, TypeAliasType, get_args, get_origin

_PYDANTIC_ALLOW_INF_NAN_URL = (
    "https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan"
)
_MCP_SERVER_URL = "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/"


def _annotation_text(annotation: object) -> str | None:
    """Return source text for a postponed annotation or type object."""
    if isinstance(annotation, str):
        return annotation.strip().strip("'\"")
    forward_arg = getattr(annotation, "__forward_arg__", None)
    if isinstance(forward_arg, str):
        return str(forward_arg).strip().strip("'\"")
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
    if text == "pydantic.types.AllowInfNan":
        return _PYDANTIC_ALLOW_INF_NAN_URL
    if text in {"mcp.server.Server", "mcp.server.lowlevel.server.Server"}:
        return _MCP_SERVER_URL
    return None


@dataclass(frozen=True, slots=True)
class TypeHintsFormatter:
    """Pickleable Sphinx config value that delegates to the annotation renderer."""

    def __call__(self, annotation: Any, config: Any = None) -> str | None:
        """Format the annotation using the shared API rendering rules."""
        return format_type_hint(annotation, config)


def _runtime_metadata_text(item: object) -> str:
    """Render runtime Pydantic metadata without losing marker type identity."""
    nested_metadata = getattr(item, "metadata", None)
    if isinstance(nested_metadata, list | tuple):
        return ", ".join(repr(value) for value in nested_metadata)
    return repr(item)


def _annotated_parts(annotation: object) -> tuple[object, str] | None:
    """Return the base and metadata text of a runtime or postponed Annotated."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if len(args) > 1:
            return args[0], ", ".join(_runtime_metadata_text(item) for item in args[1:])

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
    has_non_finite_policy = "AllowInfNan(" in metadata
    if not (has_regex or has_non_finite_policy):
        return None
    rendered_base = _base_reference(base)
    if rendered_base is None:
        return None
    return f"{rendered_base} ``{metadata}``"


def attribute_type_components(annotation: object) -> tuple[str, str | None] | None:
    """Return plain domain-target and literal metadata fields for autodoc attributes.

    Sphinx treats all of an attribute's ``:type:`` value as a Python class target,
    so inline reStructuredText in that field becomes part of the unresolved name.
    Keep the target in that field and place parser-sensitive metadata in its own
    literal-valued field instead.
    """
    parts = _annotated_parts(annotation)
    if parts is not None:
        base, metadata = parts
        if "pattern=" not in metadata and "AllowInfNan(" not in metadata:
            return None
        if isinstance(base, str):
            base_text = base.strip().strip("'\"")
        elif isinstance(base, type):
            base_text = _annotation_text(base) or ""
            if base.__module__ == "builtins":
                base_text = base.__qualname__
        else:
            base_text = _annotation_text(base) or ""
        if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", base_text) is None:
            return None
        return base_text, metadata

    if external_type_url(annotation) is not None:
        text = _annotation_text(annotation)
        if text is not None and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", text):
            return text, None
    return None


def format_type_hint(annotation: Any, config: Any = None) -> str | None:
    """Format external types and Annotated field metadata for Sphinx.

    Metadata is rendered as source text, while its base remains a Python type
    reference. This keeps regex character classes out of docutils's reference
    syntax without hiding unresolved first-party base types.
    """
    annotated = _format_annotated(annotation)
    if annotated is not None:
        return annotated

    if isinstance(annotation, TypeAliasType):
        text = _annotation_text(annotation)
        if text is not None and "." in text:
            return f":py:class:`{text}`"

    url = external_type_url(annotation)
    if url is None:
        return None
    text = _annotation_text(annotation)
    if text is None:
        return None
    label = text.rsplit(".", 1)[-1]
    return f"`{label} <{url}>`_"

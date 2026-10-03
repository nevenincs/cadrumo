"""Document prose for the authoritative locale audit."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from dev._paths import UTF_8

from .signal_policy import LOCALES
from .signal_syntax import TRANSLATION_HTML_LANGUAGE_RE
from .signal_tokens import filtered_translation_text

if TYPE_CHECKING:
    from markdown_it.token import Token


def visible_document_prose(path: Path) -> tuple[tuple[int, str], ...]:
    """Extract visible RST/Markdown prose while excluding literal syntax."""
    if path.suffix == ".rst":
        return rst_document_prose(path)
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(path.read_text(encoding=UTF_8))
    return tuple(
        ((token.map or [0])[0] + 1, markdown_inline_prose(token))
        for token in tokens
        if token.type == "inline"
        if any(child.type == "text" and child.content.strip() for child in (token.children or ()))
    )


def embedded_document_language_prose(path: Path) -> tuple[tuple[int, str, str], ...]:
    """Extract visible HTML fragments whose markup declares another language."""
    source = path.read_text(encoding=UTF_8)
    blocks: list[tuple[int, str, str]] = []
    for match in TRANSLATION_HTML_LANGUAGE_RE.finditer(source):
        language = match.group("locale").casefold()
        if language not in LOCALES:
            continue
        text = filtered_translation_text(match.group("body"))[0]
        if text:
            blocks.append((source.count("\n", 0, match.start()) + 1, language, text))
    return tuple(blocks)


def node_has_ancestor(node: object, node_types: tuple[type[object], ...]) -> bool:
    """Return whether a docutils node is nested below excluded syntax."""
    parent = getattr(node, "parent", None)
    while parent is not None:
        if isinstance(parent, node_types):
            return True
        parent = getattr(parent, "parent", None)
    return False


def rst_document_prose(path: Path) -> tuple[tuple[int, str], ...]:
    """Rst document prose."""
    from docutils import nodes
    from docutils.core import publish_doctree

    source = path.read_text(encoding=UTF_8)
    document = publish_doctree(
        source,
        source_path=str(path),
        settings_overrides={"report_level": 5, "halt_level": 6, "warning_stream": io.StringIO()},
    )
    excluded = (nodes.literal, nodes.literal_block, nodes.option_string, nodes.raw)
    blocks: list[tuple[int, str]] = []
    blocks_to_read = (nodes.title, nodes.paragraph, nodes.term, nodes.caption)
    for node in document.findall(lambda candidate: isinstance(candidate, blocks_to_read)):
        parts = [str(text) for text in node.findall(nodes.Text) if not node_has_ancestor(text, excluded)]
        value = " ".join("".join(parts).split())
        if value:
            blocks.append((int(node.line or 0), value))
    return tuple(blocks)


def markdown_inline_prose(token: Token) -> str:
    """Read visible text from a parsed Markdown inline token."""
    return " ".join(child.content for child in (token.children or ()) if child.type == "text")

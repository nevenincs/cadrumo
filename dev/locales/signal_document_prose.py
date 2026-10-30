"""Document prose for the authoritative locale audit."""

from __future__ import annotations

import io
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dev._paths import UTF_8

from .signal_command_paths import executable_command_paths
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
    blocks, parsed_headings, parsed_titles = _rst_prose_blocks(document, nodes)
    prose = _exclude_generated_casilla_section_identifiers(path, source, blocks, parsed_headings)
    return _exclude_generated_cli_command_headings(path, prose, parsed_titles)


def _rst_prose_blocks(
    document: Any,
    nodes: Any,
) -> tuple[tuple[tuple[int, str], ...], dict[int | None, list[str]], dict[int | None, list[str]]]:
    """Collect visible RST blocks and parsed heading text in document order."""
    excluded = (nodes.literal, nodes.literal_block, nodes.option_string, nodes.raw)
    blocks: list[tuple[int, str]] = []
    parsed_headings: dict[int | None, list[str]] = {}
    parsed_titles: dict[int | None, list[str]] = {}
    blocks_to_read = (nodes.title, nodes.subtitle, nodes.paragraph, nodes.term, nodes.caption)
    for node in document.findall(lambda candidate: isinstance(candidate, blocks_to_read)):
        _record_rst_prose_block(node, nodes, excluded, blocks, parsed_headings, parsed_titles)
    return tuple(blocks), parsed_headings, parsed_titles


def _record_rst_prose_block(
    node: Any,
    nodes: Any,
    excluded: tuple[type[Any], ...],
    blocks: list[tuple[int, str]],
    parsed_headings: dict[int | None, list[str]],
    parsed_titles: dict[int | None, list[str]],
) -> None:
    """Normalize a parsed RST node and retain its visible block/heading text."""
    parts = [str(text) for text in node.findall(nodes.Text) if not node_has_ancestor(text, excluded)]
    value = " ".join("".join(parts).split())
    if not value:
        return
    line = int(node.line) if node.line is not None else None
    if isinstance(node, (nodes.title, nodes.subtitle)):
        parsed_headings.setdefault(line, []).append(value)
    if isinstance(node, nodes.title):
        parsed_titles.setdefault(line, []).append(value)
    if not isinstance(node, nodes.subtitle):
        blocks.append((int(node.line or 0), value))


def _exclude_generated_cli_command_headings(
    path: Path,
    prose: tuple[tuple[int, str], ...],
    parsed_titles: Mapping[int | None, list[str]],
) -> tuple[tuple[int, str], ...]:
    """Exclude exact generated CLI headings that name executable commands.

    A title is exempt only when its complete extracted text is a path in the
    canonical command graphs. Other text remains enrolled for spelling, whose
    syntax filter can also classify exact embedded executable path spans.
    """
    if path.suffix != ".rst" or not _is_generated_cli_path(path):
        return prose
    command_paths = executable_command_paths()
    excluded_lines = {
        line
        for line, titles in parsed_titles.items()
        if line is not None and len(titles) == 1 and tuple(titles[0].split()) in command_paths
    }
    return tuple((line, text) for line, text in prose if line not in excluded_lines)


def _is_generated_cli_path(path: Path) -> bool:
    """Return whether a source path belongs to the generated docs/cli tree."""
    parts = path.parts
    return any(parts[index : index + 2] == ("docs", "cli") for index in range(len(parts) - 1))


_CASILLA_SECTION_MARKER_PREFIX = ".. cadrumo-casilla-section-identifier"
_CASILLA_SECTION_MARKER = re.compile(r"^\.\. cadrumo-casilla-section-identifier: (.+)$")


def _exclude_generated_casilla_section_identifiers(
    path: Path,
    source: str,
    prose: tuple[tuple[int, str], ...],
    parsed_headings: Mapping[int | None, list[str]],
) -> tuple[tuple[int, str], ...]:
    """Exclude only exact marked registry headings on generated casilla pages.

    Malformed markers, misplaced markers, and headings that no longer match
    their canonical registry display are extraction failures. They never widen
    the spelling exclusion.
    """
    lines = source.splitlines()
    marker_lines = _casilla_section_marker_lines(lines)
    if not marker_lines:
        return prose
    _validate_casilla_reference_page(path)
    excluded_lines = {
        _validated_casilla_heading_line(lines, parsed_headings, marker_line, marker)
        for marker_line, marker in marker_lines
    }
    return tuple((line, text) for line, text in prose if line not in excluded_lines)


def _casilla_section_marker_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return candidate marker lines, retaining malformed lookalikes for refusal."""
    return [
        (number, line) for number, line in enumerate(lines, start=1) if line.startswith(_CASILLA_SECTION_MARKER_PREFIX)
    ]


def _validate_casilla_reference_page(path: Path) -> None:
    """Accept markers only in the generator's per-modelo output files."""
    from dev.docs.terminology.casilla_anchor import CASILLA_REFERENCE_DIR

    if (
        path.suffix != ".rst"
        or path.parts[-3:-1] != tuple(CASILLA_REFERENCE_DIR.split("/"))
        or re.fullmatch(r"[0-9]{3}", path.stem) is None
    ):
        raise ValueError("casilla section identifier markers are only valid in generated casilla pages")


def _validated_casilla_heading_line(
    lines: list[str],
    parsed_headings: Mapping[int | None, list[str]],
    marker_line: int,
    marker: str,
) -> int:
    """Validate one exact marker and return its parsed prose line for exclusion."""
    section = _casilla_section_from_marker(marker, marker_line)
    heading_source_line = _casilla_heading_source_line(lines, marker_line)
    from cadrumo.core.external_constants import OutputLanguage
    from dev.docs.casilla_display import section_display

    expected = section_display(section, OutputLanguage.EN)
    source_heading = re.sub(r"\\(.)", r"\1", lines[heading_source_line - 1]).strip()
    parsed_heading_line = next(
        (line for line in (heading_source_line, heading_source_line + 1) if expected in parsed_headings.get(line, ())),
        None,
    )
    if source_heading != expected or (parsed_heading_line is None and expected not in parsed_headings.get(None, ())):
        raise ValueError(
            f"casilla section marker on line {marker_line} does not match its heading "
            f"(expected {expected!r} at source line {heading_source_line}; got {source_heading!r})"
        )
    return parsed_heading_line if parsed_heading_line is not None else heading_source_line


def _casilla_section_from_marker(marker: str, marker_line: int) -> tuple[str, ...]:
    """Parse and validate the JSON tuple carried by one generated comment."""
    match = _CASILLA_SECTION_MARKER.fullmatch(marker)
    if match is None:
        raise ValueError(f"malformed casilla section identifier marker on line {marker_line}")
    try:
        section = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed casilla section path on line {marker_line}") from exc
    if not isinstance(section, list) or not section or any(not isinstance(part, str) or not part for part in section):
        raise ValueError(f"invalid casilla section path on line {marker_line}")
    return tuple(str(part) for part in section)


def _casilla_heading_source_line(lines: list[str], marker_line: int) -> int:
    """Require the marker's next nonblank source line to be its heading."""
    heading_line = marker_line + 2
    if (
        heading_line + 1 > len(lines)
        or lines[marker_line] != ""
        or not lines[marker_line + 1].strip()
        or not lines[heading_line].strip()
    ):
        raise ValueError(f"casilla section marker on line {marker_line} is not adjacent to a heading")
    return heading_line


def markdown_inline_prose(token: Token) -> str:
    """Read visible text from a parsed Markdown inline token."""
    return " ".join(child.content for child in (token.children or ()) if child.type == "text")

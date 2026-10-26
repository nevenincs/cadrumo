"""Render lifted casilla blocks while preserving all untouched source text."""

from __future__ import annotations

import re

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_toml_writer as _edition_delta_toml_writer


def _scan_depth(text: str, depth: int) -> int:
    """Return bracket depth after text, ignoring strings and comments."""
    index, quote = 0, ""
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 1
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            break
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        index += 1
    return depth


def _top_level_items(inline: str) -> list[str]:
    """Split an inline table at top-level commas, retaining each item's text."""
    items: list[str] = []
    depth, quote, start, index = 0, "", 0, 0
    while index < len(inline):
        depth, quote, separator, skip = _advance_inline_state(inline[index], depth, quote)
        if separator:
            items.append(inline[start:index])
            start = index + 1
        if skip:
            index += 1
        index += 1
    items.append(inline[start:])
    return [item for item in items if item.strip()]


def _advance_inline_state(char: str, depth: int, quote: str) -> tuple[int, str, bool, bool]:
    separator = False
    skip = False
    if quote:
        if char == "\\" and quote == '"':
            skip = True
        elif char == quote:
            quote = ""
    elif char in "\"'":
        quote = char
    elif char in "[{":
        depth += 1
    elif char in "]}":
        depth -= 1
    elif char == "," and depth == 0:
        separator = True
    return depth, quote, separator, skip


def _additions_assignment(additions: tuple[str, ...]) -> str:
    return f"{_edition_delta_fields._ROW_SOURCE_ADDITIONS} = {_edition_delta_toml_writer.toml_value(list(additions))}"


def _lifted_inline(line: str, lift: _edition_delta_source._TableLift) -> str:
    key, _, rest = line.partition("=")
    body = rest.strip()
    if not (body.startswith("{") and body.endswith("}")):
        raise _edition_delta_errors.MigrationRefusedError(
            f"constraints are neither a table nor a one-line inline table: {line!r}"
        )
    kept = [
        rendered
        for item in (item.strip() for item in _top_level_items(body[1:-1]))
        if (rendered := _lifted_inline_item(item, lift)) is not None
    ]
    return f"{key.rstrip()} = {{ {', '.join(kept)} }}\n" if kept else f"{key.rstrip()} = {{}}\n"


def _lifted_inline_item(item: str, lift: _edition_delta_source._TableLift) -> str | None:
    name = item.partition("=")[0].strip()
    replace_source = _edition_delta_fields._ROW_SOURCE in lift.removed
    if name == _edition_delta_fields._ROW_SOURCE_ADDITIONS and replace_source:
        return _additions_assignment(lift.additions) if lift.additions is not None else None
    if name not in lift.removed:
        return item
    if name == _edition_delta_fields._ROW_SOURCE and lift.additions is not None:
        return _additions_assignment(lift.additions)
    return None


def _key_of(line: str) -> str | None:
    match = re.match(r"^([A-Za-z0-9_-]+)\s*=", line)
    return str(match.group(1)) if match else None


def _scope_and_table_lift(
    line: str, scope: str, lift: _edition_delta_source._Lift
) -> tuple[str, _edition_delta_source._TableLift | None, str | None]:
    stripped = line.rstrip("\r\n")
    if _edition_delta_fields._ROW_HEADER.match(stripped):
        scope = "row"
    elif _edition_delta_fields._CONSTRAINTS_HEADER.match(stripped):
        scope = "constraints"
    elif stripped.startswith("["):
        scope = "other"
    table_lift = lift.row_lift if scope == "row" else lift.constraint_lift if scope == "constraints" else None
    return scope, table_lift, _key_of(line)


def _is_lifted_key(key: str, table_lift: _edition_delta_source._TableLift) -> bool:
    return key in table_lift.removed or (
        key == _edition_delta_fields._ROW_SOURCE_ADDITIONS and _edition_delta_fields._ROW_SOURCE in table_lift.removed
    )


def _skip_assignment(lines: list[str], index: int) -> int:
    depth = _scan_depth(lines[index].partition("=")[2], 0)
    while depth > 0 and index + 1 < len(lines):
        index += 1
        depth = _scan_depth(lines[index], depth)
    return index


def _lifted_text(block: _edition_delta_source._Block, lift: _edition_delta_source._Lift) -> str:
    """Remove lifted keys from row text and verify the reparsed row remains exact."""
    if not lift.row_lift.removed and not lift.constraint_lift.removed:
        return block.text
    lines = block.text.splitlines(keepends=True)
    out: list[str] = []
    scope, index = "comment", 0
    while index < len(lines):
        scope, index = _rewrite_lifted_line(lines, index, scope, lift, out)
    text = "".join(out)
    if _edition_delta_source._block_row(text) != lift.row:
        raise _edition_delta_errors.MigrationRefusedError(
            f"lifting casilla {_edition_delta_source._row_id(block.row)!r} would change more than its lifted keys"
        )
    return text


def _rewrite_lifted_line(
    lines: list[str],
    index: int,
    scope: str,
    lift: _edition_delta_source._Lift,
    out: list[str],
) -> tuple[str, int]:
    line = lines[index]
    scope, table_lift, key = _scope_and_table_lift(line, scope, lift)
    if key is not None and table_lift is not None and _is_lifted_key(key, table_lift):
        index = _skip_assignment(lines, index)
        if (
            key in {_edition_delta_fields._ROW_SOURCE, _edition_delta_fields._ROW_SOURCE_ADDITIONS}
            and table_lift.additions is not None
        ):
            out.append(_additions_assignment(table_lift.additions) + "\n")
        return scope, index + 1
    if scope == "row" and key == _edition_delta_fields._CONSTRAINTS and lift.constraint_lift.removed:
        line = _lifted_inline(line, lift.constraint_lift)
    out.append(line)
    return scope, index + 1

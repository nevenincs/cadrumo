"""Apply reviewed lineage key edits to their owning casilla declaration files."""

from __future__ import annotations

import collections
import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path

from .casilla_lineage_seed_paths import _MODELOS_ROOT, _UTF_8
from .casilla_lineage_seed_types import LineagePlan

_LINEAGE_KEYS = ("continuidad_id", "continuidad_origin", "continuidad_evidence")
_CASILLA_HEADER = re.compile(r'^\[\[revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\.casillas\]\]\s*$')
_ID_LINE = re.compile(r"""^id\s*=\s*(?:"([^"]+)"|'([^']+)')\s*$""")


def insert_lineage_keys(text: str, revision: str, edits: Mapping[str, Mapping[str, str]]) -> tuple[str, set[str]]:
    """Insert lineage keys into the named casilla tables of one declaration file.

    Returns the new text and the casilla ids it edited. A key already present
    with the same value is left alone; a differing value is refused.
    """
    lines = text.split("\n")
    output: list[str] = []
    done: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        index += 1
        if _header_revision(line) != revision:
            continue
        block, index = _table_block(lines, index)
        _append_table_block(output, block, edits, done)
    return "\n".join(output), done


def _header_revision(line: str) -> str | None:
    header = _CASILLA_HEADER.match(line)
    if header is None:
        return None
    revision = header.group(1) or header.group(2)
    return revision if isinstance(revision, str) else None


def _table_block(lines: list[str], index: int) -> tuple[list[str], int]:
    start = index
    while index < len(lines) and not lines[index].lstrip().startswith("["):
        index += 1
    return lines[start:index], index


def _append_table_block(
    output: list[str],
    block: list[str],
    edits: Mapping[str, Mapping[str, str]],
    done: set[str],
) -> None:
    casilla_id = _block_casilla_id(block)
    if casilla_id is None or casilla_id not in edits:
        output.extend(block)
        return
    output.extend(_edit_block(block, casilla_id, edits[casilla_id]))
    done.add(casilla_id)


def _block_casilla_id(block: list[str]) -> str | None:
    for entry in block:
        match = _ID_LINE.match(entry)
        if match is None:
            continue
        casilla_id = match.group(1) or match.group(2)
        return casilla_id if isinstance(casilla_id, str) else None
    return None


def _edit_block(block: list[str], casilla_id: str, keys: Mapping[str, str]) -> list[str]:
    present: dict[str, int] = {}
    for position, entry in enumerate(block):
        key = entry.split("=", 1)[0].strip()
        if key in _LINEAGE_KEYS or key == "id":
            present[key] = position
    new_lines: list[str] = []
    for key in _LINEAGE_KEYS:
        if key not in keys:
            continue
        rendered = f"{key} = {json.dumps(keys[key], ensure_ascii=False)}"
        if key in present:
            if block[present[key]].strip() != rendered:
                raise ValueError(f"casilla {casilla_id!r} already declares a different {key}: {block[present[key]]!r}")
            continue
        new_lines.append(rendered)
    anchor = present.get("continuidad_id", present["id"])
    return [*block[: anchor + 1], *new_lines, *block[anchor + 1 :]]


def _casilla_files(modelo_id: str, revision: str) -> Iterator[Path]:
    yield from sorted((_MODELOS_ROOT / modelo_id / "revisions" / revision / "casillas").rglob("*.toml"))


def apply_plan(plan: LineagePlan) -> int:
    """Write a plan's edits into the declaration files; return the number of rows edited."""
    by_revision: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(dict)
    for (revision, casilla_id), keys in plan.edits.items():
        by_revision[revision][casilla_id] = keys
    edited = 0
    for revision, edits in sorted(by_revision.items()):
        remaining = dict(edits)
        for path in _casilla_files(plan.modelo, revision):
            text = path.read_text(encoding=_UTF_8)
            new_text, done = insert_lineage_keys(text, revision, remaining)
            if new_text != text:
                path.write_text(new_text, encoding=_UTF_8, newline="\n")
            for casilla_id in done:
                remaining.pop(casilla_id)
            edited += len(done)
        if remaining:
            raise ValueError(f"modelo {plan.modelo} {revision}: rows not found on disk: {sorted(remaining)[:5]}")
    return edited

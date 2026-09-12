"""Rewrite every row-producing binding's value contract onto the row-set shape.

A binding whose ``aggregation.op`` is ``rows`` yields a *row collection*, and
the value contract now says so on the channel axis alone:
``channel = "row_set"`` is the transport, ``data_type`` is the **per-row element
type** (``money``, ``integer``, ``boolean``, ``text``, ``date``, ``enum``). The
retired ``rows`` data type conflated the two, which left the corpus with two contradictory
authoring styles for the same fact:

- ``data_type = "rows", channel = "row_set"`` -- the transport stated twice and
  the element type displaced onto the provider's own ``data_type`` field.
- ``data_type = "text", channel = "text"`` -- the element type stated correctly
  and the row collection not stated at all, so the row family read as a scalar.

This tool normalises both onto the one shape. The element type is read from the
provider's ``data_type`` field where it carries one, and otherwise from the
already-authored scalar ``data_type``.

There are two row channels, and ``row_grouping`` distinguishes them. A family
enrolled in :data:`~cadrumo.core.aggregation.ROW_SET_GROUPING_FOR_BINDING_SOURCE`
is assembled by the grouped row-set assembler and names its grouping axis. The
rest emit rows provider-natively -- the invoice catalogue resolver its detail
rows, the inventory resolver its row binding values, the profile resolver its
repeating collections -- and declare no grouping at all. A grouping is never
invented for them: the row-assembly dispatcher is closed, so a grouping no
assembler consumes would fall through at resolve time instead of failing here.

The rewrite is textual and in place, one ``value = { ... }`` line at a time, so
comments, citations, and key order survive. Every rewritten row is validated as
a ``BindingDefinition`` and every rewritten file is re-parsed and re-validated
before a byte is written; a file with any refusal is left untouched entirely.

Usage::

    uv run --no-sync python -m dev.registry.fix_binding_row_set_contracts --all --dry-run --report out.json
    uv run --no-sync python -m dev.registry.fix_binding_row_set_contracts --all
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cadrumo.core.aggregation import ROW_SET_GROUPING_FOR_BINDING_SOURCE, BindingSourceKind
from cadrumo.domain.calculations.registry.schema import BindingDefinition

from .convert_binding_provider_shape import (
    BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE,
    REGISTRY_MODELOS_ROOT,
)

__all__ = [
    "FixReport",
    "RowSetRefusalError",
    "fix_file",
    "fix_modelo",
    "main",
    "row_set_value_for",
]

_BINDINGS_HEADER = re.compile(r"""^\[\[revisions\.(?:"(?P<quoted>[^"]+)"|(?P<bare>[^.\]]+))\.bindings\]\]""")
_VALUE_LINE = re.compile(r"^(?P<indent>\s*)value\s*=\s*\{")

_ROWS_OP = "rows"
_RETIRED_ROWS_DATA_TYPE = "rows"
_ROW_SET_CHANNEL = "row_set"


class RowSetRefusalError(Exception):
    """One binding row the tool declines to rewrite, with the reason stated."""

    def __init__(self, binding_id: str, reason: str) -> None:
        """Record the refused binding's id and the reason it was declined."""
        super().__init__(f"{binding_id}: {reason}")
        self.binding_id = binding_id
        self.reason = reason


@dataclass
class FixReport:
    """What the run did, per modelo and in total."""

    modelos: list[str] = field(default_factory=list)
    rows_fixed_by_modelo: Counter[str] = field(default_factory=Counter)
    rows_already_correct: int = 0
    files_rewritten: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    refusals: list[dict[str, str]] = field(default_factory=list)

    @property
    def rows_fixed(self) -> int:
        """Return the total number of rewritten rows across every modelo."""
        return sum(self.rows_fixed_by_modelo.values())

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable summary of the run."""
        return {
            "modelos": self.modelos,
            "rows_fixed": self.rows_fixed,
            "rows_fixed_by_modelo": dict(sorted(self.rows_fixed_by_modelo.items())),
            "rows_already_correct": self.rows_already_correct,
            "files_rewritten": self.files_rewritten,
            "files_skipped": self.files_skipped,
            "refusals": self.refusals,
        }


def _element_data_type(binding_id: str, provider: dict[str, Any], value: dict[str, Any]) -> str:
    """Return the per-row element data type for one row-producing binding.

    The provider's own ``data_type`` field is the more authoritative statement
    where it exists -- under the retired shape it is the only place the element
    type survived. Otherwise the already-authored scalar ``data_type`` is the
    element type, mis-channelled but not mis-typed.

    Raises:
        RowSetRefusalError: Neither field yields a scalar element type.
    """
    for candidate in (provider.get("data_type"), value.get("data_type")):
        if not isinstance(candidate, str) or candidate == _RETIRED_ROWS_DATA_TYPE:
            continue
        mapped = BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE.get(candidate)
        if mapped is not None:
            return mapped.value
        raise RowSetRefusalError(binding_id, f"element data type {candidate!r} is not a known binding data type")
    raise RowSetRefusalError(binding_id, "no per-row element data type on the provider or the value contract")


def row_set_value_for(row: dict[str, Any]) -> dict[str, Any]:
    """Return the row-set value contract one row-producing binding should carry.

    A family enrolled in
    :data:`~cadrumo.core.aggregation.ROW_SET_GROUPING_FOR_BINDING_SOURCE` is
    assembled by the grouped row-set assembler and names its grouping axis. The
    remaining row-producing families emit their rows provider-natively -- the
    invoice catalogue resolver its detail rows, the inventory resolver its row
    binding values, the profile resolver its repeating collections -- and
    declare no grouping, because no grouped assembler consumes them and an
    invented grouping would fall through the closed dispatcher at resolve time.

    Raises:
        RowSetRefusalError: The source is unknown or yields no per-row element
            type.
    """
    binding_id = str(row.get("id", "?"))
    provider = row.get("provider")
    provider = dict(provider) if isinstance(provider, dict) else {}
    value = row.get("value")
    value = dict(value) if isinstance(value, dict) else {}

    raw_kind = provider.get("kind")
    try:
        kind = BindingSourceKind(raw_kind)
    except ValueError as exc:
        raise RowSetRefusalError(binding_id, f"unknown provider kind {raw_kind!r}") from exc

    contract: dict[str, Any] = {
        "data_type": _element_data_type(binding_id, provider, value),
        "channel": _ROW_SET_CHANNEL,
    }
    grouping = ROW_SET_GROUPING_FOR_BINDING_SOURCE.get(kind)
    if grouping is not None:
        contract["row_grouping"] = grouping.value
    typed_enum = value.get("typed_enum")
    if isinstance(typed_enum, str):
        contract["typed_enum"] = typed_enum
    return contract


def _is_rows_binding(row: dict[str, Any]) -> bool:
    aggregation = row.get("aggregation")
    return isinstance(aggregation, dict) and bool(aggregation.get("op") == _ROWS_OP)


def _already_correct(row: dict[str, Any], contract: dict[str, Any]) -> bool:
    value = row.get("value")
    return isinstance(value, dict) and dict(value) == contract


def _toml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _toml_inline_table(table: dict[str, Any]) -> str:
    body = ", ".join(f"{key} = {_toml_scalar(item)}" for key, item in table.items())
    return f"{{ {body} }}"


def _as_tuples(value: object) -> object:
    """Return ``value`` with every list turned into a tuple, recursively."""
    if isinstance(value, list):
        return tuple(_as_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _as_tuples(item) for key, item in value.items()}
    return value


def _validated(row: dict[str, Any], contract: dict[str, Any]) -> None:
    """Construct the rewritten row as a ``BindingDefinition``, raising on refusal."""
    candidate = dict(row)
    candidate["value"] = contract
    try:
        BindingDefinition.model_validate(_as_tuples(candidate))
    except Exception as exc:
        raise RowSetRefusalError(str(row.get("id", "?")), f"rewritten row does not validate: {exc}") from exc


def _value_line_indices(lines: list[str]) -> list[tuple[str, int]]:
    """Return ``(revision, line index)`` of each binding block's ``value`` line.

    One entry per ``[[revisions."X".bindings]]`` element in document order; a
    block with no top-level ``value`` line yields ``-1`` so the row ordinals
    still line up with the parsed document.
    """
    located: list[tuple[str, int]] = []
    index = 0
    while index < len(lines):
        header = _BINDINGS_HEADER.match(lines[index])
        if header is None:
            index += 1
            continue
        revision = header.group("quoted") or header.group("bare")
        cursor = index + 1
        value_index = -1
        while cursor < len(lines) and not lines[cursor].lstrip().startswith("["):
            if value_index < 0 and _VALUE_LINE.match(lines[cursor]):
                value_index = cursor
            cursor += 1
        located.append((revision, value_index))
        index = cursor if cursor > index else index + 1
    return located


def fix_file(path: Path, report: FixReport, modelo: str, *, apply: bool) -> None:
    """Normalise every row-producing binding in one fragment, or skip the file."""
    original = path.read_text(encoding="utf-8", newline="")
    line_ending = "\r\n" if "\r\n" in original else "\n"
    document = tomllib.loads(original)
    rows_by_revision: dict[str, list[dict[str, Any]]] = {}
    for revision, table in (document.get("revisions") or {}).items():
        if isinstance(table, dict) and isinstance(table.get("bindings"), list):
            rows_by_revision[revision] = [row for row in table["bindings"] if isinstance(row, dict)]
    if not rows_by_revision:
        return

    lines = original.splitlines(keepends=True)
    located = _value_line_indices(lines)
    seen: Counter[str] = Counter()
    planned: list[tuple[int, dict[str, Any]]] = []
    refusals: list[dict[str, str]] = []
    already = 0

    for revision, value_index in located:
        ordinal = seen[revision]
        seen[revision] += 1
        rows = rows_by_revision.get(revision, [])
        if ordinal >= len(rows):
            refusals.append({"file": str(path), "binding_id": "*", "reason": "text and parsed row order disagree"})
            break
        row = rows[ordinal]
        if not _is_rows_binding(row):
            continue
        try:
            contract = row_set_value_for(row)
            if _already_correct(row, contract):
                already += 1
                continue
            if value_index < 0:
                raise RowSetRefusalError(str(row.get("id", "?")), "no top-level value line to rewrite")
            _validated(row, contract)
        except RowSetRefusalError as refusal:
            refusals.append({"file": str(path), "binding_id": refusal.binding_id, "reason": refusal.reason})
            continue
        planned.append((value_index, contract))

    report.rows_already_correct += already
    if refusals:
        report.refusals.extend(refusals)
        report.files_skipped.append(str(path))
        return
    if not planned:
        return

    rewritten = list(lines)
    for value_index, contract in sorted(planned, key=lambda item: item[0], reverse=True):
        indent = _VALUE_LINE.match(rewritten[value_index])
        prefix = indent.group("indent") if indent else ""
        rewritten[value_index] = f"{prefix}value = {_toml_inline_table(contract)}{line_ending}"
    new_text = "".join(rewritten)

    try:
        reparsed = tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:
        report.refusals.append({"file": str(path), "binding_id": "*", "reason": f"rewritten file is not TOML: {exc}"})
        report.files_skipped.append(str(path))
        return
    try:
        for table in (reparsed.get("revisions") or {}).values():
            for row in table.get("bindings") or []:
                BindingDefinition.model_validate(_as_tuples(row))
    except Exception as exc:
        report.refusals.append({"file": str(path), "binding_id": "*", "reason": f"rewritten file rejected: {exc}"})
        report.files_skipped.append(str(path))
        return

    report.rows_fixed_by_modelo[modelo] += len(planned)
    report.files_rewritten.append(str(path))
    if apply:
        # Write bytes so the textual rewrite preserves the source line ending
        # exactly on Windows as well as POSIX. ``Path.write_text(...,
        # newline="")`` is not accepted consistently by the Python 3.13
        # Windows runtime used by the registry tools.
        path.write_bytes(new_text.encode("utf-8"))


def fix_modelo(modelo: str, report: FixReport, *, apply: bool, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> None:
    """Normalise every bindings fragment of one modelo."""
    revisions = modelos_root / modelo / "revisions"
    if not revisions.is_dir():
        report.refusals.append({"file": str(modelos_root / modelo), "binding_id": "*", "reason": "no revisions tree"})
        return
    report.modelos.append(modelo)
    for revision_dir in sorted(p for p in revisions.iterdir() if p.is_dir()):
        bindings_dir = revision_dir / "bindings"
        if not bindings_dir.is_dir():
            continue
        for toml_path in sorted(bindings_dir.glob("*.toml")):
            fix_file(toml_path, report, modelo, apply=apply)


def _all_modelos(modelos_root: Path) -> list[str]:
    return sorted(p.name for p in modelos_root.iterdir() if p.is_dir() and (p / "revisions").is_dir())


def main(argv: list[str] | None = None) -> int:
    """Run the normalisation and return the process exit code."""
    parser = argparse.ArgumentParser(description="Normalise row-producing binding value contracts.")
    parser.add_argument("--modelo", action="append", default=[], help="Modelo to fix; repeatable.")
    parser.add_argument("--all", action="store_true", help="Fix every modelo carrying a revisions tree.")
    parser.add_argument("--dry-run", action="store_true", help="Report the rewrite without writing any file.")
    parser.add_argument("--report", type=Path, default=None, help="Write the JSON summary to this path.")
    args = parser.parse_args(argv)

    if not args.modelo and not args.all:
        parser.error("pass --modelo <id> at least once, or --all")
    modelos = _all_modelos(REGISTRY_MODELOS_ROOT) if args.all else list(dict.fromkeys(args.modelo))

    report = FixReport()
    for modelo in modelos:
        fix_modelo(modelo, report, apply=not args.dry_run)

    summary = report.as_dict()
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    mode = "dry-run" if args.dry_run else "applied"
    print(f"Rows fixed: {summary['rows_fixed']} across {len(summary['files_rewritten'])} files [{mode}]")
    for modelo, count in summary["rows_fixed_by_modelo"].items():
        print(f"  modelo {modelo}: {count}")
    print(f"Rows already on the row-set shape: {summary['rows_already_correct']}")
    if summary["refusals"]:
        print(f"Refused rows ({len(summary['refusals'])}); their files were left untouched:")
        by_reason: dict[str, list[str]] = defaultdict(list)
        for refusal in summary["refusals"]:
            by_reason[refusal["reason"]].append(refusal["binding_id"])
        for reason, ids in sorted(by_reason.items()):
            unique = sorted(set(ids))
            print(f"  {reason} ({len(unique)}): {', '.join(unique[:8])}{' ...' if len(unique) > 8 else ''}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

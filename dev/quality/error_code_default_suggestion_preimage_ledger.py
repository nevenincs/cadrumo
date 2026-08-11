"""Fail-closed historical ledger for retired error-code default suggestions.

The campaign removed ``ErrorCode.default_suggestion`` from the live runtime
model.  This module keeps the *preimage* of that deleted authority separately
from the live CLI action census: it reads the immutable source commit with
``git show``, extracts each former declaration with Python's AST, and requires
the checked-in ledger to match the complete ordered source multiset.

The ledger is migration evidence only.  It must never become a runtime action
or no-recovery authority.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

__all__ = [
    "DEFAULT_PREIMAGE_LEDGER_PATH",
    "SOURCE_COMMIT",
    "ErrorCodeDefaultPreimageError",
    "ErrorCodeDefaultPreimageRecord",
    "extract_preimage_records",
    "load_preimage_ledger",
    "main",
    "render_preimage_ledger",
    "validate_preimage_ledger",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_PREIMAGE_LEDGER_PATH: Final[Path] = (
    REPO_ROOT / "dev" / "quality" / "error_code_default_suggestion_preimage.json"
)
SOURCE_COMMIT: Final[str] = "930ef9f4017a23cccaf4990d287beb014fc9723c"
_SCHEMA_VERSION: Final[int] = 1
_UTF_8: Final[str] = "utf-8"
_RECORD_FIELDS: Final[tuple[str, ...]] = (
    "source_commit",
    "error_code",
    "error_qualname",
    "source_shard",
    "old_value_source",
    "disposition_owner_step",
    "source_line",
    "source_column",
)
_SOURCE_SHARD_OWNERS: Final[dict[str, tuple[str, str]]] = {
    "src/cadrumo/core/errors/registry/_core.py": ("core", "S50"),
    "src/cadrumo/core/errors/registry/_application_part1.py": ("application_part1", "S51"),
    "src/cadrumo/core/errors/registry/_application_part2.py": ("application_part2", "S52"),
    "src/cadrumo/core/errors/registry/_domain_part1.py": ("domain_part1", "S53"),
    "src/cadrumo/core/errors/registry/_domain_part2.py": ("domain_part2", "S54"),
    "src/cadrumo/core/errors/registry/_domain_part3.py": ("domain_part3", "S55"),
    "src/cadrumo/core/errors/registry/_adapters_part1.py": ("adapters_part1", "S56"),
    "src/cadrumo/core/errors/registry/_adapters_part2.py": ("adapters_part2", "S57"),
    "src/cadrumo/core/errors/registry/_entrypoints.py": ("entrypoints", "S64"),
}
_SOURCE_SHARDS: Final[dict[str, str]] = {
    source_shard: owner_step for source_shard, owner_step in _SOURCE_SHARD_OWNERS.values()
}


class ErrorCodeDefaultPreimageError(ValueError):
    """Raised when the historical evidence cannot prove exact preimage coverage."""


@dataclass(frozen=True, slots=True)
class ErrorCodeDefaultPreimageRecord:
    """One source-located historical ``ErrorCode.default_suggestion`` declaration."""

    source_commit: str
    error_code: str
    error_qualname: str
    source_shard: str
    old_value_source: str
    disposition_owner_step: str
    source_line: int
    source_column: int

    @property
    def source_identity(self) -> tuple[str, str, str, str, str, int, int]:
        """Return the source identity independently of the assigned owner Step."""
        return (
            self.source_commit,
            self.error_code,
            self.error_qualname,
            self.source_shard,
            self.old_value_source,
            self.source_line,
            self.source_column,
        )

    @property
    def identity(self) -> tuple[str, str, str, str, str, int, int, str]:
        """Return the complete evidence identity, including exclusive ownership."""
        return (*self.source_identity, self.disposition_owner_step)


def _is_error_code_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "ErrorCode"


def _string_constant(node: ast.AST | None, *, field: str, path: str, line: int) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value:
        raise ErrorCodeDefaultPreimageError(f"{path}:{line}: ErrorCode {field} must be a non-empty string literal")
    return node.value


def _call_keywords(node: ast.Call, *, path: str) -> dict[str, ast.expr]:
    keywords: dict[str, ast.expr] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            raise ErrorCodeDefaultPreimageError(f"{path}:{node.lineno}: ErrorCode may not unpack keyword arguments")
        if keyword.arg in keywords:
            raise ErrorCodeDefaultPreimageError(f"{path}:{node.lineno}: ErrorCode repeats {keyword.arg!r}")
        keywords[keyword.arg] = keyword.value
    return keywords


def _qualname_for_call(node: ast.Call, parents: dict[int, ast.AST], *, path: str) -> str:
    parent = parents.get(id(node))
    if not isinstance(parent, ast.Tuple) or len(parent.elts) != 2 or parent.elts[1] is not node:
        raise ErrorCodeDefaultPreimageError(
            f"{path}:{node.lineno}: ErrorCode declaration must be the second member of a qualname pair",
        )
    return _string_constant(parent.elts[0], field="qualname", path=path, line=node.lineno)


def _source_for(path: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed executable and immutable repository object
        ["git", "show", f"{SOURCE_COMMIT}:{path}"],  # noqa: S607 - Git is the repository authority
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    return completed.stdout.decode(_UTF_8)


def _source_location(node: ast.AST, *, path: str) -> tuple[int, int]:
    attributes = cast(dict[str, object], vars(node))
    source_line = attributes.get("lineno")
    source_column = attributes.get("col_offset")
    if type(source_line) is not int or source_line < 1 or type(source_column) is not int or source_column < 0:
        raise ErrorCodeDefaultPreimageError(f"{path}: ErrorCode default_suggestion has no usable source location")
    return source_line, source_column


def _records_from_source(path: str, source_shard: str, owner_step: str) -> tuple[ErrorCodeDefaultPreimageRecord, ...]:
    source = _source_for(path)
    tree = ast.parse(source, filename=path)
    parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    records: list[ErrorCodeDefaultPreimageRecord] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_error_code_call(node):
            continue
        keywords = _call_keywords(node, path=path)
        missing = {"code", "default_suggestion"}.difference(keywords)
        if missing:
            names = ", ".join(sorted(missing))
            raise ErrorCodeDefaultPreimageError(f"{path}:{node.lineno}: ErrorCode is missing {names}")
        old_value = keywords["default_suggestion"]
        old_value_source = ast.get_source_segment(source, old_value)
        if old_value_source is None:
            raise ErrorCodeDefaultPreimageError(f"{path}:{node.lineno}: cannot recover default_suggestion source")
        source_line, source_column = _source_location(old_value, path=path)
        records.append(
            ErrorCodeDefaultPreimageRecord(
                source_commit=SOURCE_COMMIT,
                error_code=_string_constant(keywords["code"], field="code", path=path, line=node.lineno),
                error_qualname=_qualname_for_call(node, parents, path=path),
                source_shard=source_shard,
                old_value_source=old_value_source,
                disposition_owner_step=owner_step,
                source_line=source_line,
                source_column=source_column,
            ),
        )
    return tuple(sorted(records, key=lambda record: (record.source_line, record.source_column)))


def extract_preimage_records() -> tuple[ErrorCodeDefaultPreimageRecord, ...]:
    """AST-extract the complete retired default-suggestion preimage from Git."""
    return tuple(
        record
        for path, (source_shard, owner_step) in _SOURCE_SHARD_OWNERS.items()
        for record in _records_from_source(path, source_shard, owner_step)
    )


def _record_values(record: ErrorCodeDefaultPreimageRecord) -> list[object]:
    return [
        record.source_commit,
        record.error_code,
        record.error_qualname,
        record.source_shard,
        record.old_value_source,
        record.disposition_owner_step,
        record.source_line,
        record.source_column,
    ]


def render_preimage_ledger(records: tuple[ErrorCodeDefaultPreimageRecord, ...]) -> str:
    """Render the one canonical JSON representation for reviewed preimage rows."""
    _validate_record_shapes(records)
    metadata = json.dumps(
        {
            "schema_version": _SCHEMA_VERSION,
            "source_commit": SOURCE_COMMIT,
            "record_fields": _RECORD_FIELDS,
        },
    )
    lines = [
        "{",
        f'  "meta": {metadata},',
        '  "records": [',
    ]
    lines.extend(
        f"    {json.dumps(_record_values(record), ensure_ascii=False)}{',' if index + 1 < len(records) else ''}"
        for index, record in enumerate(records)
    )
    lines.extend(["  ]", "}", ""])
    return "\n".join(lines)


def _error_strings(errors: list[str]) -> ErrorCodeDefaultPreimageError:
    return ErrorCodeDefaultPreimageError("\n".join(sorted(errors)))


def _record_from_values(index: int, values: object, source_commit: str) -> ErrorCodeDefaultPreimageRecord:
    if not isinstance(values, list):
        raise ErrorCodeDefaultPreimageError(f"records[{index}] must be an eight-value array")
    raw = cast(list[object], values)
    if len(raw) != len(_RECORD_FIELDS):
        raise ErrorCodeDefaultPreimageError(f"records[{index}] must be an eight-value array")
    strings = raw[:6]
    if not all(isinstance(value, str) and value for value in strings):
        raise ErrorCodeDefaultPreimageError(f"records[{index}] has an empty or non-string identity field")
    row_commit, error_code, error_qualname, source_shard, old_value_source, owner_step = cast(
        tuple[str, str, str, str, str, str],
        tuple(strings),
    )
    if row_commit != source_commit:
        raise ErrorCodeDefaultPreimageError(f"records[{index}] source_commit disagrees with meta.source_commit")
    source_line, source_column = raw[6:]
    if type(source_line) is not int or source_line < 1 or type(source_column) is not int or source_column < 0:
        raise ErrorCodeDefaultPreimageError(f"records[{index}] has an invalid source location")
    return ErrorCodeDefaultPreimageRecord(
        source_commit=row_commit,
        error_code=error_code,
        error_qualname=error_qualname,
        source_shard=source_shard,
        old_value_source=old_value_source,
        disposition_owner_step=owner_step,
        source_line=source_line,
        source_column=source_column,
    )


def _validate_record_shapes(records: tuple[ErrorCodeDefaultPreimageRecord, ...]) -> None:
    errors: list[str] = []
    identities: Counter[tuple[str, str, str, str, str, int, int]] = Counter()
    for index, record in enumerate(records):
        if record.source_commit != SOURCE_COMMIT:
            errors.append(f"records[{index}] source_commit must be immutable preimage commit {SOURCE_COMMIT}")
        expected_owner = _SOURCE_SHARDS.get(record.source_shard)
        if expected_owner is None:
            errors.append(f"records[{index}] has unknown source_shard {record.source_shard!r}")
        elif record.disposition_owner_step != expected_owner:
            errors.append(
                f"records[{index}] owner {record.disposition_owner_step!r} must be {expected_owner!r} "
                f"for {record.source_shard}",
            )
        identities[record.source_identity] += 1
    for identity, count in identities.items():
        if count > 1:
            errors.append(f"ledger duplicates source identity {identity!r}")
    if errors:
        raise _error_strings(errors)


def load_preimage_ledger(path: Path = DEFAULT_PREIMAGE_LEDGER_PATH) -> tuple[ErrorCodeDefaultPreimageRecord, ...]:
    """Load only the exact historical-ledger schema; no legacy shape is tolerated."""
    try:
        payload = cast(object, json.loads(path.read_text(encoding=_UTF_8)))
    except (OSError, json.JSONDecodeError) as error:
        raise ErrorCodeDefaultPreimageError(f"cannot read error-code preimage ledger {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ErrorCodeDefaultPreimageError("preimage ledger must contain exactly meta and records")
    document = cast(dict[str, object], payload)
    if set(document) != {"meta", "records"}:
        raise ErrorCodeDefaultPreimageError("preimage ledger must contain exactly meta and records")
    meta = document["meta"]
    if not isinstance(meta, dict):
        raise ErrorCodeDefaultPreimageError("preimage ledger meta has an unrecognized schema")
    metadata = cast(dict[str, object], meta)
    if set(metadata) != {"schema_version", "source_commit", "record_fields"}:
        raise ErrorCodeDefaultPreimageError("preimage ledger meta has an unrecognized schema")
    if metadata["schema_version"] != _SCHEMA_VERSION:
        raise ErrorCodeDefaultPreimageError(f"preimage ledger schema_version must be {_SCHEMA_VERSION}")
    source_commit = metadata["source_commit"]
    if source_commit != SOURCE_COMMIT:
        raise ErrorCodeDefaultPreimageError(f"preimage ledger source_commit must be {SOURCE_COMMIT}")
    if metadata["record_fields"] != list(_RECORD_FIELDS):
        raise ErrorCodeDefaultPreimageError("preimage ledger record_fields must be the canonical schema order")
    values = document["records"]
    if not isinstance(values, list):
        raise ErrorCodeDefaultPreimageError("preimage ledger records must be an array")
    raw_records = cast(list[object], values)
    records = tuple(_record_from_values(index, value, SOURCE_COMMIT) for index, value in enumerate(raw_records))
    _validate_record_shapes(records)
    return records


def _describe_records(records: Counter[tuple[str, str, str, str, str, int, int]]) -> list[str]:
    return [repr(identity) for identity, count in sorted(records.items()) for _ in range(count)]


def validate_preimage_ledger(
    records: tuple[ErrorCodeDefaultPreimageRecord, ...],
) -> tuple[ErrorCodeDefaultPreimageRecord, ...]:
    """Require ordered, source-located multiset equality with the Git preimage."""
    _validate_record_shapes(records)
    expected = extract_preimage_records()
    expected_by_source = {record.source_identity: record for record in expected}
    actual_by_source = {record.source_identity: record for record in records}
    expected_counter = Counter(record.source_identity for record in expected)
    actual_counter = Counter(record.source_identity for record in records)
    errors: list[str] = []
    missing = expected_counter - actual_counter
    extra = actual_counter - expected_counter
    if missing:
        errors.append(f"preimage ledger is missing source identities: {_describe_records(missing)!r}")
    if extra:
        errors.append(f"preimage ledger has extra source identities: {_describe_records(extra)!r}")
    for identity in sorted(expected_counter.keys() & actual_counter.keys()):
        expected_owner = expected_by_source[identity].disposition_owner_step
        actual_owner = actual_by_source[identity].disposition_owner_step
        if actual_owner != expected_owner:
            errors.append(f"preimage ledger owner drift for {identity!r}: {actual_owner!r} != {expected_owner!r}")
    if not errors and records != expected:
        errors.append("preimage ledger rows must retain canonical source order")
    if errors:
        raise _error_strings(errors)
    return records


def main(argv: list[str] | None = None) -> int:
    """Check the checked-in historical ledger against its immutable Git source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_PREIMAGE_LEDGER_PATH)
    parser.add_argument("--json", action="store_true", help="render checked ledger rows as JSON")
    arguments = parser.parse_args(argv)
    try:
        records = validate_preimage_ledger(load_preimage_ledger(arguments.ledger))
    except ErrorCodeDefaultPreimageError as error:
        print(error)
        return 1
    if arguments.json:
        print(render_preimage_ledger(records), end="")
    else:
        print(f"error-code default-suggestion preimage rows {len(records)}")
        print(f"source commit {SOURCE_COMMIT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

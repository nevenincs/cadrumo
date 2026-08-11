"""Fail-closed, non-runtime rehoming ledger for retired error defaults.

This module owns only the typed representation and strict TOML boundary for
the historical-default rehoming join.  It intentionally contains no recovery
policy, rendered text, command identity, or locale data.
"""

from __future__ import annotations

import argparse
import ast
import tomllib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, cast

from dev.error_code_default_suggestion_preimage_ledger import (
    SOURCE_COMMIT,
    ErrorCodeDefaultPreimageError,
    ErrorCodeDefaultPreimageRecord,
    load_preimage_ledger,
    validate_preimage_ledger,
)

__all__ = [
    "DEFAULT_REHOMING_LEDGER_PATH",
    "DispositionKind",
    "HistoricalKey",
    "RehomingLedger",
    "RehomingLedgerError",
    "RehomingRow",
    "SourceFingerprint",
    "load_rehoming_ledger",
    "main",
]


REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_REHOMING_LEDGER_PATH: Final[Path] = REPO_ROOT / "dev" / "error_code_default_recovery_rehoming.toml"
_UTF_8: Final[str] = "utf-8"
_SCHEMA_VERSION: Final[int] = 1
_STEP_PREFIX: Final[str] = "S"
_TOP_LEVEL_FIELDS: Final[frozenset[str]] = frozenset({"meta", "rehoming"})
_META_FIELDS: Final[frozenset[str]] = frozenset({"schema_version"})
_ROW_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "historical_error_code",
        "historical_error_qualname",
        "historical_source_shard",
        "historical_old_value_source",
        "historical_source_line",
        "historical_source_column",
        "disposition_kind",
        "current_error_qualname",
        "current_owner_step",
        "fingerprints",
    },
)
_FINGERPRINT_FIELDS: Final[frozenset[str]] = frozenset({"path", "line", "column", "context", "kind"})
_FINGERPRINT_KINDS: Final[frozenset[str]] = frozenset({"constructor", "reference"})


class RehomingLedgerError(ValueError):
    """Raised when the rehoming ledger cannot prove an exact source join."""

    def __init__(self, errors: Iterable[str]) -> None:
        """Normalize diagnostics before exposing the parse failure."""
        self.errors = tuple(sorted(set(errors)))
        super().__init__("\n".join(self.errors))


class DispositionKind(StrEnum):
    """The closed evidence states permitted in a rehoming row."""

    MIGRATION_REQUIRED = "migration_required"
    VERIFIED_TYPED_ACTION = "verified_typed_action"
    VERIFIED_TERMINAL_NO_RECOVERY = "verified_terminal_no_recovery"
    VERIFIED_NONPRODUCER_REFERENCE = "verified_nonproducer_reference"
    RETIRED_OR_UNREACHABLE = "retired_or_unreachable"


@dataclass(frozen=True, slots=True)
class HistoricalKey:
    """The immutable identity of one non-null retired default declaration."""

    source_commit: str
    error_code: str
    error_qualname: str
    source_shard: str
    old_value_source: str
    historical_owner_step: str
    source_line: int
    source_column: int

    @classmethod
    def from_preimage(cls, record: ErrorCodeDefaultPreimageRecord) -> HistoricalKey:
        """Convert a source-proven immutable preimage row without reinterpretation."""
        return cls(
            source_commit=record.source_commit,
            error_code=record.error_code,
            error_qualname=record.error_qualname,
            source_shard=record.source_shard,
            old_value_source=record.old_value_source,
            historical_owner_step=record.disposition_owner_step,
            source_line=record.source_line,
            source_column=record.source_column,
        )

    @property
    def source_identity(self) -> tuple[str, str, str, str, str, int, int]:
        """Return the immutable source identity independent of old allocation."""
        return (
            self.source_commit,
            self.error_code,
            self.error_qualname,
            self.source_shard,
            self.old_value_source,
            self.source_line,
            self.source_column,
        )


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """One exact current-tree physical observation, without policy payload."""

    path: str
    line: int
    column: int
    context: str
    kind: Literal["constructor", "reference"]

    @property
    def identity(self) -> tuple[str, int, int, str, str]:
        """Return the complete source locator for exact reconciliation."""
        return (self.path, self.line, self.column, self.context, self.kind)


@dataclass(frozen=True, slots=True)
class RehomingRow:
    """One evidence-only join from a retired declaration to current source."""

    historical: HistoricalKey
    disposition_kind: DispositionKind
    current_error_qualname: str | None
    current_owner_step: str | None
    fingerprints: tuple[SourceFingerprint, ...]


@dataclass(frozen=True, slots=True)
class RehomingLedger:
    """The complete, exact join over every historical non-null declaration."""

    rows: tuple[RehomingRow, ...]


def _nonempty_string(
    table: dict[str, object],
    field: str,
    *,
    context: str,
    errors: list[str],
) -> str | None:
    value = table.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        errors.append(f"{context}: {field} must be a non-empty, trimmed string")
        return None
    return value


def _positive_integer(
    table: dict[str, object],
    field: str,
    *,
    minimum: int,
    context: str,
    errors: list[str],
) -> int | None:
    value = table.get(field)
    if type(value) is not int or value < minimum:
        errors.append(f"{context}: {field} must be an integer >= {minimum}")
        return None
    return value


def _parse_fingerprint(value: object, *, context: str, errors: list[str]) -> SourceFingerprint | None:
    if not isinstance(value, dict):
        errors.append(f"{context}: must be an inline table")
        return None
    table = cast(dict[str, object], value)
    unknown = sorted(set(table) - _FINGERPRINT_FIELDS)
    missing = sorted(_FINGERPRINT_FIELDS - set(table))
    if unknown:
        errors.append(f"{context}: unrecognized field(s): {', '.join(unknown)}")
    if missing:
        errors.append(f"{context}: missing field(s): {', '.join(missing)}")
    path = _nonempty_string(table, "path", context=context, errors=errors)
    line = _positive_integer(table, "line", minimum=1, context=context, errors=errors)
    column = _positive_integer(table, "column", minimum=0, context=context, errors=errors)
    source_context = _nonempty_string(table, "context", context=context, errors=errors)
    raw_kind = _nonempty_string(table, "kind", context=context, errors=errors)
    if raw_kind not in _FINGERPRINT_KINDS:
        errors.append(f"{context}: kind must be constructor or reference")
        return None
    if path is None or line is None or column is None or source_context is None:
        return None
    return SourceFingerprint(path, line, column, source_context, cast(Literal["constructor", "reference"], raw_kind))


def _parse_fingerprints(
    table: dict[str, object], *, context: str, errors: list[str]
) -> tuple[SourceFingerprint, ...] | None:
    value = table.get("fingerprints")
    if not isinstance(value, list) or not value:
        errors.append(f"{context}: fingerprints must be a non-empty array")
        return None
    values = cast(list[object], value)
    records = [
        record
        for index, item in enumerate(values, start=1)
        if (record := _parse_fingerprint(item, context=f"{context}.fingerprints[{index}]", errors=errors)) is not None
    ]
    if len(records) != len(values):
        return None
    if len({record.identity for record in records}) != len(records):
        errors.append(f"{context}: fingerprints must not contain duplicates")
        return None
    return tuple(sorted(records, key=lambda record: record.identity))


def _is_step_id(value: str) -> bool:
    return value.startswith(_STEP_PREFIX) and value[len(_STEP_PREFIX) :].isdigit()


def _parse_row(value: object, *, context: str, errors: list[str]) -> RehomingRow | None:
    if not isinstance(value, dict):
        errors.append(f"{context}: must be a table")
        return None
    table = cast(dict[str, object], value)
    unknown = sorted(set(table) - _ROW_FIELDS)
    if unknown:
        errors.append(f"{context}: unrecognized field(s): {', '.join(unknown)}")
    historical_error_code = _nonempty_string(table, "historical_error_code", context=context, errors=errors)
    historical_error_qualname = _nonempty_string(table, "historical_error_qualname", context=context, errors=errors)
    historical_source_shard = _nonempty_string(table, "historical_source_shard", context=context, errors=errors)
    historical_old_value_source = _nonempty_string(table, "historical_old_value_source", context=context, errors=errors)
    historical_source_line = _positive_integer(
        table, "historical_source_line", minimum=1, context=context, errors=errors
    )
    historical_source_column = _positive_integer(
        table, "historical_source_column", minimum=0, context=context, errors=errors
    )
    raw_disposition = _nonempty_string(table, "disposition_kind", context=context, errors=errors)
    try:
        disposition_kind = DispositionKind(raw_disposition) if raw_disposition is not None else None
    except ValueError:
        errors.append(f"{context}: disposition_kind is not recognized")
        disposition_kind = None

    current_fields = {"current_error_qualname", "current_owner_step", "fingerprints"}
    present_current = current_fields & set(table)
    has_current = bool(present_current)
    if has_current and present_current != current_fields:
        errors.append(f"{context}: current source evidence must carry all current fields")
    current_error_qualname: str | None = None
    current_owner_step: str | None = None
    fingerprints: tuple[SourceFingerprint, ...] = ()
    if has_current:
        current_error_qualname = _nonempty_string(table, "current_error_qualname", context=context, errors=errors)
        current_owner_step = _nonempty_string(table, "current_owner_step", context=context, errors=errors)
        if current_owner_step is not None and not _is_step_id(current_owner_step):
            errors.append(f"{context}: current_owner_step must be a canonical S## identifier")
            current_owner_step = None
        parsed_fingerprints = _parse_fingerprints(table, context=context, errors=errors)
        if parsed_fingerprints is not None:
            fingerprints = parsed_fingerprints
    if disposition_kind is DispositionKind.RETIRED_OR_UNREACHABLE and has_current:
        errors.append(f"{context}: retired_or_unreachable cannot carry current source evidence")
    if disposition_kind is not DispositionKind.RETIRED_OR_UNREACHABLE and not has_current:
        errors.append(f"{context}: current source evidence is required for this disposition_kind")

    if (
        historical_error_code is None
        or historical_error_qualname is None
        or historical_source_shard is None
        or historical_old_value_source is None
        or historical_source_line is None
        or historical_source_column is None
        or disposition_kind is None
        or (has_current and (current_error_qualname is None or current_owner_step is None or not fingerprints))
    ):
        return None
    return RehomingRow(
        historical=HistoricalKey(
            source_commit=SOURCE_COMMIT,
            error_code=historical_error_code,
            error_qualname=historical_error_qualname,
            source_shard=historical_source_shard,
            old_value_source=historical_old_value_source,
            historical_owner_step="",
            source_line=historical_source_line,
            source_column=historical_source_column,
        ),
        disposition_kind=disposition_kind,
        current_error_qualname=current_error_qualname,
        current_owner_step=current_owner_step,
        fingerprints=fingerprints,
    )


def _is_non_null_default(record: ErrorCodeDefaultPreimageRecord) -> bool:
    try:
        expression = ast.parse(record.old_value_source, mode="eval").body
    except SyntaxError as error:
        raise RehomingLedgerError(
            (f"cannot parse immutable old value for {record.source_identity!r}: {error.msg}",)
        ) from error
    return not (isinstance(expression, ast.Constant) and expression.value is None)


def _preimage_keys() -> tuple[HistoricalKey, ...]:
    try:
        records = validate_preimage_ledger(load_preimage_ledger())
    except ErrorCodeDefaultPreimageError as error:
        raise RehomingLedgerError((str(error),)) from error
    return tuple(HistoricalKey.from_preimage(record) for record in records if _is_non_null_default(record))


def _reconcile_exact_preimage(rows: tuple[RehomingRow, ...]) -> tuple[RehomingRow, ...]:
    expected = _preimage_keys()
    expected_by_source = {key.source_identity: key for key in expected}
    actual_by_source = {row.historical.source_identity: row for row in rows}
    expected_counter = Counter(key.source_identity for key in expected)
    actual_counter = Counter(row.historical.source_identity for row in rows)
    errors: list[str] = []
    missing = expected_counter - actual_counter
    extra = actual_counter - expected_counter
    if missing:
        errors.append(f"rehoming ledger is missing historical identities: {sorted(missing.elements())!r}")
    if extra:
        errors.append(f"rehoming ledger has extra historical identities: {sorted(extra.elements())!r}")
    for source_identity in sorted(expected_counter.keys() & actual_counter.keys()):
        expected_key = expected_by_source[source_identity]
        actual_row = actual_by_source[source_identity]
        if actual_row.historical.historical_owner_step:
            errors.append(f"rehoming ledger must not declare historical owner: {source_identity!r}")
        actual_historical = HistoricalKey(
            source_commit=actual_row.historical.source_commit,
            error_code=actual_row.historical.error_code,
            error_qualname=actual_row.historical.error_qualname,
            source_shard=actual_row.historical.source_shard,
            old_value_source=actual_row.historical.old_value_source,
            historical_owner_step=expected_key.historical_owner_step,
            source_line=actual_row.historical.source_line,
            source_column=actual_row.historical.source_column,
        )
        if actual_historical != expected_key:
            errors.append(f"rehoming ledger historical identity drift: {source_identity!r}")
        if actual_row.historical.historical_owner_step != "":
            errors.append(f"rehoming ledger historical owner drift: {source_identity!r}")
    duplicate_keys = [identity for identity, count in actual_counter.items() if count > 1]
    if duplicate_keys:
        errors.append(f"rehoming ledger duplicates historical identities: {sorted(duplicate_keys)!r}")
    if errors:
        raise RehomingLedgerError(errors)

    rehomed: list[RehomingRow] = []
    for row in rows:
        canonical = expected_by_source.get(row.historical.source_identity)
        if canonical is None:
            continue
        rehomed.append(
            RehomingRow(
                historical=canonical,
                disposition_kind=row.disposition_kind,
                current_error_qualname=row.current_error_qualname,
                current_owner_step=row.current_owner_step,
                fingerprints=row.fingerprints,
            )
        )
    return tuple(sorted(rehomed, key=lambda row: row.historical.source_identity))


def load_rehoming_ledger(path: Path = DEFAULT_REHOMING_LEDGER_PATH) -> RehomingLedger:
    """Load a strict TOML ledger and join every row to immutable preimage proof."""
    try:
        document = cast(dict[str, object], tomllib.loads(path.read_text(encoding=_UTF_8)))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RehomingLedgerError((f"cannot read rehoming ledger {path}: {error}",)) from error

    errors: list[str] = []
    unknown_top = sorted(set(document) - _TOP_LEVEL_FIELDS)
    if unknown_top:
        errors.append(f"{path}: unrecognized top-level field(s): {', '.join(unknown_top)}")
    raw_meta = document.get("meta")
    meta = cast(dict[str, object], raw_meta) if isinstance(raw_meta, dict) else None
    if meta is None or frozenset(meta) != _META_FIELDS or meta.get("schema_version") != _SCHEMA_VERSION:
        errors.append(f"{path}: meta must contain only schema_version = {_SCHEMA_VERSION}")
    raw_rows = document.get("rehoming")
    if not isinstance(raw_rows, list):
        errors.append(f"{path}: rehoming must be an array of tables")
        raw_rows = []
    rows = [
        row
        for index, value in enumerate(cast(list[object], raw_rows), start=1)
        if (row := _parse_row(value, context=f"{path} [[rehoming]] #{index}", errors=errors)) is not None
    ]
    if errors:
        raise RehomingLedgerError(errors)
    return RehomingLedger(_reconcile_exact_preimage(tuple(rows)))


def main(argv: list[str] | None = None) -> int:
    """Validate a rehoming ledger's typed, source-only representation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_REHOMING_LEDGER_PATH)
    arguments = parser.parse_args(argv)
    try:
        ledger = load_rehoming_ledger(arguments.ledger)
    except RehomingLedgerError as error:
        print(error)
        return 1
    print(f"reconciled {len(ledger.rows)} historical default rehoming rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail-closed, non-runtime rehoming ledger for retired error defaults.

This module owns only the typed representation and strict TOML boundary for
the historical-default rehoming join.  It intentionally contains no recovery
policy, rendered text, command identity, or locale data.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, cast

from .error_code_default_suggestion_preimage_ledger import (
    SOURCE_COMMIT,
    ErrorCodeDefaultPreimageError,
    ErrorCodeDefaultPreimageRecord,
    load_preimage_ledger,
    validate_preimage_ledger,
)

__all__ = [
    "DEFAULT_REHOMING_LEDGER_PATH",
    "DispositionKind",
    "FingerprintOwnership",
    "HistoricalKey",
    "RehomingLedger",
    "RehomingLedgerError",
    "RehomingRow",
    "SourceFingerprint",
    "current_source_fingerprints",
    "load_rehoming_ledger",
    "main",
    "migrate_legacy_ledger",
    "render_rehoming_ledger",
    "validate_rehoming_ledger",
]


REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_REHOMING_LEDGER_PATH: Final[Path] = REPO_ROOT / "dev" / "quality" / "error_code_default_recovery_rehoming.toml"
_PLAN_PATH: Final[Path] = REPO_ROOT / ".vault" / "plan" / "2026-08-09-cli-action-envelope-hardening-plan.md"
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
        "ownerships",
    },
)
_AST_FORMAT: Final[str] = "recovery-ast-v1"
_FINGERPRINT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "path",
        "lexical_owner",
        "role",
        "ast_format",
        "normalized_ast_sha256",
        "identical_site_ordinal",
        "line",
        "column",
        "end_line",
        "end_column",
    }
)
_FINGERPRINT_ROLES: Final[frozenset[str]] = frozenset({"constructor", "reference"})
_OWNERSHIP_FIELDS: Final[frozenset[str]] = _FINGERPRINT_FIELDS | frozenset({"owner_step"})
_LEGACY_ROW_FIELDS: Final[frozenset[str]] = _ROW_FIELDS - frozenset({"ownerships"}) | frozenset(
    {"current_owner_step", "fingerprints"}
)
_MIGRATION_SOURCE_ROW_FIELDS: Final[frozenset[str]] = _LEGACY_ROW_FIELDS | _ROW_FIELDS
_MIGRATION_WRITE_ATTEMPTS: Final[int] = 3


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


#: The final dispositions a row reaches once its producer migration has landed.
#: A row carrying one of these is no longer owned by an open Step.
_VERIFIED_DISPOSITIONS: Final[frozenset[DispositionKind]] = frozenset(
    {
        DispositionKind.VERIFIED_TYPED_ACTION,
        DispositionKind.VERIFIED_TERMINAL_NO_RECOVERY,
        DispositionKind.VERIFIED_NONPRODUCER_REFERENCE,
    },
)


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
    """One structural current-tree observation with non-gating locator metadata."""

    path: str
    lexical_owner: str
    role: Literal["constructor", "reference"]
    ast_format: Literal["recovery-ast-v1"]
    normalized_ast_sha256: str
    identical_site_ordinal: int
    line: int
    column: int
    end_line: int
    end_column: int

    @property
    def structural_group(self) -> tuple[str, str, str, str, str]:
        """Return the traversal-ordinal group for this structural site."""
        return (self.path, self.lexical_owner, self.role, self.ast_format, self.normalized_ast_sha256)

    @property
    def identity(self) -> tuple[str, str, str, str, str, int]:
        """Return the source-structural evidence identity for reconciliation."""
        return (
            self.path,
            self.lexical_owner,
            self.role,
            self.ast_format,
            self.normalized_ast_sha256,
            self.identical_site_ordinal,
        )

    def with_ordinal(self, identical_site_ordinal: int) -> SourceFingerprint:
        """Return the structurally identical fingerprint with its traversal ordinal."""
        return SourceFingerprint(
            self.path,
            self.lexical_owner,
            self.role,
            self.ast_format,
            self.normalized_ast_sha256,
            identical_site_ordinal,
            self.line,
            self.column,
            self.end_line,
            self.end_column,
        )


@dataclass(frozen=True, slots=True)
class FingerprintOwnership:
    """One source fingerprint and its exclusive current migration owner."""

    fingerprint: SourceFingerprint
    owner_step: str

    @property
    def identity(self) -> tuple[str, str, str, str, str, int, str]:
        """Return the exact fingerprint-owner evidence identity."""
        return (*self.fingerprint.identity, self.owner_step)


@dataclass(frozen=True, slots=True)
class RehomingRow:
    """One evidence-only join from a retired declaration to current source."""

    historical: HistoricalKey
    disposition_kind: DispositionKind
    current_error_qualname: str | None
    ownerships: tuple[FingerprintOwnership, ...]


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
    lexical_owner = _nonempty_string(table, "lexical_owner", context=context, errors=errors)
    raw_role = _nonempty_string(table, "role", context=context, errors=errors)
    ast_format = _nonempty_string(table, "ast_format", context=context, errors=errors)
    normalized_ast_sha256 = _nonempty_string(table, "normalized_ast_sha256", context=context, errors=errors)
    identical_site_ordinal = _positive_integer(
        table, "identical_site_ordinal", minimum=1, context=context, errors=errors
    )
    line = _positive_integer(table, "line", minimum=1, context=context, errors=errors)
    column = _positive_integer(table, "column", minimum=0, context=context, errors=errors)
    end_line = _positive_integer(table, "end_line", minimum=1, context=context, errors=errors)
    end_column = _positive_integer(table, "end_column", minimum=0, context=context, errors=errors)
    if raw_role not in _FINGERPRINT_ROLES:
        errors.append(f"{context}: role must be constructor or reference")
        return None
    if ast_format != _AST_FORMAT:
        errors.append(f"{context}: ast_format must be {_AST_FORMAT}")
        return None
    if normalized_ast_sha256 is None or (
        len(normalized_ast_sha256) != 64
        or any(character not in "0123456789abcdef" for character in normalized_ast_sha256)
    ):
        errors.append(f"{context}: normalized_ast_sha256 must be lowercase sha256")
        return None
    if (
        line is not None
        and column is not None
        and end_line is not None
        and end_column is not None
        and (end_line < line or (end_line == line and end_column < column))
    ):
        errors.append(f"{context}: locator end precedes locator start")
        return None
    if (
        path is None
        or lexical_owner is None
        or identical_site_ordinal is None
        or line is None
        or column is None
        or end_line is None
        or end_column is None
    ):
        return None
    return SourceFingerprint(
        path,
        lexical_owner,
        cast(Literal["constructor", "reference"], raw_role),
        ast_format,
        normalized_ast_sha256,
        identical_site_ordinal,
        line,
        column,
        end_line,
        end_column,
    )


def _parse_ownership(value: object, *, context: str, errors: list[str]) -> FingerprintOwnership | None:
    if not isinstance(value, dict):
        errors.append(f"{context}: must be an inline table")
        return None
    table = cast(dict[str, object], value)
    unknown = sorted(set(table) - _OWNERSHIP_FIELDS)
    missing = sorted(_OWNERSHIP_FIELDS - set(table))
    if unknown:
        errors.append(f"{context}: unrecognized field(s): {', '.join(unknown)}")
    if missing:
        errors.append(f"{context}: missing field(s): {', '.join(missing)}")
    fingerprint = _parse_fingerprint(
        {field: table[field] for field in _FINGERPRINT_FIELDS if field in table}, context=context, errors=errors
    )
    owner_step = _nonempty_string(table, "owner_step", context=context, errors=errors)
    if owner_step is not None and not _is_step_id(owner_step):
        errors.append(f"{context}: owner_step must be a canonical S## identifier")
        owner_step = None
    if fingerprint is None or owner_step is None:
        return None
    return FingerprintOwnership(fingerprint, owner_step)


def _parse_ownerships(
    table: dict[str, object], *, context: str, errors: list[str]
) -> tuple[FingerprintOwnership, ...] | None:
    value = table.get("ownerships")
    if not isinstance(value, list) or not value:
        errors.append(f"{context}: ownerships must be a non-empty array")
        return None
    values = cast(list[object], value)
    records = [
        record
        for index, item in enumerate(values, start=1)
        if (record := _parse_ownership(item, context=f"{context}.ownerships[{index}]", errors=errors)) is not None
    ]
    if len(records) != len(values):
        return None
    if len({record.identity for record in records}) != len(records):
        errors.append(f"{context}: ownerships must not contain duplicates")
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

    current_fields = {"current_error_qualname", "ownerships"}
    present_current = current_fields & set(table)
    has_current = bool(present_current)
    if has_current and present_current != current_fields:
        errors.append(f"{context}: current source evidence must carry all current fields")
    current_error_qualname: str | None = None
    ownerships: tuple[FingerprintOwnership, ...] = ()
    if has_current:
        current_error_qualname = _nonempty_string(table, "current_error_qualname", context=context, errors=errors)
        parsed_ownerships = _parse_ownerships(table, context=context, errors=errors)
        if parsed_ownerships is not None:
            ownerships = parsed_ownerships
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
        or (has_current and (current_error_qualname is None or not ownerships))
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
        ownerships=ownerships,
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
        if actual_row.historical.historical_owner_step not in ("", expected_key.historical_owner_step):
            errors.append(f"rehoming ledger historical owner drift: {source_identity!r}")
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
                ownerships=row.ownerships,
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


def _load_legacy_rehoming_ledger(path: Path) -> RehomingLedger:
    """Load only the immutable identity and disposition from a legacy ledger."""
    try:
        document = cast(dict[str, object], tomllib.loads(path.read_text(encoding=_UTF_8)))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RehomingLedgerError((f"E_REHOMING_LEGACY_READ:{path}:{type(error).__name__}",)) from error

    errors: list[str] = []
    unknown_top = sorted(set(document) - _TOP_LEVEL_FIELDS)
    if unknown_top:
        errors.append(f"E_REHOMING_LEGACY_TOP_LEVEL:{','.join(unknown_top)}")
    raw_meta = document.get("meta")
    meta = cast(dict[str, object], raw_meta) if isinstance(raw_meta, dict) else None
    if meta is None or frozenset(meta) != _META_FIELDS or meta.get("schema_version") != _SCHEMA_VERSION:
        errors.append("E_REHOMING_LEGACY_META")
    raw_rows = document.get("rehoming")
    if not isinstance(raw_rows, list):
        errors.append("E_REHOMING_LEGACY_ROWS")
        raw_rows = []

    rows: list[RehomingRow] = []
    for index, value in enumerate(cast(list[object], raw_rows), start=1):
        context = f"E_REHOMING_LEGACY_ROW:{index}"
        if not isinstance(value, dict):
            errors.append(context)
            continue
        table = cast(dict[str, object], value)
        unknown = sorted(set(table) - _MIGRATION_SOURCE_ROW_FIELDS)
        if unknown:
            errors.append(f"{context}:UNKNOWN:{','.join(unknown)}")
        historical_error_code = _nonempty_string(table, "historical_error_code", context=context, errors=errors)
        historical_error_qualname = _nonempty_string(table, "historical_error_qualname", context=context, errors=errors)
        historical_source_shard = _nonempty_string(table, "historical_source_shard", context=context, errors=errors)
        historical_old_value_source = _nonempty_string(
            table, "historical_old_value_source", context=context, errors=errors
        )
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
            errors.append(f"{context}:DISPOSITION")
            disposition_kind = None
        if (
            historical_error_code is None
            or historical_error_qualname is None
            or historical_source_shard is None
            or historical_old_value_source is None
            or historical_source_line is None
            or historical_source_column is None
            or disposition_kind is None
        ):
            continue
        rows.append(
            RehomingRow(
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
                current_error_qualname=None,
                ownerships=(),
            )
        )
    if errors:
        raise RehomingLedgerError(errors)
    return RehomingLedger(_reconcile_exact_preimage(tuple(rows)))


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_rehoming_ledger(ledger: RehomingLedger) -> str:
    """Render a deterministic strict-current-schema rehoming ledger."""
    reconciled = RehomingLedger(_reconcile_exact_preimage(ledger.rows))
    lines = ["[meta]", f"schema_version = {_SCHEMA_VERSION}"]
    for row in reconciled.rows:
        historical = row.historical
        lines.extend(
            (
                "",
                "[[rehoming]]",
                f"historical_error_code = {_toml_string(historical.error_code)}",
                f"historical_error_qualname = {_toml_string(historical.error_qualname)}",
                f"historical_source_shard = {_toml_string(historical.source_shard)}",
                f"historical_old_value_source = {_toml_string(historical.old_value_source)}",
                f"historical_source_line = {historical.source_line}",
                f"historical_source_column = {historical.source_column}",
                f"disposition_kind = {_toml_string(row.disposition_kind.value)}",
            )
        )
        if row.current_error_qualname is not None:
            lines.extend(
                (
                    f"current_error_qualname = {_toml_string(row.current_error_qualname)}",
                    "ownerships = [",
                )
            )
            for ownership in sorted(row.ownerships, key=lambda item: item.identity):
                fingerprint = ownership.fingerprint
                lines.append(
                    "  { "
                    f"path = {_toml_string(fingerprint.path)}, "
                    f"lexical_owner = {_toml_string(fingerprint.lexical_owner)}, "
                    f"role = {_toml_string(fingerprint.role)}, "
                    f"ast_format = {_toml_string(fingerprint.ast_format)}, "
                    f"normalized_ast_sha256 = {_toml_string(fingerprint.normalized_ast_sha256)}, "
                    f"identical_site_ordinal = {fingerprint.identical_site_ordinal}, "
                    f"line = {fingerprint.line}, "
                    f"column = {fingerprint.column}, "
                    f"end_line = {fingerprint.end_line}, "
                    f"end_column = {fingerprint.end_column}, "
                    f"owner_step = {_toml_string(ownership.owner_step)} "
                    "},"
                )
            lines.append("]")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _PlanStep:
    step_id: str
    checked: bool
    scope: tuple[str, ...]


def _current_plan_steps(plan_path: Path = _PLAN_PATH) -> tuple[_PlanStep, ...]:
    completed = subprocess.run(  # noqa: S603
        ["uv", "run", "--no-sync", "vaultspec-core", "vault", "plan", "query", str(plan_path), "--json"],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
    )
    if completed.returncode != 0:
        raise _recovery_error("E_REHOMING_PLAN_QUERY", completed.returncode, completed.stderr.strip())
    try:
        document = cast(dict[str, object], json.loads(completed.stdout))
        data = cast(dict[str, object], document["data"])
        raw_steps = cast(list[object], data["steps"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise _recovery_error("E_REHOMING_PLAN_RESPONSE", type(error).__name__) from error
    steps: list[_PlanStep] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise _recovery_error("E_REHOMING_PLAN_ROW")
        step = cast(dict[str, object], raw_step)
        display_path = step.get("display_path")
        checked = step.get("checked")
        scope = step.get("scope")
        if not isinstance(display_path, str) or not isinstance(checked, bool) or not isinstance(scope, str):
            raise _recovery_error("E_REHOMING_PLAN_FIELDS")
        step_id = display_path.rpartition(".")[2]
        if not _is_step_id(step_id):
            raise _recovery_error("E_REHOMING_PLAN_STEP", display_path)
        scope_parts = tuple(item.strip() for item in scope.split(";") if item.strip())
        if not scope_parts:
            raise _recovery_error("E_REHOMING_PLAN_SCOPE", step_id)
        steps.append(_PlanStep(step_id, checked, scope_parts))
    return tuple(steps)


def _scope_covers(path: str, scope: tuple[str, ...]) -> bool:
    return any(path == item or path.startswith(f"{item.rstrip('/')}/") for item in scope)


def _validate_fingerprint_owners(
    row: RehomingRow,
    steps: tuple[_PlanStep, ...],
    steps_by_id: dict[str, list[_PlanStep]],
    errors: list[str],
    *,
    require_open_owner: bool,
) -> None:
    """Bind every fingerprint to exactly one scope-valid owner Step.

    A row still awaiting migration needs an *open* owner, and the uniqueness it
    is checked against is uniqueness among open Steps: two open Steps covering
    one path is an unresolved ownership dispute. A row whose migration has
    landed is the opposite case -- its owner is expected to be closed, and the
    covering set is drawn from every Step, because a closed owner has left the
    open population by construction.
    """
    for ownership in row.ownerships:
        fingerprint = ownership.fingerprint
        owner_id = ownership.owner_step
        owners = steps_by_id.get(owner_id, [])
        if not owners:
            errors.append(f"E_REHOMING_OWNER_UNKNOWN:{row.historical.error_qualname}:{owner_id}")
            continue
        if len(owners) != 1:
            errors.append(f"E_REHOMING_OWNER_MULTIPLE:{row.historical.error_qualname}:{owner_id}:{len(owners)}")
            continue
        owner = owners[0]
        if require_open_owner and owner.checked:
            errors.append(f"E_REHOMING_OWNER_CLOSED:{row.historical.error_qualname}:{owner_id}")
            continue
        path = fingerprint.path
        covering = [
            step for step in steps if (not step.checked or not require_open_owner) and _scope_covers(path, step.scope)
        ]
        if not any(step.step_id == owner_id for step in covering):
            errors.append(f"E_REHOMING_OWNER_SCOPE:{row.historical.error_qualname}:{owner_id}:{path}")
        if require_open_owner and len(covering) != 1:
            errors.append(
                f"E_REHOMING_OWNER_OVERLAP:{row.historical.error_qualname}:{path}:"
                f"{','.join(sorted(step.step_id for step in covering))}"
            )


def validate_rehoming_ledger(
    ledger: RehomingLedger,
    *,
    root: Path = REPO_ROOT,
    plan_path: Path = _PLAN_PATH,
) -> RehomingLedger:
    """Require exact current evidence and a scope-valid owner for each row's disposition.

    Whether a row still awaits migration is read from the current source, not
    from the row's own bookkeeping: a constructor that still passes a
    positional argument keeps an authored sentence alive, and such a row needs
    exactly one open scope-valid owner. Once no constructor authors a message
    the migration has landed by evidence, and the owner Step is expected to be
    closed -- demanding an open owner there would make closing any Step red the
    gate, so the campaign could never converge. A row may only *claim* a
    verified disposition when the evidence agrees with the claim.
    """
    reconciled = RehomingLedger(_reconcile_exact_preimage(ledger.rows))
    current, authored = _scan_current_source(root)
    steps = _current_plan_steps(plan_path)
    steps_by_id: dict[str, list[_PlanStep]] = defaultdict(list)
    for step in steps:
        steps_by_id[step.step_id].append(step)
    errors: list[str] = []
    joined: dict[str, list[RehomingRow]] = defaultdict(list)
    for row in reconciled.rows:
        qualname = row.historical.error_qualname
        expected = current.get(qualname, ())
        if expected:
            joined[qualname].append(row)
            if row.current_error_qualname != qualname:
                errors.append(f"E_REHOMING_CURRENT_QUALNAME:{qualname}:{row.current_error_qualname}")
            ownership_fingerprints = tuple(ownership.fingerprint for ownership in row.ownerships)
            if Counter(fingerprint.identity for fingerprint in ownership_fingerprints) != Counter(
                fingerprint.identity for fingerprint in expected
            ):
                errors.append(f"E_REHOMING_FINGERPRINT_MULTISET:{qualname}")
            if len({ownership.fingerprint.identity for ownership in row.ownerships}) != len(row.ownerships):
                errors.append(f"E_REHOMING_FINGERPRINT_DUPLICATE:{qualname}")
            authored_groups = authored.get(qualname, frozenset())
            authors_message = any(fingerprint.structural_group in authored_groups for fingerprint in expected)
            has_constructor = any(fingerprint.role == "constructor" for fingerprint in expected)
            if row.disposition_kind is DispositionKind.RETIRED_OR_UNREACHABLE:
                errors.append(f"E_REHOMING_CURRENT_DISPOSITION:{qualname}:{row.disposition_kind.value}")
            if row.disposition_kind in _VERIFIED_DISPOSITIONS and authors_message:
                errors.append(f"E_REHOMING_VERIFIED_AUTHORS_MESSAGE:{qualname}")
            if row.disposition_kind is DispositionKind.VERIFIED_NONPRODUCER_REFERENCE and has_constructor:
                errors.append(f"E_REHOMING_REFERENCE_HAS_CONSTRUCTOR:{qualname}")
            _validate_fingerprint_owners(row, steps, steps_by_id, errors, require_open_owner=authors_message)
        elif (
            row.disposition_kind is not DispositionKind.RETIRED_OR_UNREACHABLE
            or row.current_error_qualname is not None
            or row.ownerships
        ):
            errors.append(f"E_REHOMING_ZERO_DISPOSITION:{qualname}")
    for qualname, rows in sorted(joined.items()):
        if len(rows) != 1:
            errors.append(f"E_REHOMING_ROW_OVERLAP:{qualname}:{len(rows)}")
    for qualname in sorted(current):
        if qualname not in joined:
            errors.append(f"E_REHOMING_CURRENT_UNJOINED:{qualname}")
    if errors:
        raise RehomingLedgerError(errors)
    return reconciled


def _generate_rehoming_ledger(
    legacy: RehomingLedger,
    current: dict[str, tuple[SourceFingerprint, ...]],
    steps: tuple[_PlanStep, ...],
    authored: dict[str, frozenset[tuple[str, str, str, str, str]]] | None = None,
) -> RehomingLedger:
    errors: list[str] = []
    generated: list[RehomingRow] = []
    authored_by_qualname = authored or {}
    for row in legacy.rows:
        qualname = row.historical.error_qualname
        fingerprints = current.get(qualname, ())
        # Mirror the validator: a row whose sites no longer author a message has
        # landed, so its owner is expected to have closed. Drawing its covering
        # set from open Steps only would leave it ownerless and unrenderable.
        authored_groups = authored_by_qualname.get(qualname, frozenset())
        authors_message = any(fingerprint.structural_group in authored_groups for fingerprint in fingerprints)
        # A landed row keeps the owner already recorded against its path. That
        # owner is immutable provenance -- it is the Step that did the work --
        # and re-deriving it from the current open population would either find
        # nothing (the owner has closed) or find several closed Steps whose
        # scopes overlap, neither of which is a correction.
        recorded_owner_by_path = {ownership.fingerprint.path: ownership.owner_step for ownership in row.ownerships}
        ownerships: list[FingerprintOwnership] = []
        for fingerprint in fingerprints:
            if not authors_message:
                recorded = recorded_owner_by_path.get(fingerprint.path)
                if recorded is not None:
                    ownerships.append(FingerprintOwnership(fingerprint, recorded))
                    continue
            covering = [step for step in steps if not step.checked and _scope_covers(fingerprint.path, step.scope)]
            if not covering:
                errors.append(f"E_REHOMING_GENERATE_OWNER_ZERO:{qualname}:{fingerprint.path}")
                continue
            if len(covering) != 1:
                errors.append(
                    f"E_REHOMING_GENERATE_OWNER_OVERLAP:{qualname}:{fingerprint.path}:"
                    f"{','.join(sorted(step.step_id for step in covering))}"
                )
                continue
            ownerships.append(FingerprintOwnership(fingerprint, covering[0].step_id))
        generated.append(
            RehomingRow(
                historical=row.historical,
                disposition_kind=row.disposition_kind,
                current_error_qualname=qualname if fingerprints else None,
                ownerships=tuple(sorted(ownerships, key=lambda ownership: ownership.identity)),
            )
        )
    if errors:
        raise RehomingLedgerError(errors)
    return RehomingLedger(tuple(generated))


def migrate_legacy_ledger(
    legacy_path: Path,
    *,
    root: Path = REPO_ROOT,
    plan_path: Path = _PLAN_PATH,
) -> RehomingLedger:
    """Derive strict-current ownership evidence from immutable legacy rows."""
    legacy = _load_legacy_rehoming_ledger(legacy_path)
    fingerprints, authored = _scan_current_source(root)
    generated = _generate_rehoming_ledger(legacy, fingerprints, _current_plan_steps(plan_path), authored)
    return validate_rehoming_ledger(generated, root=root, plan_path=plan_path)


def _check_rendered_migration(
    output_path: Path,
    rendered: str,
    *,
    root: Path,
    plan_path: Path,
) -> RehomingLedger:
    try:
        output = output_path.read_text(encoding=_UTF_8)
    except OSError as error:
        raise _recovery_error("E_REHOMING_MIGRATION_CHECK_READ", type(error).__name__) from error
    if output != rendered:
        raise _recovery_error("E_REHOMING_MIGRATION_CHECK_CONTENT")
    return validate_rehoming_ledger(load_rehoming_ledger(output_path), root=root, plan_path=plan_path)


def _write_migrated_ledger(
    legacy_path: Path,
    output_path: Path,
    *,
    root: Path,
    plan_path: Path,
) -> RehomingLedger:
    legacy = _load_legacy_rehoming_ledger(legacy_path)
    last_drift: RehomingLedgerError | None = None
    for _ in range(_MIGRATION_WRITE_ATTEMPTS):
        fingerprints, authored = _scan_current_source(root)
        generated = _generate_rehoming_ledger(
            legacy,
            fingerprints,
            _current_plan_steps(plan_path),
            authored,
        )
        try:
            output_path.write_text(render_rehoming_ledger(generated), encoding=_UTF_8)
        except OSError as error:
            raise _recovery_error("E_REHOMING_MIGRATION_WRITE", type(error).__name__) from error
        structural = load_rehoming_ledger(output_path)
        try:
            return validate_rehoming_ledger(structural, root=root, plan_path=plan_path)
        except RehomingLedgerError as error:
            if not error.errors or not all(
                item.startswith("E_REHOMING_FINGERPRINT_MULTISET:") for item in error.errors
            ):
                raise
            last_drift = error
    if last_drift is not None:
        raise last_drift
    raise _recovery_error("E_REHOMING_MIGRATION_CONVERGENCE")


@dataclass(frozen=True, slots=True)
class _ProductionModule:
    path: Path
    relative_path: str
    module: str
    is_package: bool
    future_annotations: bool
    tree: ast.Module


@dataclass(frozen=True, slots=True)
class _Resolution:
    error_qualnames: frozenset[str] = frozenset()
    modules: frozenset[str] = frozenset()
    known: bool = False

    def merged(self, other: _Resolution) -> _Resolution:
        return _Resolution(
            self.error_qualnames | other.error_qualnames,
            self.modules | other.modules,
            self.known or other.known,
        )


_EMPTY_RESOLUTION: Final[_Resolution] = _Resolution()


def _recovery_error(code: str, *values: object) -> RehomingLedgerError:
    suffix = ":".join(str(value) for value in values)
    return RehomingLedgerError((code if not suffix else f"{code}:{suffix}",))


def _module_name(source_path: Path, *, root: Path) -> tuple[str, bool]:
    relative = source_path.relative_to(root / "src").with_suffix("")
    is_package = relative.name == "__init__"
    parts = relative.parts[:-1] if is_package else relative.parts
    return ".".join(parts), is_package


def _production_modules(root: Path) -> tuple[_ProductionModule, ...]:
    source_root = root / "src" / "cadrumo"
    if not source_root.is_dir():
        raise _recovery_error("E_REHOMING_SOURCE_ROOT", source_root)
    modules: list[_ProductionModule] = []
    for path in sorted(source_root.rglob("*.py")):
        relative_parts = path.relative_to(root).parts
        if "tests" in relative_parts:
            continue
        relative_path = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding=_UTF_8)
        except OSError as error:
            raise _recovery_error("E_REHOMING_SOURCE_READ", relative_path, type(error).__name__) from error
        except UnicodeDecodeError as error:
            raise _recovery_error("E_REHOMING_SOURCE_DECODE", relative_path, type(error).__name__) from error
        try:
            tree = ast.parse(source, filename=relative_path)
        except SyntaxError as error:
            raise _recovery_error("E_REHOMING_SOURCE_PARSE", relative_path, error.lineno, error.offset) from error
        module, is_package = _module_name(path, root=root)
        future_annotations = any(
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
            and any(alias.name == "annotations" for alias in statement.names)
            for statement in tree.body
        )
        modules.append(_ProductionModule(path, relative_path, module, is_package, future_annotations, tree))
    if not modules:
        raise _recovery_error("E_REHOMING_SOURCE_EMPTY", source_root)
    return tuple(modules)


def _target_qualnames() -> frozenset[str]:
    return frozenset(key.error_qualname for key in _preimage_keys())


def _current_definitions(
    modules: tuple[_ProductionModule, ...], targets: frozenset[str]
) -> dict[str, _ProductionModule]:
    definitions: dict[str, list[_ProductionModule]] = defaultdict(list)
    for module in modules:
        for statement in module.tree.body:
            if isinstance(statement, ast.ClassDef):
                qualname = f"{module.module}.{statement.name}"
                if qualname in targets:
                    definitions[qualname].append(module)
    duplicates = sorted(qualname for qualname, found in definitions.items() if len(found) != 1)
    if duplicates:
        raise RehomingLedgerError(
            tuple(f"E_REHOMING_TARGET_DEFINITION_AMBIGUOUS:{value}" for value in duplicates),
        )
    return {qualname: found[0] for qualname, found in definitions.items()}


def _package_for(module: _ProductionModule) -> str:
    return module.module if module.is_package else module.module.rpartition(".")[0]


def _absolute_module(module: _ProductionModule, level: int, source: str | None) -> str:
    package = _package_for(module).split(".") if _package_for(module) else []
    if level:
        package = package[: len(package) - level + 1]
    if source:
        package.extend(source.split("."))
    return ".".join(part for part in package if part)


def _static_bind(target: ast.expr, value: object, bindings: dict[str, object]) -> bool:
    if isinstance(target, ast.Name):
        bindings[target.id] = value
        return True
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)):
        sequence = cast(tuple[object, ...] | list[object], value)
        if len(target.elts) != len(sequence):
            return False
        return all(
            _static_bind(item, item_value, bindings) for item, item_value in zip(target.elts, sequence, strict=True)
        )
    return False


def _static_value(node: ast.AST, bindings: dict[str, object]) -> object | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
        return node.value
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values: list[object | None] = [_static_value(item, bindings) for item in node.elts]
        if any(item is None for item in values):
            return None
        if isinstance(node, ast.Tuple):
            return tuple(values)
        if isinstance(node, ast.List):
            return values
        return frozenset(values)
    if isinstance(node, ast.Dict):
        mapping: dict[object, object] = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                return None
            static_key = _static_value(key, bindings)
            static_value = _static_value(value, bindings)
            if static_key is None or static_value is None:
                return None
            mapping[static_key] = static_value
        return mapping
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 and not node.keywords:
        value = _static_value(node.args[0], bindings)
        if value is None or node.func.id not in {"tuple", "list", "set", "frozenset"}:
            return None
        if not isinstance(value, (tuple, list, frozenset)):
            return None
        collection = cast(tuple[object, ...] | list[object] | frozenset[object], value)
        if node.func.id == "tuple":
            return tuple(collection)
        if node.func.id == "list":
            return list(collection)
        if node.func.id == "set":
            return frozenset(collection)
        return frozenset(collection)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_value(node.left, bindings)
        right = _static_value(node.right, bindings)
        if isinstance(left, tuple) and isinstance(right, tuple):
            return cast(tuple[object, ...], left) + cast(tuple[object, ...], right)
        if isinstance(left, list) and isinstance(right, list):
            return cast(list[object], left) + cast(list[object], right)
        return None
    if isinstance(node, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        comprehension_mapping: dict[object, object] = {}
        comprehension_values: list[object] = []

        def visit_generator(index: int, local: dict[str, object]) -> bool:
            if index == len(node.generators):
                if isinstance(node, ast.DictComp):
                    key = _static_value(node.key, local)
                    value = _static_value(node.value, local)
                    if key is None or value is None:
                        return False
                    comprehension_mapping[key] = value
                else:
                    value = _static_value(node.elt, local)
                    if value is None:
                        return False
                    comprehension_values.append(value)
                return True
            generator = node.generators[index]
            if generator.is_async or generator.ifs:
                return False
            iterable = _static_value(generator.iter, local)
            if not isinstance(iterable, (tuple, list, frozenset)):
                return False
            collection = cast(tuple[object, ...] | list[object] | frozenset[object], iterable)
            for item in collection:
                next_local = dict(local)
                if not _static_bind(generator.target, item, next_local) or not visit_generator(index + 1, next_local):
                    return False
            return True

        if not visit_generator(0, dict(bindings)):
            return None
        if isinstance(node, ast.DictComp):
            return comprehension_mapping
        if isinstance(node, ast.ListComp):
            return comprehension_values
        if isinstance(node, ast.SetComp):
            return frozenset(comprehension_values)
        return tuple(comprehension_values)
    return None


def _static_module_bindings(module: _ProductionModule) -> dict[str, object]:
    bindings: dict[str, object] = {}
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            value = _static_value(statement.value, bindings)
            if (value is None or not _static_bind(statement.targets[0], value, bindings)) and isinstance(
                statement.targets[0], ast.Name
            ):
                bindings.pop(statement.targets[0].id, None)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            value = _static_value(statement.value, bindings)
            if (value is None or not _static_bind(statement.target, value, bindings)) and isinstance(
                statement.target, ast.Name
            ):
                bindings.pop(statement.target.id, None)
        elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
            bindings.pop(statement.target.id, None)
    return bindings


def _lazy_mapping_lookup(node: ast.AST, *, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_LAZY_EXPORTS"
        and node.func.attr == "get"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == name
        and not node.keywords
    )


def _module_import_module_bindings(module: _ProductionModule) -> dict[str, Literal["module", "function"]]:
    bindings: dict[str, Literal["module", "function"]] = {}
    proven_imports: dict[int, dict[str, Literal["module", "function"]]] = {}
    tainted: set[str] = set()
    for statement in module.tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                name = alias.asname or alias.name.split(".")[0]
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    if name in bindings:
                        tainted.add(name)
                    else:
                        bindings[name] = "module"
                        proven_imports.setdefault(id(statement), {})[name] = "module"
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                if statement.level == 0 and statement.module == "importlib" and alias.name == "import_module":
                    if name in bindings:
                        tainted.add(name)
                    else:
                        bindings[name] = "function"
                        proven_imports.setdefault(id(statement), {})[name] = "function"

    def taint_targets(targets: Iterable[ast.AST]) -> None:
        for target in targets:
            tainted.update(_assignment_target_names(target) & bindings.keys())

    def expression_taints(node: ast.AST) -> None:
        if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.NamedExpr):
            taint_targets((node.target,))
        for child in ast.iter_child_nodes(node):
            expression_taints(child)

    def inspect_statement(statement: ast.stmt) -> None:
        if isinstance(statement, ast.Import):
            proven = proven_imports.get(id(statement), {})
            for alias in statement.names:
                name = alias.asname or alias.name.split(".")[0]
                if name in bindings and name not in proven:
                    tainted.add(name)
            return
        if isinstance(statement, ast.ImportFrom):
            proven = proven_imports.get(id(statement), {})
            for alias in statement.names:
                if alias.name != "*" and (name := alias.asname or alias.name) in bindings and name not in proven:
                    tainted.add(name)
            return
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if statement.name in bindings:
                tainted.add(statement.name)
            return
        if isinstance(statement, ast.Assign):
            taint_targets(statement.targets)
            expression_taints(statement.value)
            return
        if isinstance(statement, ast.AnnAssign):
            taint_targets((statement.target,))
            expression_taints(statement.annotation)
            if statement.value is not None:
                expression_taints(statement.value)
            return
        if isinstance(statement, ast.AugAssign):
            taint_targets((statement.target,))
            expression_taints(statement.value)
            return
        if isinstance(statement, ast.Delete):
            taint_targets(statement.targets)
            return
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            taint_targets((statement.target,))
            expression_taints(statement.iter)
            for nested in (*statement.body, *statement.orelse):
                inspect_statement(nested)
            return
        if isinstance(statement, ast.While):
            expression_taints(statement.test)
            for nested in (*statement.body, *statement.orelse):
                inspect_statement(nested)
            return
        if isinstance(statement, ast.If):
            expression_taints(statement.test)
            for nested in (*statement.body, *statement.orelse):
                inspect_statement(nested)
            return
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                expression_taints(item.context_expr)
                if item.optional_vars is not None:
                    taint_targets((item.optional_vars,))
            for nested in statement.body:
                inspect_statement(nested)
            return
        if isinstance(statement, (ast.Try, ast.TryStar)):
            for nested in (*statement.body, *statement.orelse, *statement.finalbody):
                inspect_statement(nested)
            for handler in statement.handlers:
                if handler.type is not None:
                    expression_taints(handler.type)
                if handler.name in bindings:
                    tainted.add(handler.name)
                for nested in handler.body:
                    inspect_statement(nested)
            return
        if isinstance(statement, ast.Match):
            expression_taints(statement.subject)
            for case in statement.cases:
                tainted.update(_pattern_binders(case.pattern) & bindings.keys())
                if case.guard is not None:
                    expression_taints(case.guard)
                for nested in case.body:
                    inspect_statement(nested)
            return
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                expression_taints(child)

    for statement in module.tree.body:
        inspect_statement(statement)
    return {name: kind for name, kind in bindings.items() if name not in tainted}


def _route_local_import_module_callable(
    route: ast.FunctionDef | ast.AsyncFunctionDef,
    callee: ast.AST,
    *,
    name: str,
    expected: Literal["module", "function"],
) -> bool:
    """Prove a sole, sequential local import for a verified lazy route."""
    if expected == "function":
        if not isinstance(callee, ast.Name) or callee.id != name:
            return False
    elif not (
        isinstance(callee, ast.Attribute)
        and isinstance(callee.value, ast.Name)
        and callee.value.id == name
        and callee.attr == "import_module"
    ):
        return False

    route_bindings, global_names, nonlocal_names = _scope_binders(route.body)
    parameters = {argument.arg for argument in (*route.args.posonlyargs, *route.args.args, *route.args.kwonlyargs)}
    if route.args.vararg is not None:
        parameters.add(route.args.vararg.arg)
    if route.args.kwarg is not None:
        parameters.add(route.args.kwarg.arg)
    if name not in route_bindings or name in parameters or name in global_names or name in nonlocal_names:
        return False

    bindings: list[ast.AST] = []

    def collect(node: ast.AST) -> None:
        if node is not route and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                bindings.append(node)
            return
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, ast.Import):
            if any((alias.asname or alias.name.split(".", 1)[0]) == name for alias in node.names):
                bindings.append(node)
            return
        if isinstance(node, ast.ImportFrom):
            if any((alias.asname or alias.name) == name for alias in node.names):
                bindings.append(node)
            return
        if isinstance(node, ast.Assign):
            if any(name in _assignment_target_names(target) for target in node.targets):
                bindings.append(node)
        elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
            if name in _assignment_target_names(node.target):
                bindings.append(node)
        elif isinstance(node, ast.Delete):
            if any(name in _assignment_target_names(target) for target in node.targets):
                bindings.append(node)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            if name in _assignment_target_names(node.target):
                bindings.append(node)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            if any(
                item.optional_vars is not None and name in _assignment_target_names(item.optional_vars)
                for item in node.items
            ):
                bindings.append(node)
        elif isinstance(node, ast.ExceptHandler):
            if node.name == name:
                bindings.append(node)
        elif isinstance(node, ast.Match):
            matches_name = any(name in _pattern_binders(case.pattern) for case in node.cases)
            if matches_name:
                bindings.append(node)
        for child in ast.iter_child_nodes(node):
            collect(child)

    collect(route)
    if len(bindings) != 1:
        return False
    binding = bindings[0]
    binding_line = getattr(binding, "lineno", None)
    callee_line = getattr(callee, "lineno", None)
    if not isinstance(binding_line, int) or not isinstance(callee_line, int) or binding_line >= callee_line:
        return False
    if expected == "function":
        return (
            isinstance(binding, ast.ImportFrom)
            and binding.level == 0
            and binding.module == "importlib"
            and len(binding.names) == 1
            and binding.names[0].name == "import_module"
            and (binding.names[0].asname or binding.names[0].name) == name
        )
    return (
        isinstance(binding, ast.Import)
        and len(binding.names) == 1
        and binding.names[0].name == "importlib"
        and (binding.names[0].asname or binding.names[0].name.split(".", 1)[0]) == name
    )


def _module_import_module_callable(module: _ProductionModule, node: ast.AST) -> bool:
    name: str
    expected: Literal["module", "function"]
    if isinstance(node, ast.Name):
        name = node.id
        expected = "function"
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.attr == "import_module":
        name = node.value.id
        expected = "module"
    else:
        return False
    for statement in module.tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) or statement.name != "__getattr__":
            continue
        if not any(child is node for child in ast.walk(statement)):
            continue
        route_bindings, global_names, nonlocal_names = _scope_binders(statement.body)
        parameters = (*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs)
        parameter_names = {parameter.arg for parameter in parameters}
        if name in parameter_names or name in global_names or name in nonlocal_names:
            return False
        if name in route_bindings:
            return _route_local_import_module_callable(statement, node, name=name, expected=expected)
    return _module_import_module_bindings(module).get(name) == expected


def _import_module_call(node: ast.AST, *, mapping_name: str, module: _ProductionModule) -> bool:
    if not isinstance(node, ast.Call) or len(node.args) != 2 or node.keywords:
        return False
    if not isinstance(node.args[0], ast.Name) or node.args[0].id != mapping_name:
        return False
    if not isinstance(node.args[1], ast.Name) or node.args[1].id != "__name__":
        return False
    return _module_import_module_callable(module, node.func)


def _static_import_module_accessors(
    module: _ProductionModule,
    exports: dict[str, dict[str, _Resolution]],
    module_names: frozenset[str],
) -> dict[str, tuple[ast.Call, _Resolution]]:
    """Return module-local, zero-argument lazy accessors with a closed body."""
    accessors: dict[str, tuple[ast.Call, _Resolution]] = {}
    ambiguous: set[str] = set()
    module_bindings = _module_import_module_bindings(module)
    for function in module.tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) or function.decorator_list:
            continue
        if function.name in ambiguous:
            continue
        if (
            function.args.posonlyargs
            or function.args.args
            or function.args.kwonlyargs
            or function.args.vararg is not None
            or function.args.kwarg is not None
        ):
            continue
        body = list(function.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        local_name: str | None = None
        local_kind: Literal["module", "function"] | None = None
        if len(body) == 2:
            import_statement, return_statement = body
            if isinstance(import_statement, ast.Import) and len(import_statement.names) == 1:
                alias = import_statement.names[0]
                if alias.name == "importlib":
                    local_name = alias.asname or alias.name
                    local_kind = "module"
            elif isinstance(import_statement, ast.ImportFrom) and len(import_statement.names) == 1:
                alias = import_statement.names[0]
                if (
                    import_statement.level == 0
                    and import_statement.module == "importlib"
                    and alias.name == "import_module"
                ):
                    local_name = alias.asname or alias.name
                    local_kind = "function"
            if local_name is None or local_kind is None:
                continue
        elif len(body) == 1:
            return_statement = body[0]
        else:
            continue
        if not isinstance(return_statement, ast.Return) or return_statement.value is None:
            continue
        attribute: str | None = None
        imported = return_statement.value
        if isinstance(imported, ast.Attribute):
            attribute = imported.attr
            imported = imported.value
        if not isinstance(imported, ast.Call) or len(imported.args) != 1 or imported.keywords:
            continue
        if not isinstance(imported.args[0], ast.Constant) or not isinstance(imported.args[0].value, str):
            continue
        imported_module = imported.args[0].value
        if imported_module.startswith("."):
            continue
        if local_kind == "module":
            callable_is_proven = (
                isinstance(imported.func, ast.Attribute)
                and isinstance(imported.func.value, ast.Name)
                and imported.func.value.id == local_name
                and imported.func.attr == "import_module"
            )
        elif local_kind == "function":
            callable_is_proven = isinstance(imported.func, ast.Name) and imported.func.id == local_name
        elif isinstance(imported.func, ast.Name):
            callable_is_proven = module_bindings.get(imported.func.id) == "function"
        else:
            callable_is_proven = (
                isinstance(imported.func, ast.Attribute)
                and isinstance(imported.func.value, ast.Name)
                and imported.func.attr == "import_module"
                and module_bindings.get(imported.func.value.id) == "module"
            )
        if not callable_is_proven:
            continue
        resolution = _Resolution(modules=frozenset({imported_module}), known=True)
        if attribute is not None:
            resolution = _resolve_symbol(imported_module, attribute, exports, module_names)
            if not resolution.known and not resolution.error_qualnames:
                continue
        if function.name in accessors:
            accessors.pop(function.name, None)
            ambiguous.add(function.name)
        else:
            accessors[function.name] = (imported, resolution)
    return accessors


def _direct_route_statements(statements: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    for statement in statements:
        yield statement
        if isinstance(statement, ast.If):
            yield from _direct_route_statements(statement.body)
            yield from _direct_route_statements(statement.orelse)
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            yield from _direct_route_statements(statement.body)
            for handler in statement.handlers:
                yield from _direct_route_statements(handler.body)
            yield from _direct_route_statements(statement.orelse)
            yield from _direct_route_statements(statement.finalbody)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            yield from _direct_route_statements(statement.body)


def _static_lazy_import_module_calls(module: _ProductionModule) -> tuple[ast.Call, ...]:
    candidates = [
        statement
        for statement in module.tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name == "__getattr__"
    ]
    if len(candidates) != 1:
        return ()
    route = candidates[0]
    parameters = (*route.args.posonlyargs, *route.args.args)
    if len(parameters) != 1 or route.args.vararg is not None or route.args.kwarg is not None:
        return ()
    name = parameters[0].arg
    values: dict[str, ast.AST] = {}
    mapping_names: list[str] = []
    statements = tuple(_direct_route_statements(route.body))
    if any(isinstance(statement, (ast.Try, ast.TryStar)) for statement in statements):
        return ()
    for node in statements:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = node.value
            if _lazy_mapping_lookup(node.value, name=name):
                mapping_names.append(node.targets[0].id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            values[node.target.id] = node.value
            if _lazy_mapping_lookup(node.value, name=name):
                mapping_names.append(node.target.id)
    if len(mapping_names) != 1:
        return ()
    mapping_name = mapping_names[0]
    returns = [node for node in statements if isinstance(node, ast.Return)]
    if len(returns) != 1 or returns[0] not in route.body:
        return ()
    node = returns[0]
    if node.value is None:
        return ()
    value = values.get(node.value.id, node.value) if isinstance(node.value, ast.Name) else node.value
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "getattr":
        return ()
    if len(value.args) != 2 or value.keywords or not isinstance(value.args[1], ast.Name) or value.args[1].id != name:
        return ()
    imported = values.get(value.args[0].id, value.args[0]) if isinstance(value.args[0], ast.Name) else value.args[0]
    return (
        (imported,)
        if isinstance(imported, ast.Call) and _import_module_call(imported, mapping_name=mapping_name, module=module)
        else ()
    )


def _lazy_route_is_static(module: _ProductionModule) -> bool:
    return bool(_static_lazy_import_module_calls(module))


def _lazy_exports(module: _ProductionModule) -> dict[str, str]:
    lazy = _static_module_bindings(module).get("_LAZY_EXPORTS")
    if lazy is None:
        return {}
    if not _lazy_route_is_static(module):
        raise _recovery_error("E_REHOMING_LAZY_GETATTR", module.relative_path)
    if not isinstance(lazy, dict):
        raise _recovery_error("E_REHOMING_LAZY_EXPORTS_STATIC", module.relative_path)
    lazy_map = cast(dict[object, object], lazy)
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in lazy_map.items()):
        raise _recovery_error("E_REHOMING_LAZY_EXPORTS_STATIC", module.relative_path)
    exports: dict[str, str] = {}
    for raw_name, raw_relative_module in lazy_map.items():
        name = cast(str, raw_name)
        relative_module = cast(str, raw_relative_module)
        if not name or not relative_module:
            raise _recovery_error("E_REHOMING_LAZY_EXPORTS_VALUE", module.relative_path)
        if relative_module.startswith("."):
            resolved = _absolute_module(
                module, len(relative_module) - len(relative_module.lstrip(".")), relative_module.lstrip(".")
            )
        else:
            resolved = relative_module
        exports[name] = resolved
    return exports


def _module_bases(modules: tuple[_ProductionModule, ...], targets: frozenset[str]) -> dict[str, dict[str, _Resolution]]:
    module_names = {module.module for module in modules}
    bases: dict[str, dict[str, _Resolution]] = {module.module: {} for module in modules}
    for module in modules:
        base = bases[module.module]
        for candidate in module_names:
            parent, _, child = candidate.rpartition(".")
            if parent == module.module:
                base[child] = _Resolution(modules=frozenset({candidate}))
        for statement in module.tree.body:
            if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{module.module}.{statement.name}"
                base[statement.name] = _Resolution(
                    error_qualnames=frozenset({qualname}) if qualname in targets else frozenset(), known=True
                )
    return bases


def _resolve_symbol(
    module_name: str,
    name: str,
    exports: dict[str, dict[str, _Resolution]],
    module_names: frozenset[str],
) -> _Resolution:
    direct = f"{module_name}.{name}"
    result = exports.get(module_name, {}).get(name, _EMPTY_RESOLUTION)
    if direct in module_names:
        result = result.merged(_Resolution(modules=frozenset({direct})))
    return result


def _module_statements(nodes: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    for statement in nodes:
        if isinstance(
            statement,
            (
                ast.Import,
                ast.ImportFrom,
                ast.Assign,
                ast.AnnAssign,
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            yield statement
            continue
        if isinstance(statement, ast.If):
            yield from _module_statements(statement.body)
            yield from _module_statements(statement.orelse)
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            yield from _module_statements(statement.body)
            for handler in statement.handlers:
                yield from _module_statements(handler.body)
            yield from _module_statements(statement.orelse)
            yield from _module_statements(statement.finalbody)


def _resolve_module_exports(
    modules: tuple[_ProductionModule, ...], targets: frozenset[str]
) -> dict[str, dict[str, _Resolution]]:
    module_names = frozenset(module.module for module in modules)
    bases = _module_bases(modules, targets)
    lazy = {module.module: _lazy_exports(module) for module in modules}
    exports = {name: dict(values) for name, values in bases.items()}
    limit = len(modules) * 2 + 1
    for _round in range(limit):
        next_exports: dict[str, dict[str, _Resolution]] = {}
        for module in modules:
            values = dict(bases[module.module])
            for statement in _module_statements(module.tree.body):
                if isinstance(statement, ast.Import):
                    for alias in statement.names:
                        target = alias.name if alias.asname else alias.name.split(".")[0]
                        if target in module_names:
                            values[alias.asname or target] = _Resolution(modules=frozenset({target}))
                elif isinstance(statement, ast.ImportFrom):
                    source = (
                        statement.module
                        if statement.level == 0 and statement.module is not None
                        else _absolute_module(module, statement.level, statement.module)
                    )
                    for alias in statement.names:
                        if alias.name == "*":
                            if any(value.error_qualnames for value in exports.get(source, {}).values()):
                                raise _recovery_error("E_REHOMING_TARGET_STAR_IMPORT", module.relative_path, source)
                            continue
                        values[alias.asname or alias.name] = _resolve_symbol(source, alias.name, exports, module_names)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    assigned = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    expression = statement.value
                    if expression is not None and isinstance(expression, ast.Name):
                        value = values.get(expression.id, _EMPTY_RESOLUTION)
                        for target in assigned:
                            if isinstance(target, ast.Name):
                                values[target.id] = value
            for name, source in lazy[module.module].items():
                values[name] = _resolve_symbol(source, name, exports, module_names)
            next_exports[module.module] = values
        if next_exports == exports:
            target_names = frozenset(qualname.rpartition(".")[2] for qualname in targets)
            for module_name, entries in lazy.items():
                for name, source in entries.items():
                    if name not in target_names:
                        continue
                    candidates = _resolve_symbol(source, name, next_exports, module_names).error_qualnames & targets
                    if len(candidates) != 1:
                        raise _recovery_error("E_REHOMING_LAZY_TARGET", module_name, name, *sorted(candidates))
            return next_exports
        exports = next_exports
    raise _recovery_error("E_REHOMING_EXPORT_FIXED_POINT", limit)


def _node_location(node: ast.AST, *, path: str) -> tuple[int, int, int, int]:
    attributes = cast(dict[str, object], vars(node))
    line = attributes.get("lineno")
    column = attributes.get("col_offset")
    end_line = attributes.get("end_lineno")
    end_column = attributes.get("end_col_offset")
    if (
        type(line) is not int
        or line < 1
        or type(column) is not int
        or column < 0
        or type(end_line) is not int
        or end_line < line
        or type(end_column) is not int
        or end_column < 0
        or (end_line == line and end_column < column)
    ):
        raise _recovery_error("E_REHOMING_SOURCE_LOCATION", path, type(node).__name__)
    return line, column, end_line, end_column


def _normalized_ast_value(value: object) -> object:
    if isinstance(value, ast.AST):
        return [
            type(value).__name__,
            [[field, _normalized_ast_value(cast(object, getattr(value, field)))] for field in value._fields],
        ]
    if isinstance(value, list):
        return [_normalized_ast_value(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return ["tuple", [_normalized_ast_value(item) for item in cast(tuple[object, ...], value)]]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, complex):
        return ["complex", value.real, value.imag]
    if value is Ellipsis:
        return ["ellipsis"]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise _recovery_error("E_REHOMING_AST_VALUE", type(value).__name__)


def _normalized_ast_sha256(node: ast.AST) -> str:
    payload = f"{_AST_FORMAT}:{json.dumps(_normalized_ast_value(node), ensure_ascii=False, separators=(',', ':'))}"
    return hashlib.sha256(payload.encode(_UTF_8)).hexdigest()


class _ScopeBinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()

    def _target(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            self.names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                self._target(item)

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._target(target)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._target(node.target)
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._target(node.target)
        self.visit(node.value)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self._target(target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._target(node.target)
        self.visit(node.value)

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        self._target(node.target)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit_For(node)

    def visit_With(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._target(item.optional_vars)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.visit_With(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocals.update(node.names)

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        for case in node.cases:
            self.names.update(_pattern_binders(case.pattern))
            if case.guard is not None:
                self.visit(case.guard)
            for statement in case.body:
                self.visit(statement)


def _scope_binders(body: Iterable[ast.stmt]) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    visitor = _ScopeBinder()
    for statement in body:
        visitor.visit(statement)
    return frozenset(visitor.names), frozenset(visitor.globals), frozenset(visitor.nonlocals)


def _expression_binders(node: ast.AST) -> frozenset[str]:
    visitor = _ScopeBinder()
    visitor.visit(node)
    return frozenset(visitor.names)


def _assignment_target_names(node: ast.AST) -> frozenset[str]:
    names: set[str] = set()

    def collect(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                collect(item)

    collect(node)
    return frozenset(names)


def _pattern_binders(pattern: ast.pattern) -> frozenset[str]:
    if isinstance(pattern, ast.MatchAs):
        nested: set[str] = set(_pattern_binders(pattern.pattern)) if pattern.pattern is not None else set()
        if pattern.name is not None:
            nested.add(pattern.name)
        return frozenset(nested)
    if isinstance(pattern, ast.MatchStar):
        return frozenset({pattern.name}) if pattern.name is not None else frozenset()
    if isinstance(pattern, ast.MatchSequence):
        return frozenset(name for item in pattern.patterns for name in _pattern_binders(item))
    if isinstance(pattern, ast.MatchMapping):
        nested = {name for item in pattern.patterns for name in _pattern_binders(item)}
        if pattern.rest is not None:
            nested.add(pattern.rest)
        return frozenset(nested)
    if isinstance(pattern, ast.MatchClass):
        return frozenset(name for item in (*pattern.patterns, *pattern.kwd_patterns) for name in _pattern_binders(item))
    if isinstance(pattern, ast.MatchOr):
        alternatives = tuple(_pattern_binders(item) for item in pattern.patterns)
        if not alternatives or any(item != alternatives[0] for item in alternatives[1:]):
            raise _recovery_error("E_REHOMING_MATCH_BINDERS")
        return alternatives[0]
    if isinstance(pattern, (ast.MatchValue, ast.MatchSingleton)):
        return frozenset()
    raise _recovery_error("E_REHOMING_MATCH_PATTERN", type(pattern).__name__)


def _name_binding_nodes(node: ast.AST, name: str) -> tuple[ast.AST, ...]:
    """Return every syntactic binding of ``name`` without trusting execution order.

    This deliberately walks nested lexical scopes too.  A finite import domain
    is admissible only while its one canonical declaration has no competing
    binding anywhere in the module's source, including a later runtime
    reassignment through a nested scope.
    """
    bindings: list[ast.AST] = []

    def collect(current: ast.AST) -> None:
        if isinstance(current, ast.Name) and isinstance(current.ctx, ast.Store | ast.Del) and current.id == name:
            bindings.append(current)
        elif isinstance(current, ast.Import):
            if any((alias.asname or alias.name.split(".", 1)[0]) == name for alias in current.names):
                bindings.append(current)
        elif isinstance(current, ast.ImportFrom):
            if any(alias.name != "*" and (alias.asname or alias.name) == name for alias in current.names):
                bindings.append(current)
        elif isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if current.name == name:
                bindings.append(current)
        elif isinstance(current, ast.arg):
            if current.arg == name:
                bindings.append(current)
        elif isinstance(current, ast.ExceptHandler | ast.MatchAs):
            if current.name == name:
                bindings.append(current)
        elif isinstance(current, ast.MatchStar) and current.name == name:
            bindings.append(current)
        for child in ast.iter_child_nodes(current):
            collect(child)

    collect(node)
    return tuple(bindings)


def _sole_direct_import_source(module: _ProductionModule, name: str) -> str | None:
    """Resolve one direct, unrebound in-repository ``from`` import exactly."""
    bindings = _name_binding_nodes(module.tree, name)
    if len(bindings) != 1 or not isinstance(bindings[0], ast.ImportFrom):
        return None
    statement = bindings[0]
    if statement not in module.tree.body or len(statement.names) != 1:
        return None
    alias = statement.names[0]
    if alias.name != name or alias.asname is not None:
        return None
    if statement.level == 0:
        return statement.module
    return _absolute_module(module, statement.level, statement.module)


def _sole_literal_tuple_domain(module: _ProductionModule, name: str) -> frozenset[str] | None:
    """Return an unaliased, unrebound module-level literal string tuple only."""
    bindings = _name_binding_nodes(module.tree, name)
    if len(bindings) != 1 or not isinstance(bindings[0], ast.Name):
        return None
    target = bindings[0]
    declaration = next(
        (
            statement
            for statement in module.tree.body
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1 and statement.targets[0] is target)
            or (isinstance(statement, ast.AnnAssign) and statement.target is target and statement.value is not None)
        ),
        None,
    )
    if declaration is None:
        return None
    value = declaration.value
    if not isinstance(value, ast.Tuple) or not value.elts:
        return None
    values: list[str] = []
    for item in value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        values.append(item.value)
    return frozenset(values)


class _LexicalScanner(ast.NodeVisitor):
    def __init__(
        self,
        module: _ProductionModule,
        exports: dict[str, dict[str, _Resolution]],
        modules_by_name: dict[str, _ProductionModule],
        targets: frozenset[str],
    ) -> None:
        self.module = module
        self.exports = exports
        self.modules_by_name = modules_by_name
        self.targets = targets
        self.module_names = frozenset(exports)
        self.static_bindings = _static_module_bindings(module)
        module_scope = dict(exports[module.module])
        for statement in module.tree.body:
            if isinstance(statement, ast.ClassDef):
                module_scope.pop(statement.name, None)
        self.scopes: list[dict[str, _Resolution]] = [module_scope]
        self.scope_kinds: list[Literal["module", "function", "class", "comprehension"]] = ["module"]
        self.scope_globals: list[frozenset[str]] = [frozenset()]
        self.scope_nonlocals: list[frozenset[str]] = [frozenset()]
        self.named_owners: list[str] = [module.module]
        self.static_lazy_import_module_calls = frozenset(id(node) for node in _static_lazy_import_module_calls(module))
        self.static_import_module_accessors = _static_import_module_accessors(module, exports, self.module_names)
        self.static_import_module_accessor_calls = frozenset(
            id(call) for call, _ in self.static_import_module_accessors.values()
        )
        self.static_import_module_accessor_call_resolutions = {
            id(call): resolution for call, resolution in self.static_import_module_accessors.values()
        }
        self.safe_non_target_import_module_calls: dict[int, _Resolution] = {}
        self.parents = {id(child): parent for parent in ast.walk(module.tree) for child in ast.iter_child_nodes(parent)}
        self.observations: list[tuple[str, SourceFingerprint]] = []
        #: Identities (pre-ordinal) of constructor calls that pass a positional
        #: argument. A registered error resolves its operator text from its
        #: message key, but ``str(exc)`` prefers ``args[0]``, so a positional
        #: argument is an authored sentence reaching tracebacks and logs in
        #: every locale. This is evidence about the call shape only; it carries
        #: no action, condition, command, or locale policy.
        self.authored_message_sites: list[tuple[str, tuple[str, str, str, str, str]]] = []

    def _lookup(self, name: str) -> _Resolution:
        index = len(self.scopes) - 1
        deferred_function = self.scope_kinds[index] == "function"
        while index >= 0:
            if name in self.scope_globals[index]:
                return self.scopes[0].get(name, _EMPTY_RESOLUTION)
            if name in self.scope_nonlocals[index]:
                return self._nonlocal_lookup(index, name)
            if name in self.scopes[index]:
                return self.scopes[index][name]
            if index == 0 and deferred_function:
                return self.exports[self.module.module].get(name, _EMPTY_RESOLUTION)
            index = self._parent_scope(index)
        return _EMPTY_RESOLUTION

    def _parent_scope(self, index: int) -> int:
        parent = index - 1
        if (
            self.scope_kinds[index] in {"function", "comprehension"}
            and parent > 0
            and self.scope_kinds[parent] == "class"
        ):
            return parent - 1
        return parent

    def _nonlocal_lookup(self, index: int, name: str) -> _Resolution:
        parent = self._parent_scope(index)
        while parent > 0:
            if self.scope_kinds[parent] == "function" and name in self.scopes[parent]:
                return self.scopes[parent][name]
            parent = self._parent_scope(parent)
        raise _recovery_error("E_REHOMING_NONLOCAL", self.module.relative_path, name)

    def _bind_at(self, index: int, name: str, resolution: _Resolution) -> None:
        if name in self.scope_globals[index]:
            self.scopes[0][name] = resolution
            return
        if name in self.scope_nonlocals[index]:
            parent = self._parent_scope(index)
            while parent > 0:
                if self.scope_kinds[parent] == "function" and name in self.scopes[parent]:
                    self.scopes[parent][name] = resolution
                    return
                parent = self._parent_scope(parent)
            raise _recovery_error("E_REHOMING_NONLOCAL", self.module.relative_path, name)
        self.scopes[index][name] = resolution

    def _bind_name(self, name: str, resolution: _Resolution) -> None:
        self._bind_at(len(self.scopes) - 1, name, resolution)

    def _delete_name(self, name: str) -> None:
        index = len(self.scopes) - 1
        if name in self.scope_globals[index]:
            self.scopes[0].pop(name, None)
            return
        if name in self.scope_nonlocals[index]:
            parent = self._parent_scope(index)
            while parent > 0:
                if self.scope_kinds[parent] == "function" and name in self.scopes[parent]:
                    self.scopes[parent][name] = _EMPTY_RESOLUTION
                    return
                parent = self._parent_scope(parent)
            raise _recovery_error("E_REHOMING_NONLOCAL", self.module.relative_path, name)
        if self.scope_kinds[index] == "function" or self.scope_kinds[index] == "comprehension":
            self.scopes[index][name] = _EMPTY_RESOLUTION
        else:
            self.scopes[index].pop(name, None)

    def _resolve(self, node: ast.AST) -> _Resolution:
        if isinstance(node, ast.Call) and id(node) in self.static_import_module_accessor_call_resolutions:
            return self.static_import_module_accessor_call_resolutions[id(node)]
        if (
            isinstance(node, ast.Call)
            and not node.args
            and not node.keywords
            and isinstance(node.func, ast.Name)
            and node.func.id in self.static_import_module_accessors
        ):
            return self.static_import_module_accessors[node.func.id][1]
        if isinstance(node, ast.Name):
            return self._lookup(node.id)
        if isinstance(node, ast.Attribute):
            result = _EMPTY_RESOLUTION
            for module_name in self._resolve(node.value).modules:
                result = result.merged(_resolve_symbol(module_name, node.attr, self.exports, self.module_names))
            return result
        return _EMPTY_RESOLUTION

    def _fingerprint(self, node: ast.AST, *, role: Literal["constructor", "reference"]) -> SourceFingerprint:
        line, column, end_line, end_column = _node_location(node, path=self.module.relative_path)
        return SourceFingerprint(
            self.module.relative_path,
            self.named_owners[-1],
            role,
            _AST_FORMAT,
            _normalized_ast_sha256(node),
            0,
            line,
            column,
            end_line,
            end_column,
        )

    def _record(self, resolution: _Resolution, node: ast.AST, *, role: Literal["constructor", "reference"]) -> None:
        exact = resolution.error_qualnames & self.targets
        if not exact:
            return
        if len(exact) != 1:
            line, column, _, _ = _node_location(node, path=self.module.relative_path)
            raise _recovery_error("E_REHOMING_TARGET_AMBIGUOUS", self.module.relative_path, line, column)
        qualname = next(iter(exact))
        fingerprint = self._fingerprint(node, role=role)
        self.observations.append((qualname, fingerprint))
        if role == "constructor" and isinstance(node, ast.Call) and node.args:
            self.authored_message_sites.append((qualname, fingerprint.structural_group))

    def _has_target_export(self, resolution: _Resolution) -> bool:
        return any(
            value.error_qualnames & self.targets
            for module_name in resolution.modules
            for value in self.exports.get(module_name, {}).values()
        )

    def _literal_names(self, node: ast.AST, *, name: str) -> frozenset[str] | None:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
            return None
        if not isinstance(node.left, ast.Name) or node.left.id != name:
            return None
        comparator = node.comparators[0]
        if (
            isinstance(node.ops[0], ast.Eq)
            and isinstance(comparator, ast.Constant)
            and isinstance(comparator.value, str)
        ):
            return frozenset({comparator.value})
        if not isinstance(node.ops[0], ast.In):
            return None
        if isinstance(comparator, ast.Name):
            value = self.static_bindings.get(comparator.id)
            if not isinstance(value, (tuple, list, frozenset)):
                return None
            collection = cast(tuple[object, ...] | list[object] | frozenset[object], value)
            return (
                frozenset(cast(str, item) for item in collection)
                if all(isinstance(item, str) for item in collection)
                else None
            )
        if not isinstance(comparator, (ast.Tuple, ast.List, ast.Set)):
            return None
        values = [
            item.value for item in comparator.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        return frozenset(values) if len(values) == len(comparator.elts) else None

    def _guarded_names(self, node: ast.AST, *, name: str) -> frozenset[str] | None:
        parent = self.parents.get(id(node))
        while parent is not None:
            if isinstance(parent, ast.If):
                names = self._literal_names(parent.test, name=name)
                if names is not None:
                    return names
            parent = self.parents.get(id(parent))
        return None

    def _record_guarded_getattr(self, node: ast.Call) -> bool:
        if not isinstance(node.func, ast.Name) or node.func.id != "getattr" or not node.args:
            return False
        base = self._resolve(node.args[0])
        if not self._has_target_export(base):
            return False
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Name):
            raise _recovery_error("E_REHOMING_DYNAMIC_CALL", self.module.relative_path, node.lineno)
        names = self._guarded_names(node, name=node.args[1].id)
        if names is None:
            raise _recovery_error("E_REHOMING_DYNAMIC_CALL", self.module.relative_path, node.lineno)
        target_names = frozenset(qualname.rpartition(".")[2] for qualname in self.targets)
        for name in names & target_names:
            candidates = frozenset(
                candidate
                for module_name in base.modules
                for candidate in _resolve_symbol(module_name, name, self.exports, self.module_names).error_qualnames
                if candidate in self.targets
            )
            if len(candidates) != 1:
                raise _recovery_error(
                    "E_REHOMING_DYNAMIC_SYMBOL", self.module.relative_path, node.lineno, *sorted(candidates), name
                )
            self._record(_Resolution(error_qualnames=candidates, known=True), node, role="reference")
        return True

    def _dynamic_target_path(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Name) and node.func.id == "__import__" and node.args:
            module_name = node.args[0]
            if isinstance(module_name, ast.Constant) and isinstance(module_name.value, str):
                return self._has_target_export(_Resolution(modules=frozenset({module_name.value})))
        return False

    def _is_static_lazy_facade_call(self, node: ast.Call) -> bool:
        return id(node) in self.static_lazy_import_module_calls

    def _is_import_module_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Name):
            return "importlib.import_module" in self._resolve(node.func).modules
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and "importlib" in self._resolve(node.func.value).modules
        )

    def _import_module_name(self, node: ast.Call) -> str | None:
        if not node.args:
            return None
        module_name = _static_value(node.args[0], self.static_bindings)
        if not isinstance(module_name, str):
            return None
        if not module_name.startswith("."):
            return module_name
        level = len(module_name) - len(module_name.lstrip("."))
        source = module_name.lstrip(".")
        if len(node.args) > 1:
            package = _static_value(node.args[1], self.static_bindings)
            if isinstance(node.args[1], ast.Name) and node.args[1].id == "__name__":
                package = self.module.module
            if isinstance(package, str):
                package_parts = package.split(".")
                return ".".join((*package_parts[: len(package_parts) - level + 1], *source.split(".")))
        return _absolute_module(self.module, level, source)

    def _has_target_relevance(self) -> bool:
        if self._has_target_export(_Resolution(modules=frozenset({self.module.module}))):
            return True
        return any(resolution.error_qualnames & self.targets for scope in self.scopes for resolution in scope.values())

    def _dynamic_import_module_target_path(self, node: ast.Call) -> bool:
        if id(node) in self.safe_non_target_import_module_calls:
            return False
        if (
            not self._is_import_module_call(node)
            or self._is_static_lazy_facade_call(node)
            or id(node) in self.static_import_module_accessor_calls
        ):
            return False
        if self._safe_bounded_import_module_side_effect(node):
            return False
        module_name = self._import_module_name(node)
        if module_name is not None:
            return self._has_target_export(_Resolution(modules=frozenset({module_name})))
        return True

    def _safe_bounded_import_module_side_effect(self, node: ast.Call) -> bool:
        """Prove a finite in-corpus registration loop discards every result."""
        if len(node.args) != 1 or node.keywords or not isinstance(node.args[0], ast.Name):
            return False
        expression = self.parents.get(id(node))
        if not isinstance(expression, ast.Expr) or expression.value is not node:
            return False
        container = self.parents.get(id(expression))
        if isinstance(container, ast.Try):
            if container.body != [expression] or container.orelse or container.finalbody or not container.handlers:
                return False
            loop = self.parents.get(id(container))
            loop_statement: ast.stmt = container
        else:
            loop = container
            loop_statement = expression
        if not (
            isinstance(loop, ast.For)
            and not loop.orelse
            and isinstance(loop.target, ast.Name)
            and loop.target.id == node.args[0].id
            and loop_statement in loop.body
        ):
            return False
        domain = self._static_guard_domain(loop.iter)
        if domain is None or any(module_name not in self.module_names for module_name in domain):
            return False
        bindings, global_names, nonlocal_names = _scope_binders(
            statement for statement in loop.body if statement is not expression
        )
        return node.args[0].id not in bindings | global_names | nonlocal_names

    def _static_guard_domain(self, node: ast.AST) -> frozenset[str] | None:
        declarations: list[ast.Assign | ast.AnnAssign] = []
        if isinstance(node, ast.Name):
            if len(_name_binding_nodes(self.module.tree, node.id)) != 1:
                return None
            declarations = [
                statement
                for statement in self.module.tree.body
                if (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == node.id
                )
                or (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == node.id
                    and statement.value is not None
                )
            ]
            if len(declarations) > 1:
                return None
            if declarations:
                declaration_value = declarations[0].value
                if isinstance(declaration_value, ast.Set) or (
                    isinstance(declaration_value, ast.Call)
                    and isinstance(declaration_value.func, ast.Name)
                    and declaration_value.func.id in {"set", "list"}
                ):
                    return None
        direct = _static_value(node, self.static_bindings)
        if isinstance(direct, tuple | frozenset):
            direct_domain = cast(tuple[object, ...] | frozenset[object], direct)
            if direct_domain and all(isinstance(item, str) for item in direct_domain):
                return frozenset(cast(str, item) for item in direct_domain)
        if not isinstance(node, ast.Name):
            return None
        if not declarations:
            source = _sole_direct_import_source(self.module, node.id)
            if source is None:
                return None
            imported_module = self.modules_by_name.get(source)
            if imported_module is None:
                return None
            return _sole_literal_tuple_domain(imported_module, node.id)
        if len(declarations) != 1:
            return None
        value = declarations[0].value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and len(value.args) == 1
            and not value.keywords
            and isinstance(value.args[0], ast.GeneratorExp)
        ):
            return None
        generator = value.args[0]
        if len(generator.generators) != 1 or generator.generators[0].is_async or generator.generators[0].ifs:
            return None
        clause = generator.generators[0]
        if not isinstance(generator.elt, ast.Name) or not isinstance(clause.target, (ast.Tuple, ast.List)):
            return None
        positions = [
            index
            for index, item in enumerate(clause.target.elts)
            if isinstance(item, ast.Name) and item.id == generator.elt.id
        ]
        if len(positions) != 1 or not isinstance(clause.iter, ast.Name):
            return None
        source_values: list[ast.Tuple] = []
        for statement in self.module.tree.body:
            if (
                (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == clause.iter.id
                )
                or (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == clause.iter.id
                )
            ) and isinstance(statement.value, ast.Tuple):
                source_values.append(statement.value)
        if len(source_values) != 1:
            return None
        position = positions[0]
        values: list[str] = []
        for item in source_values[0].elts:
            if not isinstance(item, ast.Tuple) or len(item.elts) <= position:
                return None
            selected = item.elts[position]
            if not isinstance(selected, ast.Constant) or not isinstance(selected.value, str):
                return None
            values.append(selected.value)
        return frozenset(values) if values else None

    def _guarded_import_module_names(
        self, node: ast.Call, owner: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> frozenset[str] | None:
        if not node.args or not isinstance(node.args[0], ast.Name):
            return None
        argument = node.args[0].id
        binding_scope: ast.FunctionDef | ast.AsyncFunctionDef | None = owner
        while binding_scope is not None:
            route_bindings, global_names, nonlocal_names = _scope_binders(binding_scope.body)
            if argument in route_bindings or argument in global_names or argument in nonlocal_names:
                return None
            parameters = {
                parameter.arg
                for parameter in (
                    *binding_scope.args.posonlyargs,
                    *binding_scope.args.args,
                    *binding_scope.args.kwonlyargs,
                )
            }
            if binding_scope.args.vararg is not None:
                parameters.add(binding_scope.args.vararg.arg)
            if binding_scope.args.kwarg is not None:
                parameters.add(binding_scope.args.kwarg.arg)
            if argument in parameters:
                break
            parent = self.parents.get(id(binding_scope))
            binding_scope = parent if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
        if binding_scope is None:
            return None
        for statement in owner.body:
            if statement.lineno >= node.lineno or not isinstance(statement, ast.If) or statement.orelse:
                continue
            test = statement.test
            if not (
                isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.NotIn)
                and isinstance(test.left, ast.Name)
                and test.left.id == argument
                and len(test.comparators) == 1
            ):
                continue
            domain = self._static_guard_domain(test.comparators[0])
            if domain is None:
                continue
            if len(statement.body) == 1 and isinstance(statement.body[0], ast.Raise):
                return domain
        return None

    def _safe_non_target_import_module_assignment(self, node: ast.Call, target: ast.AST) -> _Resolution | None:
        """Prove an imported module value remains closed to target access."""
        if not isinstance(target, ast.Name) or not self._is_import_module_call(node):
            return None
        owner: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        parent = self.parents.get(id(node))
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner = parent
                break
            parent = self.parents.get(id(parent))
        if owner is None:
            return None

        module_name = self._import_module_name(node)
        modules = (
            frozenset({module_name}) if module_name is not None else self._guarded_import_module_names(node, owner)
        )
        resolution = _Resolution(modules=modules, known=True) if modules is not None else _EMPTY_RESOLUTION

        name = target.id
        route_bindings, global_names, nonlocal_names = _scope_binders(owner.body)
        parameters = {argument.arg for argument in (*owner.args.posonlyargs, *owner.args.args, *owner.args.kwonlyargs)}
        if owner.args.vararg is not None:
            parameters.add(owner.args.vararg.arg)
        if owner.args.kwarg is not None:
            parameters.add(owner.args.kwarg.arg)
        if name not in route_bindings or name in parameters or name in global_names or name in nonlocal_names:
            return None

        bindings: list[ast.AST] = []
        loads: list[ast.Name] = []
        nested_reference = False

        def collect(current: ast.AST) -> None:
            nonlocal nested_reference
            if current is not owner and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if current.name == name:
                    bindings.append(current)
                if any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(current)):
                    nested_reference = True
                return
            if isinstance(current, ast.Lambda):
                if any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(current)):
                    nested_reference = True
                return
            if isinstance(current, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                if any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(current)):
                    nested_reference = True
                return
            if isinstance(current, ast.Import):
                if any((alias.asname or alias.name.split(".", 1)[0]) == name for alias in current.names):
                    bindings.append(current)
                return
            if isinstance(current, ast.ImportFrom):
                if any((alias.asname or alias.name) == name for alias in current.names):
                    bindings.append(current)
                return
            if isinstance(current, ast.Assign):
                if any(name in _assignment_target_names(item) for item in current.targets):
                    bindings.append(current)
            elif isinstance(current, ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
                if name in _assignment_target_names(current.target):
                    bindings.append(current)
            elif isinstance(current, ast.Delete):
                if any(name in _assignment_target_names(item) for item in current.targets):
                    bindings.append(current)
            elif isinstance(current, (ast.For, ast.AsyncFor, ast.comprehension)):
                if name in _assignment_target_names(current.target):
                    bindings.append(current)
            elif isinstance(current, (ast.With, ast.AsyncWith)):
                if any(
                    item.optional_vars is not None and name in _assignment_target_names(item.optional_vars)
                    for item in current.items
                ):
                    bindings.append(current)
            elif isinstance(current, ast.ExceptHandler):
                if current.name == name:
                    bindings.append(current)
            elif isinstance(current, ast.Match):
                matches_name = any(name in _pattern_binders(case.pattern) for case in current.cases)
                if matches_name:
                    bindings.append(current)
            elif isinstance(current, ast.Name) and current.id == name and isinstance(current.ctx, ast.Load):
                loads.append(current)
            for child in ast.iter_child_nodes(current):
                collect(child)

        collect(owner)
        assignment = self.parents.get(id(node))
        if nested_reference or len(bindings) != 1 or bindings[0] is not assignment or not loads:
            return None
        target_names = frozenset(qualname.rpartition(".")[2] for qualname in self.targets)
        for load in loads:
            attribute = self.parents.get(id(load))
            if not (
                isinstance(attribute, ast.Attribute) and attribute.value is load and attribute.attr not in target_names
            ):
                return None
            if modules is None and attribute.attr != "__path__":
                return None
            attribute_parent = self.parents.get(id(attribute))
            if not (
                (isinstance(attribute_parent, (ast.Assign, ast.AnnAssign)) and attribute_parent.value is attribute)
                or isinstance(attribute_parent, ast.Call)
                or (isinstance(attribute_parent, ast.Return) and attribute_parent.value is attribute)
            ):
                return None
        self.safe_non_target_import_module_calls[id(node)] = resolution
        return resolution

    def _bind(self, target: ast.AST, resolution: _Resolution) -> None:
        if isinstance(target, ast.Name):
            self._bind_name(target.id, resolution)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._bind(item, _EMPTY_RESOLUTION)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "importlib":
                self._bind_name(
                    alias.asname or alias.name,
                    _Resolution(modules=frozenset({"importlib"}), known=True),
                )
                continue
            target = alias.name if alias.asname else alias.name.split(".")[0]
            if target in self.module_names:
                self._bind_name(alias.asname or target, _Resolution(modules=frozenset({target}), known=True))
            else:
                self._bind_name(alias.asname or target, _EMPTY_RESOLUTION)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        source = (
            node.module
            if node.level == 0 and node.module is not None
            else _absolute_module(self.module, node.level, node.module)
        )
        for alias in node.names:
            if alias.name == "*":
                if any(value.error_qualnames for value in self.exports.get(source, {}).values()):
                    raise _recovery_error("E_REHOMING_TARGET_STAR_IMPORT", self.module.relative_path, node.lineno)
                continue
            if node.level == 0 and node.module == "importlib" and alias.name == "import_module":
                self._bind_name(
                    alias.asname or alias.name,
                    _Resolution(modules=frozenset({"importlib.import_module"}), known=True),
                )
                continue
            self._bind_name(
                alias.asname or alias.name, _resolve_symbol(source, alias.name, self.exports, self.module_names)
            )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(self._resolve(node), node, role="reference")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(self._resolve(node), node, role="reference")
        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        self._record(
            self._resolve(node.func),
            node,
            role="constructor",
        )
        if (
            not node.args
            and not node.keywords
            and isinstance(node.func, ast.Name)
            and node.func.id in self.static_import_module_accessors
        ):
            self._record(self._resolve(node), node, role="reference")
        guarded_getattr = self._record_guarded_getattr(node)
        if not guarded_getattr and self._dynamic_target_path(node):
            raise _recovery_error("E_REHOMING_DYNAMIC_CALL", self.module.relative_path, node.lineno)
        if self._dynamic_import_module_target_path(node):
            raise _recovery_error("E_REHOMING_DYNAMIC_IMPORT_MODULE", self.module.relative_path, node.lineno)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Assign(self, node: ast.Assign) -> None:
        safe_resolution = (
            self._safe_non_target_import_module_assignment(node.value, node.targets[0])
            if len(node.targets) == 1 and isinstance(node.value, ast.Call)
            else None
        )
        self.visit(node.value)
        resolution = safe_resolution or self._resolve(node.value)
        for target in node.targets:
            self._bind(target, resolution)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self.module.future_annotations:
            self.visit(node.annotation)
        if node.value is not None:
            safe_resolution = (
                self._safe_non_target_import_module_assignment(node.value, node.target)
                if isinstance(node.value, ast.Call)
                else None
            )
            self.visit(node.value)
            self._bind(node.target, safe_resolution or self._resolve(node.value))
        else:
            self._bind(node.target, _EMPTY_RESOLUTION)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            for name in _assignment_target_names(target):
                self._delete_name(name)
            if not isinstance(target, (ast.Name, ast.Tuple, ast.List)):
                self.visit(target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        safe_resolution = (
            self._safe_non_target_import_module_assignment(node.value, node.target)
            if isinstance(node.value, ast.Call)
            else None
        )
        self.visit(node.value)
        resolution = safe_resolution or self._resolve(node.value)
        if self.scope_kinds[-1] == "comprehension":
            for name in _assignment_target_names(node.target):
                parent = self._parent_scope(len(self.scopes) - 1)
                if parent < 0:
                    raise _recovery_error("E_REHOMING_COMPREHENSION_BIND", self.module.relative_path, name)
                self._bind_at(parent, name, resolution)
        else:
            self._bind(node.target, resolution)

    def _visit_comprehension(self, generators: list[ast.comprehension], terminal: ast.AST) -> None:
        if not generators:
            raise _recovery_error("E_REHOMING_COMPREHENSION_EMPTY", self.module.relative_path)
        self.visit(generators[0].iter)
        names = frozenset(name for generator in generators for name in _assignment_target_names(generator.target))
        self.scopes.append({name: _EMPTY_RESOLUTION for name in names})
        self.scope_kinds.append("comprehension")
        self.scope_globals.append(frozenset())
        self.scope_nonlocals.append(frozenset())
        for index, generator in enumerate(generators):
            if index:
                self.visit(generator.iter)
            self._bind(generator.target, _EMPTY_RESOLUTION)
            for condition in generator.ifs:
                self.visit(condition)
        self.visit(terminal)
        self.scopes.pop()
        self.scope_kinds.pop()
        self.scope_globals.pop()
        self.scope_nonlocals.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, node.elt)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, node.elt)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, node.elt)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, ast.Tuple(elts=[node.key, node.value], ctx=ast.Load()))

    def _visit_for(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        self._bind(node.target, _EMPTY_RESOLUTION)
        self._visit_block(node.body)
        self._visit_block(node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self._visit_for(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for(node)

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind(item.optional_vars, _EMPTY_RESOLUTION)
        self._visit_block(node.body)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is not None:
            self.visit(node.type)
        if node.name is not None:
            self._bind_name(node.name, _EMPTY_RESOLUTION)
        self._visit_block(node.body)
        if node.name is not None:
            self._bind_name(node.name, _EMPTY_RESOLUTION)

    def _visit_pattern(self, pattern: ast.pattern) -> None:
        if isinstance(pattern, ast.MatchValue):
            self.visit(pattern.value)
        elif isinstance(pattern, ast.MatchSequence):
            for item in pattern.patterns:
                self._visit_pattern(item)
        elif isinstance(pattern, ast.MatchMapping):
            for key in pattern.keys:
                self.visit(key)
            for item in pattern.patterns:
                self._visit_pattern(item)
        elif isinstance(pattern, ast.MatchClass):
            self.visit(pattern.cls)
            for item in (*pattern.patterns, *pattern.kwd_patterns):
                self._visit_pattern(item)
        elif isinstance(pattern, ast.MatchAs) and pattern.pattern is not None:
            self._visit_pattern(pattern.pattern)
        elif isinstance(pattern, ast.MatchOr):
            for item in pattern.patterns:
                self._visit_pattern(item)
        elif not isinstance(pattern, (ast.MatchAs, ast.MatchStar, ast.MatchSingleton)):
            raise _recovery_error("E_REHOMING_MATCH_PATTERN", type(pattern).__name__)

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        for case in node.cases:
            self._visit_pattern(case.pattern)
            for name in _pattern_binders(case.pattern):
                self._bind_name(name, _EMPTY_RESOLUTION)
            if case.guard is not None:
                self.visit(case.guard)
            self._visit_block(case.body)
            for name in _pattern_binders(case.pattern):
                self._bind_name(name, _EMPTY_RESOLUTION)

    def _visit_block(self, body: Iterable[ast.stmt]) -> None:
        for statement in body:
            self.visit(statement)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.named_owners.append(f"{self.named_owners[-1]}.{node.name}")
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        if not self.module.future_annotations:
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                self.visit(node.args.vararg.annotation)
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                self.visit(node.args.kwarg.annotation)
            if node.returns is not None:
                self.visit(node.returns)
        self._bind_name(node.name, _EMPTY_RESOLUTION)
        names, global_names, nonlocal_names = _scope_binders(node.body)
        scope = {name: _EMPTY_RESOLUTION for name in names - global_names - nonlocal_names}
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            scope[argument.arg] = _EMPTY_RESOLUTION
        if node.args.vararg is not None:
            scope[node.args.vararg.arg] = _EMPTY_RESOLUTION
        if node.args.kwarg is not None:
            scope[node.args.kwarg.arg] = _EMPTY_RESOLUTION
        self.scopes.append(scope)
        self.scope_kinds.append("function")
        self.scope_globals.append(global_names)
        self.scope_nonlocals.append(nonlocal_names)
        self._visit_block(node.body)
        self.scopes.pop()
        self.scope_kinds.pop()
        self.scope_globals.pop()
        self.scope_nonlocals.pop()
        self.named_owners.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        scope = {name: _EMPTY_RESOLUTION for name in _expression_binders(node.body)}
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            scope[argument.arg] = _EMPTY_RESOLUTION
        if node.args.vararg is not None:
            scope[node.args.vararg.arg] = _EMPTY_RESOLUTION
        if node.args.kwarg is not None:
            scope[node.args.kwarg.arg] = _EMPTY_RESOLUTION
        self.scopes.append(scope)
        self.scope_kinds.append("function")
        self.scope_globals.append(frozenset())
        self.scope_nonlocals.append(frozenset())
        self.visit(node.body)
        self.scopes.pop()
        self.scope_kinds.pop()
        self.scope_globals.pop()
        self.scope_nonlocals.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = f"{self.module.module}.{node.name}"
        self.named_owners.append(f"{self.named_owners[-1]}.{node.name}")
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        _, global_names, nonlocal_names = _scope_binders(node.body)
        self.scopes.append({})
        self.scope_kinds.append("class")
        self.scope_globals.append(global_names)
        self.scope_nonlocals.append(nonlocal_names)
        self._visit_block(node.body)
        self.scopes.pop()
        self.scope_kinds.pop()
        self.scope_globals.pop()
        self.scope_nonlocals.pop()
        self.named_owners.pop()
        self._bind_name(
            node.name,
            _Resolution(error_qualnames=frozenset({qualname}))
            if self.scope_kinds[-1] == "module" and qualname in self.targets
            else _EMPTY_RESOLUTION,
        )


def _scan_current_source(
    root: Path,
) -> tuple[
    dict[str, tuple[SourceFingerprint, ...]],
    dict[str, frozenset[tuple[str, str, str, str, str]]],
]:
    """Return current fingerprints plus the groups whose calls author a message."""
    modules = _production_modules(root)
    targets = _target_qualnames()
    _current_definitions(modules, targets)
    exports = _resolve_module_exports(modules, targets)
    modules_by_name = {module.module: module for module in modules}
    collected: dict[str, list[SourceFingerprint]] = defaultdict(list)
    authored: dict[str, set[tuple[str, str, str, str, str]]] = defaultdict(set)
    ordinals: defaultdict[tuple[str, str, str, str, str], int] = defaultdict(int)
    for module in modules:
        scanner = _LexicalScanner(module, exports, modules_by_name, targets)
        scanner.visit(module.tree)
        for qualname, fingerprint in scanner.observations:
            group = fingerprint.structural_group
            ordinals[group] += 1
            collected[qualname].append(fingerprint.with_ordinal(ordinals[group]))
        for qualname, group in scanner.authored_message_sites:
            authored[qualname].add(group)
    fingerprints = {
        qualname: tuple(sorted(values, key=lambda fingerprint: fingerprint.identity))
        for qualname, values in sorted(collected.items())
    }
    return fingerprints, {qualname: frozenset(groups) for qualname, groups in sorted(authored.items())}


def current_source_fingerprints(root: Path = REPO_ROOT) -> dict[str, tuple[SourceFingerprint, ...]]:
    """Return exact constructor and nonconstructor observations by historic qualname."""
    return _scan_current_source(root)[0]


def current_authored_message_groups(root: Path = REPO_ROOT) -> dict[str, frozenset[tuple[str, str, str, str, str]]]:
    """Return, per historic qualname, the constructor groups passing a positional argument.

    A registered error resolves its operator-facing text from its message key,
    but ``str(exc)`` prefers ``args[0]``. A constructor still passing a
    positional argument therefore keeps an authored sentence alive in
    tracebacks, logs, and every boundary that renders the exception directly,
    in every locale, while a key-and-context assertion stays green. This is the
    machine evidence that separates a producer still awaiting migration from
    one whose migration has landed.
    """
    return _scan_current_source(root)[1]


def main(argv: list[str] | None = None) -> int:
    """Validate a rehoming ledger's typed, source-only representation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_REHOMING_LEDGER_PATH)
    parser.add_argument("--plan", type=Path, default=_PLAN_PATH)
    parser.add_argument("--migrate-legacy", type=Path)
    parser.add_argument("--output", type=Path)
    migration_mode = parser.add_mutually_exclusive_group()
    migration_mode.add_argument("--write", action="store_true")
    migration_mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.migrate_legacy is not None:
            if arguments.output is None:
                raise _recovery_error("E_REHOMING_MIGRATION_OUTPUT_REQUIRED")
            if arguments.write:
                written = _write_migrated_ledger(
                    arguments.migrate_legacy,
                    arguments.output,
                    root=REPO_ROOT,
                    plan_path=arguments.plan,
                )
                print(f"E_REHOMING_MIGRATION_WRITTEN:{len(written.rows)}")
            else:
                ledger = migrate_legacy_ledger(arguments.migrate_legacy, plan_path=arguments.plan)
                rendered = render_rehoming_ledger(ledger)
                if arguments.check:
                    checked = _check_rendered_migration(
                        arguments.output,
                        rendered,
                        root=REPO_ROOT,
                        plan_path=arguments.plan,
                    )
                    print(f"E_REHOMING_MIGRATION_CHECKED:{len(checked.rows)}")
                else:
                    print(rendered, end="")
            return 0
        if arguments.output is not None or arguments.write or arguments.check:
            raise _recovery_error("E_REHOMING_MIGRATION_ARGUMENTS")
        ledger = validate_rehoming_ledger(load_rehoming_ledger(arguments.ledger), plan_path=arguments.plan)
    except RehomingLedgerError as error:
        print(error)
        return 1
    print(f"E_REHOMING_VALIDATED:{len(ledger.rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

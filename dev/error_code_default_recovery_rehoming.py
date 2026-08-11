"""Fail-closed, non-runtime rehoming ledger for retired error defaults.

This module owns only the typed representation and strict TOML boundary for
the historical-default rehoming join.  It intentionally contains no recovery
policy, rendered text, command identity, or locale data.
"""

from __future__ import annotations

import argparse
import ast
import tomllib
from collections import Counter, defaultdict
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
    "current_source_fingerprints",
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


@dataclass(frozen=True, slots=True)
class _ProductionModule:
    path: Path
    relative_path: str
    module: str
    is_package: bool
    tree: ast.Module


@dataclass(frozen=True, slots=True)
class _Resolution:
    error_qualnames: frozenset[str] = frozenset()
    modules: frozenset[str] = frozenset()

    def merged(self, other: _Resolution) -> _Resolution:
        return _Resolution(self.error_qualnames | other.error_qualnames, self.modules | other.modules)


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
        modules.append(_ProductionModule(path, relative_path, module, is_package, tree))
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
    missing = sorted(targets - set(definitions))
    duplicates = sorted(qualname for qualname, found in definitions.items() if len(found) != 1)
    if missing or duplicates:
        raise RehomingLedgerError(
            tuple(f"E_REHOMING_TARGET_DEFINITION_MISSING:{value}" for value in missing)
            + tuple(f"E_REHOMING_TARGET_DEFINITION_AMBIGUOUS:{value}" for value in duplicates),
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
    if isinstance(node, ast.DictComp):
        comprehension_mapping: dict[object, object] = {}

        def visit_generator(index: int, local: dict[str, object]) -> bool:
            if index == len(node.generators):
                key = _static_value(node.key, local)
                value = _static_value(node.value, local)
                if key is None or value is None:
                    return False
                comprehension_mapping[key] = value
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

        return comprehension_mapping if visit_generator(0, dict(bindings)) else None
    return None


def _lazy_exports(module: _ProductionModule) -> dict[str, str]:
    bindings: dict[str, object] = {}
    lazy: object | None = None
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            value = _static_value(statement.value, bindings)
            if (
                value is not None
                and _static_bind(statement.targets[0], value, bindings)
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "_LAZY_EXPORTS"
            ):
                lazy = value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            value = _static_value(statement.value, bindings)
            if (
                value is not None
                and _static_bind(statement.target, value, bindings)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == "_LAZY_EXPORTS"
            ):
                lazy = value
    if lazy is None:
        return {}
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
            if isinstance(statement, ast.ClassDef):
                qualname = f"{module.module}.{statement.name}"
                if qualname in targets:
                    base[statement.name] = _Resolution(error_qualnames=frozenset({qualname}))
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
                    source = _absolute_module(module, statement.level, statement.module)
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
            return next_exports
        exports = next_exports
    raise _recovery_error("E_REHOMING_EXPORT_FIXED_POINT", limit)


def _node_location(node: ast.AST, *, path: str) -> tuple[int, int]:
    attributes = cast(dict[str, object], vars(node))
    line = attributes.get("lineno")
    column = attributes.get("col_offset")
    if type(line) is not int or line < 1 or type(column) is not int or column < 0:
        raise _recovery_error("E_REHOMING_SOURCE_LOCATION", path, type(node).__name__)
    return line, column


class _LexicalScanner(ast.NodeVisitor):
    def __init__(
        self,
        module: _ProductionModule,
        exports: dict[str, dict[str, _Resolution]],
        targets: frozenset[str],
    ) -> None:
        self.module = module
        self.exports = exports
        self.targets = targets
        self.module_names = frozenset(exports)
        self.scopes: list[dict[str, _Resolution]] = [dict(exports[module.module])]
        self.parents = {id(child): parent for parent in ast.walk(module.tree) for child in ast.iter_child_nodes(parent)}
        self.fingerprints: dict[str, list[SourceFingerprint]] = defaultdict(list)

    def _lookup(self, name: str) -> _Resolution:
        if name in self.scopes[-1]:
            return self.scopes[-1][name]
        return self.scopes[0].get(name, _EMPTY_RESOLUTION)

    def _resolve(self, node: ast.AST) -> _Resolution:
        if isinstance(node, ast.Name):
            return self._lookup(node.id)
        if isinstance(node, ast.Attribute):
            result = _EMPTY_RESOLUTION
            for module_name in self._resolve(node.value).modules:
                result = result.merged(_resolve_symbol(module_name, node.attr, self.exports, self.module_names))
            return result
        return _EMPTY_RESOLUTION

    def _fingerprint(
        self, node: ast.AST, *, context: str, kind: Literal["constructor", "reference"]
    ) -> SourceFingerprint:
        line, column = _node_location(node, path=self.module.relative_path)
        return SourceFingerprint(self.module.relative_path, line, column, context, kind)

    def _record(
        self, resolution: _Resolution, node: ast.AST, *, context: str, kind: Literal["constructor", "reference"]
    ) -> None:
        exact = resolution.error_qualnames & self.targets
        if not exact:
            return
        if len(exact) != 1:
            line, column = _node_location(node, path=self.module.relative_path)
            raise _recovery_error("E_REHOMING_TARGET_AMBIGUOUS", self.module.relative_path, line, column)
        self.fingerprints[next(iter(exact))].append(self._fingerprint(node, context=context, kind=kind))

    def _bind(self, target: ast.AST, resolution: _Resolution) -> None:
        if isinstance(target, ast.Name):
            self.scopes[-1][target.id] = resolution
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._bind(item, _EMPTY_RESOLUTION)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            target = alias.name if alias.asname else alias.name.split(".")[0]
            if target in self.module_names:
                self.scopes[-1][alias.asname or target] = _Resolution(modules=frozenset({target}))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        source = _absolute_module(self.module, node.level, node.module)
        for alias in node.names:
            if alias.name == "*":
                if any(value.error_qualnames for value in self.exports.get(source, {}).values()):
                    raise _recovery_error("E_REHOMING_TARGET_STAR_IMPORT", self.module.relative_path, node.lineno)
                continue
            self.scopes[-1][alias.asname or alias.name] = _resolve_symbol(
                source, alias.name, self.exports, self.module_names
            )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(self._resolve(node), node, context="name", kind="reference")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(self._resolve(node), node, context="attribute", kind="reference")
        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        self._record(
            self._resolve(node.func),
            node,
            context=type(self.parents.get(id(node), self.module.tree)).__name__,
            kind="constructor",
        )
        if isinstance(node.func, ast.Name) and node.func.id in {"getattr", "__import__"}:
            raise _recovery_error("E_REHOMING_DYNAMIC_CALL", self.module.relative_path, node.lineno)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        resolution = self._resolve(node.value)
        for target in node.targets:
            self._bind(target, resolution)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
            self._bind(node.target, self._resolve(node.value))
        else:
            self._bind(node.target, _EMPTY_RESOLUTION)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind(node.target, self._resolve(node.value))

    def _visit_block(self, body: Iterable[ast.stmt]) -> None:
        for statement in body:
            self.visit(statement)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scopes[-1][node.name] = _EMPTY_RESOLUTION
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        scope: dict[str, _Resolution] = {}
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            scope[argument.arg] = _EMPTY_RESOLUTION
        if node.args.vararg is not None:
            scope[node.args.vararg.arg] = _EMPTY_RESOLUTION
        if node.args.kwarg is not None:
            scope[node.args.kwarg.arg] = _EMPTY_RESOLUTION
        self.scopes.append(scope)
        self._visit_block(node.body)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = f"{self.module.module}.{node.name}"
        self.scopes[-1][node.name] = (
            _Resolution(error_qualnames=frozenset({qualname})) if qualname in self.targets else _EMPTY_RESOLUTION
        )
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        self.scopes.append({})
        self._visit_block(node.body)
        self.scopes.pop()


def current_source_fingerprints(root: Path = REPO_ROOT) -> dict[str, tuple[SourceFingerprint, ...]]:
    """Return exact constructor and nonconstructor observations by historic qualname."""
    modules = _production_modules(root)
    targets = _target_qualnames()
    _current_definitions(modules, targets)
    exports = _resolve_module_exports(modules, targets)
    collected: dict[str, list[SourceFingerprint]] = defaultdict(list)
    for module in modules:
        scanner = _LexicalScanner(module, exports, targets)
        scanner.visit(module.tree)
        for qualname, fingerprints in scanner.fingerprints.items():
            collected[qualname].extend(fingerprints)
    return {
        qualname: tuple(sorted(fingerprints, key=lambda fingerprint: fingerprint.identity))
        for qualname, fingerprints in sorted(collected.items())
    }


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

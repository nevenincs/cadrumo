"""Parse and reconcile adjudications for CLI action-census candidates.

``dev.quality.cli_action_census`` owns mechanical discovery.  This module deliberately
does not repeat that walk: it turns the census's stable candidate identity into
a versioned TOML record and refuses an incomplete, stale, or ambiguous
adjudication set.  The checked-in ledger is populated by the next campaign
step; this module supplies the strict representation and reconciliation
primitive that makes that population auditable.
"""

from __future__ import annotations

import argparse
import ast
import json
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from cadrumo.core import scan_directory
from dev._paths import UTF_8

from .cli_action_census import REPO_ROOT, SOURCE_ROOT, CandidateRecord, census

__all__ = [
    "DEFAULT_DISPOSITIONS_PATH",
    "CandidateDisposition",
    "CandidateKey",
    "DispositionRole",
    "DispositionValidationError",
    "ExceptionOverrideObservation",
    "ExceptionOverrideRole",
    "ExclusionGrounding",
    "checked_in_dispositions",
    "current_exception_override_observations",
    "load_dispositions",
    "render_dispositions",
    "validate_dispositions",
    "validate_exception_override_owners",
]


_UTF_8: Final[str] = UTF_8
_SCHEMA_VERSION: Final[int] = 2
_TOP_LEVEL_FIELDS: Final[frozenset[str]] = frozenset({"meta", "disposition"})
_META_FIELDS: Final[frozenset[str]] = frozenset({"schema_version"})
_ROW_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "path",
        "enclosing_symbol",
        "candidate_role",
        "alias",
        "action_identity",
        "role",
        "reason",
        "symbol",
        "enclosing_function",
        "exception_observations",
    },
)

DEFAULT_DISPOSITIONS_PATH: Final[Path] = Path(__file__).with_suffix(".toml")
"""The checked-in ledger path to be populated after the model is established."""


class DispositionRole(StrEnum):
    """The closed, adjudicated roles a census candidate can carry."""

    CANONICAL_OWNER = "canonical_owner"
    PRODUCER = "producer"
    TRANSFORMER = "transformer"
    RENDERER = "renderer"
    VALIDATOR = "validator"
    TEST = "test"
    EXCLUDED = "excluded"


class ExceptionOverrideRole(StrEnum):
    """Data-flow role of one live exception action override."""

    SELECTOR = "selector"
    FORWARDER = "forwarder"
    MUTATOR = "mutator"


@dataclass(frozen=True, slots=True)
class CandidateKey:
    """The location-independent identity emitted by the canonical census."""

    path: str
    enclosing_symbol: str
    candidate_role: str
    alias: str
    action_identity: str

    @classmethod
    def from_candidate(cls, candidate: CandidateRecord) -> CandidateKey:
        """Convert one real census record without restating census semantics."""
        return cls(
            path=candidate.path,
            enclosing_symbol=candidate.enclosing_symbol,
            candidate_role=candidate.role,
            alias=candidate.alias,
            action_identity=candidate.action_identity,
        )

    def render(self) -> str:
        """Return one deterministic diagnostic identity."""
        return f"{self.path}::{self.enclosing_symbol} [{self.candidate_role} {self.alias}={self.action_identity!r}]"


@dataclass(frozen=True, slots=True)
class ExclusionGrounding:
    """The source-level basis required when a candidate is excluded."""

    symbol: str
    enclosing_function: str


@dataclass(frozen=True, slots=True)
class ExceptionOverrideObservation:
    """One physical, current-tree write to the retired exception action field.

    ``key`` intentionally remains the S01 location-independent identity.  The
    fingerprint adds an occurrence ordinal, so a copied same-expression write
    in one function cannot hide behind that stable key.
    """

    key: CandidateKey
    role: ExceptionOverrideRole
    form: str
    action_field: str
    expression: str
    ordinal: int
    line: int
    column: int
    mro_proven: bool = True

    @property
    def locator(self) -> str:
        """Return the current source locator for diagnostics only."""
        return f"{self.line}:{self.column}"

    @property
    def fingerprint(self) -> str:
        """Return a stable physical-observation identity for the ledger."""
        return "|".join((self.role.value, self.form, self.action_field, self.expression, str(self.ordinal)))


@dataclass(frozen=True, slots=True)
class CandidateDisposition:
    """One adjudication of one stable candidate identity."""

    key: CandidateKey
    role: DispositionRole
    reason: str
    exclusion: ExclusionGrounding | None = None
    exception_observations: tuple[str, ...] = ()


class DispositionValidationError(ValueError):
    """Raised with every deterministic error found in an adjudication pass."""

    def __init__(self, errors: Iterable[str]) -> None:
        """Join sorted diagnostics so every caller sees the same failure order."""
        self.errors = tuple(sorted(set(errors)))
        super().__init__("\n".join(self.errors))


def _require_identity_text(
    table: dict[str, object],
    field: str,
    *,
    context: str,
    errors: list[str],
    preserve_surrounding_whitespace: bool = False,
) -> str | None:
    value = table.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: missing or empty {field!r}")
        return None
    if not preserve_surrounding_whitespace and value != value.strip():
        errors.append(f"{context}: {field!r} must not have surrounding whitespace")
        return None
    return value


def _require_reason(table: dict[str, object], *, context: str, errors: list[str]) -> str | None:
    value = table.get("reason")
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: missing or empty 'reason'")
        return None
    return value.strip()


def _parse_role(table: dict[str, object], *, context: str, errors: list[str]) -> DispositionRole | None:
    raw_role = _require_identity_text(table, "role", context=context, errors=errors)
    if raw_role is None:
        return None
    try:
        return DispositionRole(raw_role)
    except ValueError:
        allowed = ", ".join(role.value for role in DispositionRole)
        errors.append(f"{context}: unrecognized disposition role {raw_role!r}; allowed: {allowed}")
        return None


def _parse_exception_owner(
    table: dict[str, object],
    *,
    context: str,
    errors: list[str],
) -> tuple[str, ...]:
    """Read optional current-tree ownership evidence without accepting half rows."""
    raw_observations = table.get("exception_observations")
    if raw_observations is None:
        return ()
    if not isinstance(raw_observations, list) or not raw_observations:
        errors.append(f"{context}: exception_observations must be a non-empty string array")
        observations: tuple[str, ...] = ()
    else:
        observation_values = cast(list[object], raw_observations)
        if any(not isinstance(item, str) or not item for item in observation_values):
            errors.append(f"{context}: exception_observations must contain non-empty strings")
            observations = ()
        else:
            observations = tuple(cast(str, item) for item in observation_values)
            if len(set(observations)) != len(observations):
                errors.append(f"{context}: exception_observations must not contain duplicates")
    return observations


def _parse_disposition_row(
    row: dict[str, object],
    *,
    context: str,
    errors: list[str],
) -> CandidateDisposition | None:
    unknown = sorted(set(row) - _ROW_FIELDS)
    if unknown:
        errors.append(f"{context}: unrecognized field(s): {', '.join(unknown)}")

    path = _require_identity_text(row, "path", context=context, errors=errors)
    enclosing_symbol = _require_identity_text(row, "enclosing_symbol", context=context, errors=errors)
    candidate_role = _require_identity_text(row, "candidate_role", context=context, errors=errors)
    alias = _require_identity_text(row, "alias", context=context, errors=errors)
    action_identity = _require_identity_text(
        row,
        "action_identity",
        context=context,
        errors=errors,
        preserve_surrounding_whitespace=True,
    )
    role = _parse_role(row, context=context, errors=errors)
    reason = _require_reason(row, context=context, errors=errors)
    exception_observations = _parse_exception_owner(row, context=context, errors=errors)

    if (
        path is None
        or enclosing_symbol is None
        or candidate_role is None
        or alias is None
        or action_identity is None
        or role is None
        or reason is None
    ):
        return None

    key = CandidateKey(
        path=path,
        enclosing_symbol=enclosing_symbol,
        candidate_role=candidate_role,
        alias=alias,
        action_identity=action_identity,
    )
    if role is not DispositionRole.EXCLUDED:
        prohibited = sorted(field for field in ("symbol", "enclosing_function") if field in row)
        if prohibited:
            errors.append(f"{context}: non-excluded disposition carries exclusion field(s): {', '.join(prohibited)}")
            return None
        return CandidateDisposition(
            key=key,
            role=role,
            reason=reason,
            exception_observations=exception_observations,
        )

    symbol = _require_identity_text(row, "symbol", context=context, errors=errors)
    enclosing_function = _require_identity_text(row, "enclosing_function", context=context, errors=errors)
    if symbol is None or enclosing_function is None:
        return None
    return CandidateDisposition(
        key=key,
        role=role,
        reason=reason,
        exclusion=ExclusionGrounding(symbol=symbol, enclosing_function=enclosing_function),
        exception_observations=exception_observations,
    )


def load_dispositions(path: Path) -> tuple[CandidateDisposition, ...]:
    """Read one strict TOML adjudication ledger without claiming coverage.

    Loading checks the representation itself.  :func:`validate_dispositions`
    separately compares the parsed records with the current real census, so a
    caller cannot mistake a well-formed partial migration ledger for complete
    coverage.
    """
    try:
        data = cast(dict[str, object], tomllib.loads(path.read_text(encoding=_UTF_8)))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise DispositionValidationError((f"cannot read disposition ledger {path}: {error}",)) from error

    errors: list[str] = []
    unknown_top_level = sorted(set(data) - _TOP_LEVEL_FIELDS)
    if unknown_top_level:
        errors.append(f"{path}: unrecognized top-level field(s): {', '.join(unknown_top_level)}")

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append(f"{path}: missing [meta] table")
    else:
        meta_table = cast(dict[str, object], meta)
        unknown_meta = sorted(set(meta_table) - _META_FIELDS)
        if unknown_meta:
            errors.append(f"{path} [meta]: unrecognized field(s): {', '.join(unknown_meta)}")
        schema_version: object | None = meta_table.get("schema_version")
        if type(schema_version) is not int or schema_version != _SCHEMA_VERSION:
            errors.append(f"{path} [meta]: schema_version must be {_SCHEMA_VERSION}")

    raw_rows: object = data.get("disposition", [])
    if not isinstance(raw_rows, list):
        errors.append(f"{path}: 'disposition' must be an array of tables")
        rows: list[object] = []
    else:
        rows = cast(list[object], raw_rows)

    parsed: list[CandidateDisposition] = []
    for index, raw_row in enumerate(rows, start=1):
        context = f"{path} [[disposition]] #{index}"
        if not isinstance(raw_row, dict):
            errors.append(f"{context}: must be a table")
            continue
        record = _parse_disposition_row(cast(dict[str, object], raw_row), context=context, errors=errors)
        if record is not None:
            parsed.append(record)

    if errors:
        raise DispositionValidationError(errors)
    return tuple(parsed)


def _terminal_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _source_expression(node: ast.expr) -> str:
    """Preserve the syntactic value that selected or forwarded the action."""
    return ast.unparse(node)


def _is_error_name(name: str | None) -> bool:
    return name is not None and (name.endswith("Error") or name.endswith("Exception"))


def _class_bases(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Return local inheritance names for conservative static error/MRO proof."""
    result: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            result[node.name] = tuple(name for base in node.bases if (name := _terminal_name(base)) is not None)
    return result


def _derives_error(name: str, bases: dict[str, tuple[str, ...]], seen: frozenset[str] = frozenset()) -> bool:
    if name in seen:
        return False
    direct = bases.get(name, ())
    return _is_error_name(name) or any(
        _is_error_name(base) or _derives_error(base, bases, seen | {name}) for base in direct
    )


def _mro_dispatch_aliases(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Find local ``cast(CadrumoError, super())`` aliases without executing code."""
    aliases: set[str] = set()
    for statement in node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1:
                continue
            target: ast.expr = statement.targets[0]
        else:
            target = statement.target
        value: ast.expr | None = statement.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call) or _terminal_name(value.func) != "cast":
            continue
        if len(value.args) != 2 or _terminal_name(value.args[0]) != "CadrumoError":
            continue
        if isinstance(value.args[1], ast.Call) and _terminal_name(value.args[1].func) == "super":
            aliases.add(target.id)
    return frozenset(aliases)


class _ExceptionOverrideVisitor(ast.NodeVisitor):
    """Extract the four static override shapes from one current source file."""

    def __init__(self, path: str, bases: dict[str, tuple[str, ...]]) -> None:
        self.path = path
        self.bases = bases
        self.symbols: list[str] = []
        self.classes: list[str] = []
        self.parameters: list[frozenset[str]] = []
        self.mro_aliases: list[frozenset[str]] = []
        self.exception_bindings: list[frozenset[str]] = []
        self.records: list[ExceptionOverrideObservation] = []

    @property
    def symbol(self) -> str:
        return ".".join(self.symbols) if self.symbols else "<module>"

    def _add(
        self,
        node: ast.Call | ast.Assign,
        value: ast.expr,
        *,
        role: ExceptionOverrideRole,
        form: str,
        candidate_role: str,
        mro_proven: bool = True,
    ) -> None:
        identity = (
            value.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
            else _source_expression(value)
        )
        key = CandidateKey(self.path, self.symbol, candidate_role, "suggestion", identity)
        self.records.append(
            ExceptionOverrideObservation(
                key=key,
                role=role,
                form=form,
                action_field="suggestion",
                expression=_source_expression(value),
                ordinal=0,
                line=node.lineno,
                column=node.col_offset,
                mro_proven=mro_proven,
            ),
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(node.name)
        self.classes.append(node.name)
        self.generic_visit(node)
        self.classes.pop()
        self.symbols.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parameters = frozenset(
            argument.arg for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        )
        self.symbols.append(node.name)
        self.parameters.append(parameters)
        self.mro_aliases.append(_mro_dispatch_aliases(node))
        self.generic_visit(node)
        self.mro_aliases.pop()
        self.parameters.pop()
        self.symbols.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        names: frozenset[str] = (
            frozenset((node.name,))
            if node.name and node.type is not None and _is_error_name(_terminal_name(node.type))
            else frozenset[str]()
        )
        self.exception_bindings.append(names)
        self.generic_visit(node)
        self.exception_bindings.pop()

    def _is_forwarder(self, value: ast.expr) -> bool:
        if isinstance(value, ast.Name):
            return bool(self.parameters and value.id in self.parameters[-1])
        return isinstance(value, ast.Attribute) and value.attr == "suggestion"

    def visit_Call(self, node: ast.Call) -> None:
        suggestion = next((keyword.value for keyword in node.keywords if keyword.arg == "suggestion"), None)
        if suggestion is not None:
            function = node.func
            if _is_error_name(_terminal_name(function)):
                self._add(
                    node,
                    suggestion,
                    role=ExceptionOverrideRole.FORWARDER
                    if self._is_forwarder(suggestion)
                    else ExceptionOverrideRole.SELECTOR,
                    form="constructor_keyword",
                    candidate_role="producer",
                )
            elif (
                isinstance(function, ast.Attribute)
                and function.attr == "__init__"
                and isinstance(function.value, ast.Call)
                and _terminal_name(function.value.func) == "super"
                and self.classes
                and _derives_error(self.classes[-1], self.bases)
            ):
                self._add(
                    node,
                    suggestion,
                    role=ExceptionOverrideRole.FORWARDER
                    if self._is_forwarder(suggestion)
                    else ExceptionOverrideRole.SELECTOR,
                    form="super_init",
                    candidate_role="producer",
                )
            elif (
                isinstance(function, ast.Attribute)
                and function.attr == "__init__"
                and isinstance(function.value, ast.Name)
                and self.mro_aliases
                and function.value.id in self.mro_aliases[-1]
            ):
                self._add(
                    node,
                    suggestion,
                    role=ExceptionOverrideRole.FORWARDER,
                    form="cooperative_mro",
                    candidate_role="producer",
                    mro_proven=bool(self.classes and self._mro_proven(self.classes[-1])),
                )
        self.generic_visit(node)

    def _mro_proven(self, mixin: str) -> bool:
        return any(
            mixin in direct_bases
            and any(_derives_error(base, self.bases) for base in direct_bases[direct_bases.index(mixin) + 1 :])
            for direct_bases in self.bases.values()
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        bound: frozenset[str] = frozenset(name for names in self.exception_bindings for name in names)
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "suggestion"
                and isinstance(target.value, ast.Name)
                and target.value.id in bound
            ):
                self._add(
                    node,
                    node.value,
                    role=ExceptionOverrideRole.MUTATOR,
                    form="exception_attribute_mutation",
                    candidate_role="assignment",
                )
        self.generic_visit(node)


def current_exception_override_observations(
    *,
    root: Path = REPO_ROOT,
) -> tuple[ExceptionOverrideObservation, ...]:
    """Return live exception-action observations from the current worktree.

    This intentionally reads the filesystem rather than a Git revision: S29 is
    a drift gate over work in progress, while S01's revision census remains the
    formatting-stable campaign baseline.
    """
    records: list[ExceptionOverrideObservation] = []
    for source_path in scan_directory(
        root / SOURCE_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)
    ):
        if "/tests/" in source_path.as_posix() or source_path.name.startswith("test_"):
            continue
        path = source_path.relative_to(root).as_posix()
        try:
            tree = ast.parse(source_path.read_text(encoding=_UTF_8), filename=path)
        except OSError as error:
            raise DispositionValidationError(
                (f"current exception-override census cannot read {path}: {type(error).__name__}",),
            ) from error
        except UnicodeDecodeError as error:
            raise DispositionValidationError(
                (f"current exception-override census cannot decode {path}: {type(error).__name__}",),
            ) from error
        except SyntaxError as error:
            raise DispositionValidationError(
                (f"current exception-override census cannot parse {path}: {type(error).__name__}",),
            ) from error
        visitor = _ExceptionOverrideVisitor(path, _class_bases(tree))
        visitor.visit(tree)
        records.extend(visitor.records)
    grouped: dict[CandidateKey, list[ExceptionOverrideObservation]] = {}
    for record in records:
        grouped.setdefault(record.key, []).append(record)
    numbered: list[ExceptionOverrideObservation] = []
    for group in grouped.values():
        for ordinal, record in enumerate(sorted(group, key=lambda item: (item.line, item.column)), start=1):
            numbered.append(replace(record, ordinal=ordinal))
    return tuple(sorted(numbered, key=lambda item: (item.key.render(), item.line, item.column)))


def validate_exception_override_owners(
    dispositions: Iterable[CandidateDisposition],
    *,
    root: Path = REPO_ROOT,
) -> tuple[ExceptionOverrideObservation, ...]:
    """Fail on missing, stale, duplicate, or drifted override ownership.

    Step ownership is deliberately NOT asserted here. Reading it meant citing a
    plan document by path and shelling the vault CLI, which couples this gate to
    the project's own development records -- the one direction the Code Stands
    Alone mandate forbids. What survives is what this gate can prove from the
    tree alone: the adjudicated role, the observation set, and the cooperative
    MRO.
    """
    observations = current_exception_override_observations(root=root)
    rows_by_key: dict[CandidateKey, list[CandidateDisposition]] = {}
    for row in dispositions:
        rows_by_key.setdefault(row.key, []).append(row)
    observed_by_key: dict[CandidateKey, list[ExceptionOverrideObservation]] = {}
    for observation in observations:
        observed_by_key.setdefault(observation.key, []).append(observation)

    errors: list[str] = []
    for key, records in sorted(observed_by_key.items(), key=lambda item: item[0].render()):
        owners = rows_by_key.get(key, [])
        if len(owners) != 1:
            errors.append(f"exception override has {len(owners)} adjudicated owners: {key.render()}")
            continue
        owner = owners[0]
        expected = tuple(sorted(record.fingerprint for record in records))
        if owner.role not in {DispositionRole.PRODUCER, DispositionRole.TRANSFORMER}:
            errors.append(
                f"exception override requires producer or transformer disposition role: {key.render()}",
            )
        if not owner.exception_observations:
            errors.append(f"exception override lacks exception_observations: {key.render()}")
        if tuple(sorted(owner.exception_observations)) != expected:
            errors.append(f"exception override observation set drifted: {key.render()}")
        if any(not record.mro_proven for record in records):
            errors.append(f"exception override cooperative MRO is not proven: {key.render()}")
    for key, owners in sorted(rows_by_key.items(), key=lambda item: item[0].render()):
        if any(owner.exception_observations for owner in owners) and key not in observed_by_key:
            errors.append(f"stale exception override owner has no current observation: {key.render()}")
    if errors:
        raise DispositionValidationError(errors)
    return observations


def _key_errors(key: CandidateKey, *, context: str) -> tuple[str, ...]:
    values = (
        ("path", cast(object, key.path)),
        ("enclosing_symbol", cast(object, key.enclosing_symbol)),
        ("candidate_role", cast(object, key.candidate_role)),
        ("alias", cast(object, key.alias)),
        ("action_identity", cast(object, key.action_identity)),
    )
    return tuple(
        f"{context}: missing or empty {field!r}" for field, value in values if not isinstance(value, str) or not value
    )


def _disposition_shape_errors(disposition: CandidateDisposition, *, context: str) -> tuple[str, ...]:
    errors = list(_key_errors(disposition.key, context=context))
    raw_role = cast(object, disposition.role)
    if not isinstance(raw_role, DispositionRole):
        errors.append(f"{context}: unrecognized disposition role {raw_role!r}")
        return tuple(errors)
    raw_reason = cast(object, disposition.reason)
    if not isinstance(raw_reason, str) or not raw_reason.strip():
        errors.append(f"{context}: missing or empty 'reason'")
    if len(set(disposition.exception_observations)) != len(disposition.exception_observations):
        errors.append(f"{context}: exception_observations must not contain duplicates")

    if raw_role is DispositionRole.EXCLUDED:
        exclusion = disposition.exclusion
        if exclusion is None:
            errors.append(f"{context}: excluded disposition requires symbol and enclosing_function grounding")
        else:
            symbol = cast(object, exclusion.symbol)
            enclosing_function = cast(object, exclusion.enclosing_function)
            if not isinstance(symbol, str) or not symbol.strip():
                errors.append(f"{context}: excluded disposition has an empty symbol")
            elif symbol != disposition.key.alias:
                errors.append(
                    f"{context}: exclusion symbol {symbol!r} does not match candidate alias {disposition.key.alias!r}",
                )
            if not isinstance(enclosing_function, str) or not enclosing_function.strip():
                errors.append(f"{context}: excluded disposition has an empty enclosing_function")
            elif enclosing_function != disposition.key.enclosing_symbol:
                errors.append(
                    f"{context}: exclusion enclosing_function {enclosing_function!r} does not match "
                    f"candidate enclosing_symbol {disposition.key.enclosing_symbol!r}",
                )
    elif disposition.exclusion is not None:
        errors.append(f"{context}: only excluded dispositions may carry exclusion grounding")
    return tuple(errors)


def validate_dispositions(
    candidates: Iterable[CandidateRecord],
    dispositions: Iterable[CandidateDisposition],
) -> tuple[CandidateDisposition, ...]:
    """Require a one-to-one, current, grounded reconciliation with real census output."""
    candidate_keys: dict[CandidateKey, CandidateRecord] = {}
    errors: list[str] = []
    for candidate in candidates:
        key = CandidateKey.from_candidate(candidate)
        if key in candidate_keys:
            errors.append(f"census emitted duplicate candidate key: {key.render()}")
        candidate_keys[key] = candidate

    parsed = tuple(dispositions)
    disposition_keys: dict[CandidateKey, list[CandidateDisposition]] = {}
    for index, disposition in enumerate(parsed, start=1):
        context = f"disposition #{index}"
        errors.extend(_disposition_shape_errors(disposition, context=context))
        disposition_keys.setdefault(disposition.key, []).append(disposition)

    for key, rows in sorted(disposition_keys.items(), key=lambda item: item[0].render()):
        if len(rows) > 1:
            errors.append(f"duplicate current disposition ({len(rows)} rows): {key.render()}")
        if key not in candidate_keys:
            errors.append(f"stale disposition has no current census candidate: {key.render()}")

    for key in sorted(candidate_keys, key=CandidateKey.render):
        if key not in disposition_keys:
            errors.append(f"missing disposition for current census candidate: {key.render()}")

    if errors:
        raise DispositionValidationError(errors)
    return tuple(sorted(parsed, key=lambda disposition: disposition.key.render()))


def _toml_string(value: str) -> str:
    """Render a TOML basic string through JSON's compatible string grammar."""
    return json.dumps(value, ensure_ascii=False)


def render_dispositions(dispositions: Iterable[CandidateDisposition]) -> str:
    """Serialize well-formed rows deterministically for the checked-in ledger.

    This only validates individual row shape.  Coverage remains an explicit
    reconciliation against a specific current census revision.
    """
    rows = tuple(dispositions)
    errors = [
        error
        for index, disposition in enumerate(rows, start=1)
        for error in _disposition_shape_errors(disposition, context=f"disposition #{index}")
    ]
    if errors:
        raise DispositionValidationError(errors)

    lines = ["[meta]", f"schema_version = {_SCHEMA_VERSION}"]
    for disposition in sorted(rows, key=lambda row: row.key.render()):
        key = disposition.key
        lines.extend(
            (
                "",
                "[[disposition]]",
                f"path = {_toml_string(key.path)}",
                f"enclosing_symbol = {_toml_string(key.enclosing_symbol)}",
                f"candidate_role = {_toml_string(key.candidate_role)}",
                f"alias = {_toml_string(key.alias)}",
                f"action_identity = {_toml_string(key.action_identity)}",
                f"role = {_toml_string(disposition.role.value)}",
                f"reason = {_toml_string(disposition.reason.strip())}",
            ),
        )
        if disposition.exclusion is not None:
            lines.extend(
                (
                    f"symbol = {_toml_string(disposition.exclusion.symbol)}",
                    f"enclosing_function = {_toml_string(disposition.exclusion.enclosing_function)}",
                ),
            )
        if disposition.exception_observations:
            lines.extend(
                (
                    "exception_observations = ["
                    + ", ".join(_toml_string(item) for item in disposition.exception_observations)
                    + "]",
                ),
            )
    return "\n".join(lines) + "\n"


def checked_in_dispositions(
    revision: str,
    *,
    path: Path = DEFAULT_DISPOSITIONS_PATH,
) -> tuple[CandidateDisposition, ...]:
    """Load the ledger and require complete coverage of one pinned real revision."""
    return validate_dispositions(census(revision), load_dispositions(path))


def main(argv: list[str] | None = None) -> int:
    """Validate a checked-in disposition ledger against one pinned census revision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Git revision to reconcile; use an immutable commit when citing output")
    parser.add_argument(
        "--dispositions",
        type=Path,
        default=DEFAULT_DISPOSITIONS_PATH,
        help="TOML ledger path (defaults to the checked-in campaign ledger)",
    )
    arguments = parser.parse_args(argv)
    try:
        rows = checked_in_dispositions(arguments.revision, path=arguments.dispositions)
    except DispositionValidationError as error:
        print(error)
        return 1
    print(f"reconciled {len(rows)} CLI action-census dispositions against {arguments.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

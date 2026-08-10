"""Parse and reconcile adjudications for CLI action-census candidates.

``dev.cli_action_census`` owns mechanical discovery.  This module deliberately
does not repeat that walk: it turns the census's stable candidate identity into
a versioned TOML record and refuses an incomplete, stale, or ambiguous
adjudication set.  The checked-in ledger is populated by the next campaign
step; this module supplies the strict representation and reconciliation
primitive that makes that population auditable.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from dev.cli_action_census import CandidateRecord, census

__all__ = [
    "DEFAULT_DISPOSITIONS_PATH",
    "CandidateDisposition",
    "CandidateKey",
    "DispositionRole",
    "DispositionValidationError",
    "ExclusionGrounding",
    "checked_in_dispositions",
    "load_dispositions",
    "render_dispositions",
    "validate_dispositions",
]


_UTF_8: Final[str] = "utf-8"
_SCHEMA_VERSION: Final[int] = 1
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
class CandidateDisposition:
    """One adjudication of one stable candidate identity."""

    key: CandidateKey
    role: DispositionRole
    reason: str
    exclusion: ExclusionGrounding | None = None


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
        return CandidateDisposition(key=key, role=role, reason=reason)

    symbol = _require_identity_text(row, "symbol", context=context, errors=errors)
    enclosing_function = _require_identity_text(row, "enclosing_function", context=context, errors=errors)
    if symbol is None or enclosing_function is None:
        return None
    return CandidateDisposition(
        key=key,
        role=role,
        reason=reason,
        exclusion=ExclusionGrounding(symbol=symbol, enclosing_function=enclosing_function),
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

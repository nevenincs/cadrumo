"""Generic readers for the persona catalogue's TOML tables."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from ..core.decimal.grammar import try_parse_canonical_decimal
from .inventory import REPO_ROOT
from .persona_types import CATALOGUE_FORMAT, PersonaDate, YearToken, _fail

type _Table = Mapping[str, object]


def _table(value: object, where: str) -> _Table:
    if not isinstance(value, dict):
        raise _fail(where, "expected a table")
    return cast(_Table, value)


def _tables(value: object, where: str) -> tuple[_Table, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise _fail(where, "expected an array of tables")
    return tuple(_table(item, f"{where}[{index}]") for index, item in enumerate(cast(list[object], value)))


def _keys(table: _Table, where: str, *, required: frozenset[str], optional: frozenset[str] = frozenset()) -> None:
    unknown = set(table) - required - optional
    if unknown:
        raise _fail(where, f"unknown fields {sorted(unknown)}")
    missing = required - set(table)
    if missing:
        raise _fail(where, f"missing fields {sorted(missing)}")


def _string(table: _Table, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise _fail(where, f"{key} must be a non-empty string")
    return value


def _optional_string(table: _Table, key: str, where: str) -> str | None:
    return None if key not in table else _string(table, key, where)


def _bool(table: _Table, key: str, where: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise _fail(where, f"{key} must be a boolean")
    return value


def _strings(table: _Table, key: str, where: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in cast(list[object], value)):
        raise _fail(where, f"{key} must be an array of strings")
    return tuple(cast(list[str], value))


def _choice[Choice: str](value: str, choices: tuple[Choice, ...], where: str) -> Choice:
    for choice in choices:
        if value == choice:
            return choice
    raise _fail(where, f"{value!r} is not one of {list(choices)}")


def _amount(text: object, where: str) -> Decimal:
    parsed = try_parse_canonical_decimal(text, signed=True) if isinstance(text, str) else None
    if parsed is None or text != str(parsed):
        raise _fail(where, f"{text!r} is not a canonical decimal amount")
    return parsed


def _string_map(table: _Table, key: str, where: str) -> tuple[tuple[str, str], ...]:
    if key not in table:
        return ()
    mapping = _table(table[key], f"{where}.{key}")
    if not all(isinstance(value, str) for value in mapping.values()):
        raise _fail(where, f"{key} values must be strings")
    return tuple((name, cast(str, value)) for name, value in mapping.items())


def _amount_map(table: _Table, key: str, where: str) -> tuple[tuple[str, str], ...]:
    """A string map whose every value is a canonical decimal amount."""
    mapping = _string_map(table, key, where)
    for name, amount in mapping:
        _amount(amount, f"{where}.{key}.{name}")
    return mapping


def _date(value: object, where: str, *, biographical: bool) -> PersonaDate:
    table = _table(value, where)
    _keys(table, where, required=frozenset({"year", "month", "day"}))
    month = table["month"]
    day = table["day"]
    if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12:
        raise _fail(where, "month must be 1..12")
    if day != "last" and (not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 31):
        raise _fail(where, 'day must be 1..31 or "last"')
    return PersonaDate(
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        month=month,
        day=cast(int | Literal["last"], day),
        biographical=biographical,
    )


def _read_toml(path: Path) -> _Table:
    where = str(path.relative_to(REPO_ROOT))
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise _fail(where, f"not TOML: {error}") from None
    if document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {document.get('format')!r}")
    return document

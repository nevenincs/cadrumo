"""The year gate's Python rules: how a syntax node writes a year as a bound, a comparison or a coordinate.

Each helper reads one node, with the module's source lines where a number's
spelling decides it, and says whether, or how, it breaks a rule. The reader in
``dev.quality.year_literal_python`` walks the tree and applies them.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator, Sequence
from typing import Final

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_LAST

from .year_literal_shapes import (
    DATE_TEXT,
    DATE_TEXT_START,
    EDITION_IN_TEXT,
    PERIOD_TEXT,
    YEAR_IN_TEXT,
    YEAR_SOURCE,
    YEAR_TEXT,
    is_edition_id,
    starts_period,
)

#: Any four-digit number. Held under a year name or compared with a year-named
#: value it is a year bound, even outside the filing century (``9999``, ``1900``).
FOUR_DIGITS: Final[re.Pattern[str]] = re.compile(r"^[1-9]\d\d\d$")

#: The words of a name that speak of a year.
YEAR_WORDS: Final[str] = r"years?|yr|ejercicios?|exercises?|anio|año|floor|horizon"
YEAR_NAME: Final[re.Pattern[str]] = re.compile(rf"(?:^|_)(?:{YEAR_WORDS})(?:_|$)", re.IGNORECASE)
_STRICT_YEAR_WORDS = r"years?|ejercicios?|anio|año"
STRICT_YEAR_NAME: Final[re.Pattern[str]] = re.compile(rf"(?:^|_)(?:{_STRICT_YEAR_WORDS})(?:_|$)", re.IGNORECASE)
_YEAR_CALL = re.compile(
    r"year|ejercicio|exercise|edition|revision|period|filing|deadline|plazo|calendar|holiday|festivo|envelope",
    re.IGNORECASE,
)
_PERIOD_CODE = re.compile(r"^(?:[1-4]T|0A|0[1-9]|1[0-2]|[1-4]P)$")
#: Calls that turn text into a date, an instant or a year.
_PARSE_CALLS = frozenset({"fromisoformat", "strptime", "isoparse", "to_datetime", "Timestamp", "datetime64"})
_PARSE_NAME = re.compile(
    r"(?:parse|from)_?\w*?(?:date|time|instant|day|iso)|(?:date|time|instant|day|iso)\w*?_?parse", re.IGNORECASE
)
#: Calls that build a date from a year, month and day.
DATE_CALLS: Final[frozenset[str]] = frozenset({"date", "datetime"})
_BOUND_KEYWORDS = frozenset({"ge", "le", "gt", "lt"})
#: Calls whose text arguments are amounts of money, never years.
AMOUNT_CALLS: Final[frozenset[str]] = frozenset({"Decimal", "Money", "Fraction"})


#: Words a comparison operand's name holds when it counts or measures; matched
#: as whole words of the name, so ``forms`` is not ``ms``.
_MEASURE_WORDS = re.compile(
    r"(?:^|_)(?:bytes|size|count|length|len|width|height|chars|limit|max|min|ms|millis|seconds|timeout|total"
    r"|amount|cents|rows|lines|pages|items|entries|port|status|offset|index|depth|capacity|tokens|dynamic)(?:_|$)",
    re.IGNORECASE,
)


def year_value(node: ast.AST | None, source: list[str] | None = None) -> int | None:
    """The year ``node`` writes, or ``None`` when it is no whole number written as a year.

    With ``source``, the number must also be spelled as four decimal digits there.
    """
    if not isinstance(node, ast.Constant) or type(node.value) is not int:
        return None
    if not YEAR_SOURCE.match(str(node.value)):
        return None
    if source is not None and not _spelled_in_decimal(node, source):
        return None
    return node.value


def _spelled_in_decimal(node: ast.expr, source: list[str]) -> bool:
    """Whether a number is written in plain decimal digits, not as hex, octal or with separators."""
    if node.lineno != node.end_lineno or node.end_col_offset is None:
        return False
    return source[node.lineno - 1][node.col_offset : node.end_col_offset].isdigit()


def bound_value(node: ast.AST | None, name: str) -> int | None:
    """The number ``node`` writes when, held under ``name``, it is a year bound.

    A number in the filing century counts under any year name; any other
    four-digit number counts only under a strict year name, since ``floor``
    and ``horizon`` also name sizes.
    """
    if not isinstance(node, ast.Constant) or type(node.value) is not int:
        return None
    text = str(node.value)
    if YEAR_SOURCE.match(text) and YEAR_NAME.search(name):
        return node.value
    if FOUR_DIGITS.match(text) and STRICT_YEAR_NAME.search(name):
        return node.value
    return None


def written_bound(node: ast.AST | None, name: str, source: list[str]) -> int | None:
    """The year bound ``node`` writes under ``name``, when it is spelled in decimal digits in ``source``."""
    if not isinstance(node, ast.expr) or not _spelled_in_decimal(node, source):
        return None
    return bound_value(node, name)


def node_name(node: ast.AST) -> str:
    """The name a node is known by: a variable, an attribute, a subscripted value or a string key."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return node_name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def year_named(node: ast.AST) -> bool:
    """Whether a node's name speaks of a year."""
    return bool(YEAR_NAME.search(node_name(node)))


def _measures(node: ast.AST) -> bool:
    """Whether a comparison operand counts or measures something, which a year never does."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and node_name(inner.func) == "len":
            return True
        if isinstance(inner, (ast.Name, ast.Attribute)) and _MEASURE_WORDS.search(node_name(inner)):
            return True
    return False


def year_compared(sides: Sequence[ast.expr], source: list[str]) -> bool:
    """Whether a comparison's operands compare a year or a year bound.

    A year of the filing century compared with nothing that counts or
    measures, a four-digit number compared with a year-named operand, or the
    four-digit cap the canonical year alias owns.
    """
    century = any(year_value(side, source) is not None for side in sides) and not any(_measures(side) for side in sides)
    return century or _named_compared(sides, source) or _capped(sides)


def _named_compared(sides: Sequence[ast.expr], source: list[str]) -> bool:
    names = [node_name(side) for side in sides if not isinstance(side, ast.Constant)]
    return any(written_bound(side, name, source) is not None for side in sides for name in names)


def _capped(sides: Iterable[ast.expr]) -> bool:
    return any(isinstance(side, ast.Constant) and side.value == FOUR_DIGIT_YEAR_LAST for side in sides)


def opaque_texts(node: ast.AST) -> Iterator[int]:
    """The texts a comparison operand writes directly or through nested literals, compared as written."""
    if isinstance(node, (ast.Constant, ast.JoinedStr)):
        yield id(node)
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for element in node.elts:
            yield from opaque_texts(element)
    elif isinstance(node, ast.Dict):
        for part in (*node.keys, *node.values):
            if part is not None:
                yield from opaque_texts(part)


def _call_keywords(*sides: ast.AST | None) -> Iterator[ast.keyword]:
    """Every keyword of every call written anywhere inside ``sides``, in walk order."""
    for side in sides:
        if side is None:
            continue
        for call in ast.walk(side):
            if isinstance(call, ast.Call):
                yield from call.keywords


def bound_detail(name: str, value: ast.AST | None, annotation: ast.AST | None, source: list[str]) -> str | None:
    """How a value bound to ``name``, or a field bound in it or its annotation, writes a year."""
    year = written_bound(value, name, source)
    if year is not None:
        return f"{name}={year}"
    for keyword in _call_keywords(annotation, value):
        if keyword.arg in _BOUND_KEYWORDS and written_bound(keyword.value, name, source) is not None:
            return f"{name}: {keyword.arg}={ast.unparse(keyword.value)}"
    return None


def keyword_bounds(node: ast.Call, source: list[str]) -> Iterator[tuple[ast.expr, str]]:
    """Each year a call is given under a year-named keyword, with its detail."""
    for keyword in node.keywords:
        year = None if keyword.arg is None else written_bound(keyword.value, keyword.arg, source)
        if year is not None:
            yield keyword.value, f"{keyword.arg}={year}"


def any_year(nodes: Iterable[ast.AST], source: list[str]) -> bool:
    """Whether any of ``nodes`` writes a year."""
    return any(year_value(node, source) is not None for node in nodes)


def year_argument(called: str, node: ast.Call, source: list[str]) -> bool:
    """Whether a call is given a year positionally under a year-speaking name or beside a period code."""
    return any_year(node.args, source) and (bool(_YEAR_CALL.search(called)) or _beside_period(node.args))


def _beside_period(arguments: Iterable[ast.expr]) -> bool:
    return any(
        isinstance(argument, ast.Constant) and isinstance(argument.value, str) and _PERIOD_CODE.match(argument.value)
        for argument in arguments
    )


def dated_from_year(node: ast.Call, source: list[str]) -> bool:
    """Whether a ``date`` or ``datetime`` call is given a written year first or as ``year=``."""
    return (bool(node.args) and year_value(node.args[0], source) is not None) or any(
        keyword.arg == "year" and year_value(keyword.value, source) is not None for keyword in node.keywords
    )


def parsed_year_texts(called: str, node: ast.Call) -> list[ast.expr]:
    """The text arguments holding a year that a parsing call turns into a date, an instant or a year."""
    if called not in _PARSE_CALLS and not _PARSE_NAME.search(called):
        return []
    return [
        argument
        for argument in (*node.args, *(keyword.value for keyword in node.keywords))
        if isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
        and YEAR_IN_TEXT.search(argument.value)
    ]


def text_finding(text: str, *, compared: bool, casilla_id: bool) -> tuple[str, str] | None:
    """The rule a string breaks and its detail, or ``None`` when it writes no coordinate where it stands."""
    if DATE_TEXT.match(text):
        return None if compared else ("date text", repr(text))
    if PERIOD_TEXT.match(text):
        return None if compared else ("period text", repr(text))
    if YEAR_TEXT.match(text):
        return None if casilla_id else ("year text", repr(text))
    if is_edition_id(text) or EDITION_IN_TEXT.search(text):
        return ("edition id", repr(text[:80]))
    return None


def template_rule(node: ast.JoinedStr) -> str | None:
    """The rule an f-string breaks by starting to write a date or a period, if any."""
    first = node.values[0] if node.values else None
    if not isinstance(first, ast.Constant):
        return None
    opening = str(first.value)
    if DATE_TEXT_START.match(opening):
        return "date text"
    if starts_period(opening, followed_by_value=len(node.values) > 1):
        return "period text"
    return None

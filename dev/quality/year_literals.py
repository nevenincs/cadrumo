"""Gate: no code in the repository names a filing year, an edition or a year bound.

Which years exist is the registry's to say, once: the supported-filing-years
declaration under the bundled authority sets the floor and horizon, each
modelo's authored editions say which revisions exist, and the canonical
temporal resolution projects every other year from the nearest edition.
Product code, developer tools, fixtures, tests and the desktop frontend read
those facts from the authority, its resolvers or a recording the backend
writes. A year written into code is a second declaration: it is locally
consistent the day it is written and wrong the day the horizon or an edition
moves, and nothing else notices.

What counts
-----------
A year is a whole number from 2000 to 2099 written in decimal digits, or a
string that is exactly such a number. Held under a strict year name (``year``,
``ejercicio``, ``anio``, ``año``), compared with one, or compared with
``9999``, any four-digit number is a year bound too, so ``LAST_YEAR = 2100``
and ``value > 9999`` restate the four-digit window the canonical alias in
``cadrumo.core.filing_year`` already owns. Every Python module and every TypeScript module the repository keeps
is read, found on the filesystem under its ignore rules, whatever its role:
production code, ``dev`` tooling, scripts, fixtures, stories, specs and tests
alike. Only the authority's own data root, ``src/cadrumo/_data``, is not
read, because it is where years are declared.

In Python, read through the syntax tree, each of these is a finding:

- ``year compared``: a year on either side of a comparison, unless an operand
  counts or measures (a ``len()`` call, or a name with a whole word such as
  ``bytes``, ``size``, ``count``, ``limit`` or ``total``);
- ``year bound``: a year assigned, annotated, defaulted, passed by keyword,
  given as a ``ge``/``le``/``gt``/``lt`` field bound or stored under a
  dictionary key whose name speaks of a year (``year``, ``ejercicio``,
  ``exercise``, ``anio``, ``floor``, ``horizon``, any ``*_year`` or
  ``year_*``), or held by an ``.year`` attribute;
- ``year argument``: a year passed positionally to a call whose name speaks of
  a year, edition, revision, period, filing, deadline, calendar or holiday, or
  next to a period code (``1T``, ``0A``, ``01`` to ``12``) in the same call;
- ``year arithmetic``: a year added to or subtracted from a year-named value;
- ``year list``: two or more years held in one tuple, list or set, a
  dictionary keyed by two or more years, or a year in a ``range``;
- ``year date``: a ``date`` or ``datetime`` built with a year, or text that
  holds a year passed to anything that parses it into a date, an instant or a
  year (``fromisoformat``, ``strptime``, ``isoparse``, ``to_datetime``,
  ``Timestamp``, or any call whose name pairs ``parse`` or ``from`` with
  ``date``, ``time``, ``instant``, ``day`` or ``iso``);
- ``date text``: a string that is exactly a date or an instant of the filing
  century (``2026-04-01``, ``2026-04``, ``2026-04-01T09:00:00+00:00``,
  ``01/04/2026``), or an f-string that starts writing one
  (``f"2026-04-{day}"``), anywhere except as an operand of a comparison or a
  ``case`` pattern. A frozen clock, a "today", a fixture anchor, a default, a
  keyword argument or a payload field is a year a parser or a slice later turns
  into a coordinate, so it is written from the authority instead;
- ``period text``: a string that is exactly a filing period of the filing
  century (``2026 1T``, ``2026-2T``, ``2026-0A``, ``2026Q1``, ``2026 03``,
  ``2026-EXT-1T``), or an f-string that starts writing one (``f"2026-{code}"``,
  ``f"2026 1T {label}"``), anywhere except as the compared side, exactly as
  ``date text``. A period is a filing coordinate like an edition id;
- ``year text``: a string that is exactly a year;
- ``edition id``: a string that is a revision id (``2026-y-siguientes``,
  ``2022-2025``, ``2024-desde-09-y-3t``) or that names one in a revision path.

In TypeScript, read with comments and string text blanked so prose and dates
written as text are not bounds, a year is any of ``18xx``, ``19xx``, ``2xxx``
or ``9999``, and each line is read for ``year compared``, ``year clamped``,
``year expected``, ``year constant`` (a year-named binding or object key set
to a year), ``year argument``, ``year date`` (``new Date`` or ``Date.UTC``
from a year of the filing century) and ``edition worked out``. Read again with
only comments blanked, a string that is exactly a year is ``year text``, a
revision id is ``edition id``, text holding a year opened straight into
``Date.parse``, ``new Date``, ``Temporal.*.from``, ``dayjs``, ``moment``,
``DateTime.fromISO``, ``parseISO`` or a ``parse``/``from`` date helper is
``year date``, and any other string or template that is exactly, or starts
writing, a date of the filing century is ``date text``, and one that is
exactly, or starts writing, a filing period is ``period text``, unless it is
compared:
it sits inside an expectation's argument (``toBe``, ``toEqual``,
``toStrictEqual``, ``toContain``, ``toMatchObject``, ``toHaveText``,
``toHaveBeenCalledWith`` and their kin, across lines), beside ``===``,
``!==``, ``==`` or ``!=``, or after ``case``.

What may stay, and why
----------------------
- Prose: comments and docstrings name years in sentences; a sentence is read
  by people, never by a resolver.
- A date, instant or filing period compared as written: the expected side of a comparison,
  an element of a literal tuple, list, set or dictionary that is such an
  operand, a ``case`` pattern, or a TypeScript expectation's argument. The
  text is the output under test, read as opaque characters; it never becomes a
  date in code, and a wrong one fails the comparison instead of diverging.
- Text that holds a year among other characters and is never parsed: a legal
  citation (``Ley 58/2003``, ``Orden HAC/1417/2023``, ``BOE-A-2023-12345``), a
  sentence, a URL, a schema or migration stamp. Such text is not a coordinate
  the code computes with; the same text passed to a parser is a ``year date``.
- A number in the year range that is no year: a count, a size or an amount,
  which the rules above never reach because they read the name or call the
  number stands under.
- A number outside 2000 to 2099 that no year name or year comparison holds,
  such as the 1970 and 1980 epochs: no filing year can be one of them.
- A number written as hex, octal or with digit separators, such as a Unicode
  codepoint range: no year is spelled that way.

There is no allowance list, baseline or exemption by file. What the rules do
not cover is stated below; it is never a reason to leave a year standing.

How to satisfy the gate
-----------------------
Read the year from the authority. Production code takes it from the operation's
pinned authority (``supported_filing_years()``, ``revision_temporal_resolution``,
the served edition fields). A Python test takes it from
``cadrumo.domain.calculations.registry.tests.authored_editions``, which reads
the published authority: the floor and horizon (``filing_year_envelope()``),
the newest authored edition,
the first projected exercise, the exercises an edition governs. A date is
built from that year (``date(year, 3, 1)``), and a frozen clock from the
horizon (``datetime(filing_year_envelope().horizon, 4, 1, 9, tzinfo=UTC)``).
The frontend reads the backend's recordings and builds a date or "today" from
the served year authority (``servedYearAuthority.ts``). A year that must sit
at, inside or outside the envelope is written from the floor or horizon, never
as a number.

What this gate cannot see
-------------------------
- A year held in text other than an exact year, date, instant or edition id
  and passed to no parser by name: a date inside a JSON blob, a CSV row or a
  sentence that a resolver reads later.
- A date compared in a TypeScript expectation that is reached through a
  helper rather than opened on the expectation itself.
- A year computed from other numbers, such as ``2000 + 25``, when neither
  operand is year-named.
- A year passed positionally to a helper whose name says nothing of a year or
  a period, with no period code beside it.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_LAST
from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

#: A year is written as these four digits. The shape is matched on the source
#: text, so ``0x2027``, ``2_027`` and ``2027.0`` are not years.
YEAR_SOURCE: Final[re.Pattern[str]] = re.compile(r"^20\d\d$")

#: Any four-digit number. Held under a year name or compared with a year-named
#: value it is a year bound, even outside the filing century (``9999``, ``1900``).
FOUR_DIGITS: Final[re.Pattern[str]] = re.compile(r"^[1-9]\d\d\d$")

PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx", ".mts", ".cts"})

#: The bundled authority's data root: the one place a year is declared.
AUTHORITY_DATA_ROOTS: Final[tuple[str, ...]] = ("src/cadrumo/_data/",)

_YEAR_WORDS = r"years?|yr|ejercicios?|exercises?|anio|año|floor|horizon"
YEAR_NAME: Final[re.Pattern[str]] = re.compile(rf"(?:^|_)(?:{_YEAR_WORDS})(?:_|$)", re.IGNORECASE)
_STRICT_YEAR_WORDS = r"years?|ejercicios?|anio|año"
STRICT_YEAR_NAME: Final[re.Pattern[str]] = re.compile(rf"(?:^|_)(?:{_STRICT_YEAR_WORDS})(?:_|$)", re.IGNORECASE)
_YEAR_CALL = re.compile(
    r"year|ejercicio|exercise|edition|revision|period|filing|deadline|plazo|calendar|holiday|festivo|envelope",
    re.IGNORECASE,
)
_PERIOD_CODE = re.compile(r"^(?:[1-4]T|0A|0[1-9]|1[0-2]|[1-4]P)$")
_YEAR_TEXT = re.compile(r"^20\d\d$")
_ISO_DATE_TEXT = re.compile(r"^20\d\d-\d\d-\d\d$")
_DAY = r"(?:0[1-9]|[12]\d|3[01])"
_MONTH = r"(?:0[1-9]|1[0-2])"
#: Text that is exactly a date or an instant of the filing century: an ISO
#: year-month, date or timestamp with or without seconds, fraction and offset,
#: or a day-first or slashed date.
DATE_TEXT: Final[re.Pattern[str]] = re.compile(
    rf"^(?:20\d\d-{_MONTH}(?:-{_DAY}(?:[T ](?:[01]\d|2[0-3])(?::[0-5]\d(?::[0-5]\d(?:[.,]\d+)?)?)?"
    rf"(?:Z|[+-]\d\d(?::?\d\d)?)?)?)?"
    rf"|{_DAY}[/.-]{_MONTH}[/.-]20\d\d|20\d\d/{_MONTH}/{_DAY})$"
)
#: The start of an f-string that writes a date of the filing century, such as ``f"2026-04-{day}"``.
_DATE_TEXT_START = re.compile(rf"^20\d\d-{_MONTH}(?:-|$)")
_PERIOD_CODE_TEXT = r"(?:[1-4][TP]|0A|Q[1-4]|T[1-4]|EXT-[1-4]T|EVENT-\d+)"
#: Text that is exactly a filing period of the filing century: a year and a period
#: code (``1T``-``4T``, ``1P``-``4P``, ``0A``, ``EXT-1T``, ``EVENT-3``, and the
#: refused calendar spellings ``Q1``/``T1``) joined directly or by a dash, space,
#: underscore, colon, slash or dot, or a year and a month joined by a space,
#: underscore, colon or slash (``2026 03``; ``2026-03`` is already date text).
PERIOD_TEXT: Final[re.Pattern[str]] = re.compile(
    rf"^20\d\d(?:[-_ :/.]?{_PERIOD_CODE_TEXT}|[_ :/]{_MONTH})$", re.IGNORECASE
)
#: The start of a template that writes a period: a year and a period code, or a
#: year with at most a separator before the first interpolation (``f"2026-{code}"``).
_PERIOD_TEXT_START = re.compile(rf"^20\d\d[-_ :/.]?{_PERIOD_CODE_TEXT}(?![0-9A-Za-z])", re.IGNORECASE)
_YEAR_BEFORE_VALUE = re.compile(r"^20\d\d[-_ :/.]?$")
_YEAR_IN_TEXT = re.compile(r"(?<!\d)20\d\d(?!\d)")
#: Calls that turn text into a date, an instant or a year.
_PARSE_CALLS = frozenset({"fromisoformat", "strptime", "isoparse", "to_datetime", "Timestamp", "datetime64"})
_PARSE_NAME = re.compile(
    r"(?:parse|from)_?\w*?(?:date|time|instant|day|iso)|(?:date|time|instant|day|iso)\w*?_?parse", re.IGNORECASE
)
_EDITION_ID = re.compile(r"^20\d\d(?:-[0-9a-z]+)+$")
_EDITION_IN_TEXT = re.compile(
    r"(?:revisions[/\\]20\d\d(?:-[0-9a-z]+)*)|\b20\d\d(?:-[0-9a-z]+)*-(?:y-siguientes|hasta-[0-9a-z-]+|desde-[0-9a-z-]+)\b"
)
_DATE_CALLS = frozenset({"date", "datetime"})
_BOUND_KEYWORDS = frozenset({"ge", "le", "gt", "lt"})
_AMOUNT_CALLS = frozenset({"Decimal", "Money", "Fraction"})


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


def is_edition_id(text: str) -> bool:
    """Whether ``text`` is a revision id: a year with a range, window or edition word after it."""
    if _ISO_DATE_TEXT.match(text):
        return False
    if not _EDITION_ID.match(text):
        return False
    rest = text[4:]
    return any(char.isalpha() for char in rest) or re.match(r"^-20\d\d$", rest) is not None


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _year_named(node: ast.AST) -> bool:
    return bool(YEAR_NAME.search(_name(node)))


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One year written into code."""

    path: str
    line: int
    rule: str
    text: str


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.found: list[tuple[int, str, str]] = []
        self._lines = source.splitlines()
        self._prose: set[int] = set()
        self._amounts: set[int] = set()
        self._compared: set[int] = set()
        self._parsed: set[int] = set()

    def _year(self, node: ast.AST | None) -> int | None:
        return year_value(node, self._lines)

    def _bound_value(self, node: ast.AST | None, name: str) -> int | None:
        if not isinstance(node, ast.expr) or not _spelled_in_decimal(node, self._lines):
            return None
        return bound_value(node, name)

    def _report(self, node: ast.AST, rule: str, detail: object) -> None:
        self.found.append((getattr(node, "lineno", 0), rule, str(detail)))

    def _mark_docstring(self, body: list[ast.stmt]) -> None:
        first = body[0] if body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            self._prose.add(id(first.value))

    @override
    def visit_Module(self, node: ast.Module) -> None:
        self._mark_docstring(node.body)
        self.generic_visit(node)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark_docstring(node.body)
        self.generic_visit(node)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._mark_docstring(node.body)
        arguments = node.args
        positional = [*arguments.posonlyargs, *arguments.args]
        defaulted: list[tuple[ast.arg, ast.expr | None]] = [
            *zip(positional[len(positional) - len(arguments.defaults) :], arguments.defaults, strict=True),
            *zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True),
        ]
        for argument, default in defaulted:
            year = self._bound_value(default, argument.arg)
            if year is not None and default is not None:
                self._report(default, "year bound", f"{argument.arg}={year}")
        self.generic_visit(node)

    @override
    def visit_Compare(self, node: ast.Compare) -> None:
        sides = (node.left, *node.comparators)
        century = any(self._year(side) is not None for side in sides) and not any(_measures(side) for side in sides)
        capped = any(isinstance(side, ast.Constant) and side.value == FOUR_DIGIT_YEAR_LAST for side in sides)
        names = [_name(side) for side in sides if not isinstance(side, ast.Constant)]
        named = any(self._bound_value(side, name) is not None for side in sides for name in names)
        if century or named or capped:
            self._report(node, "year compared", ast.unparse(node)[:80])
        for side in sides:
            self._compared.update(_opaque_texts(side))
        self.generic_visit(node)

    @override
    def visit_MatchValue(self, node: ast.MatchValue) -> None:
        self._compared.update(_opaque_texts(node.value))
        self.generic_visit(node)

    def _bound(
        self, targets: Iterable[ast.AST], value: ast.AST | None, node: ast.AST, annotation: ast.AST | None = None
    ) -> None:
        for target in targets:
            name = _name(target)
            year = self._bound_value(value, name)
            if year is not None:
                self._report(node, "year bound", f"{name}={year}")
                return
            for side in (annotation, value):
                for call in ast.walk(side) if side is not None else ():
                    if not isinstance(call, ast.Call):
                        continue
                    for keyword in call.keywords:
                        if keyword.arg in _BOUND_KEYWORDS and self._bound_value(keyword.value, name) is not None:
                            self._report(node, "year bound", f"{name}: {keyword.arg}={ast.unparse(keyword.value)}")
                            return

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        self._bound(node.targets, node.value, node)
        self.generic_visit(node)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._bound((node.target,), node.value, node, node.annotation)
        self.generic_visit(node)

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._bound((node.target,), node.value, node)
        self.generic_visit(node)

    @override
    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            year = self._bound_value(value, _name(key))
            if year is not None:
                self._report(value, "year bound", f"{_name(key)}={year}")
        if sum(1 for key in node.keys if self._year(key) is not None) >= 2:
            self._report(node, "year list", "dictionary keyed by years")
        self.generic_visit(node)

    @override
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Add, ast.Sub)):
            for year, other in ((node.left, node.right), (node.right, node.left)):
                if self._year(year) is not None and _year_named(other):
                    self._report(node, "year arithmetic", ast.unparse(node)[:80])
                    break
        self.generic_visit(node)

    def _sequence(self, node: ast.Tuple | ast.List | ast.Set) -> None:
        if sum(1 for element in node.elts if self._year(element) is not None) >= 2:
            self._report(node, "year list", ast.unparse(node)[:80])
        self.generic_visit(node)

    @override
    def visit_Tuple(self, node: ast.Tuple) -> None:
        self._sequence(node)

    @override
    def visit_List(self, node: ast.List) -> None:
        self._sequence(node)

    @override
    def visit_Set(self, node: ast.Set) -> None:
        self._sequence(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        called = _name(node.func)
        if called in _AMOUNT_CALLS:
            # An amount written as text, such as a Decimal of two thousand, is money, not a year.
            self._amounts.update(id(argument) for argument in node.args)
        if called == "range" and any(self._year(argument) is not None for argument in node.args):
            self._report(node, "year list", ast.unparse(node)[:80])
        elif self._builds_dated(called, node):
            self._report(node, "year date", ast.unparse(node)[:80])
        else:
            for keyword in node.keywords:
                year = None if keyword.arg is None else self._bound_value(keyword.value, keyword.arg)
                if year is not None:
                    self._report(keyword.value, "year bound", f"{keyword.arg}={year}")
            beside_period = any(
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and _PERIOD_CODE.match(argument.value)
                for argument in node.args
            )
            if any(self._year(argument) is not None for argument in node.args) and (
                _YEAR_CALL.search(called) or beside_period
            ):
                self._report(node, "year argument", ast.unparse(node)[:80])
        self.generic_visit(node)

    def _builds_dated(self, called: str, node: ast.Call) -> bool:
        """Whether a call builds a date or datetime from a written year."""
        if called in _DATE_CALLS:
            return (bool(node.args) and self._year(node.args[0]) is not None) or any(
                keyword.arg == "year" and self._year(keyword.value) is not None for keyword in node.keywords
            )
        if called not in _PARSE_CALLS and not _PARSE_NAME.search(called):
            return False
        written = [
            argument
            for argument in (*node.args, *(keyword.value for keyword in node.keywords))
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and _YEAR_IN_TEXT.search(argument.value)
        ]
        self._parsed.update(id(argument) for argument in written)
        return bool(written)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._prose or id(node) in self._amounts or not isinstance(node.value, str):
            return
        text = node.value
        if id(node) in self._parsed:
            return
        if DATE_TEXT.match(text):
            if id(node) not in self._compared:
                self._report(node, "date text", repr(text))
        elif PERIOD_TEXT.match(text):
            if id(node) not in self._compared:
                self._report(node, "period text", repr(text))
        elif _YEAR_TEXT.match(text):
            self._report(node, "year text", repr(text))
        elif is_edition_id(text) or _EDITION_IN_TEXT.search(text):
            self._report(node, "edition id", repr(text[:80]))

    @override
    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        literal = "".join(str(part.value) for part in node.values if isinstance(part, ast.Constant))
        first = node.values[0] if node.values else None
        if (
            isinstance(first, ast.Constant)
            and _DATE_TEXT_START.match(str(first.value))
            and id(node) not in self._compared | self._parsed
        ):
            self._report(node, "date text", repr(literal[:80]))
        elif (
            isinstance(first, ast.Constant)
            and _starts_period(str(first.value), followed_by_value=len(node.values) > 1)
            and id(node) not in self._compared | self._parsed
        ):
            self._report(node, "period text", repr(literal[:80]))
        elif _EDITION_IN_TEXT.search(literal):
            self._report(node, "edition id", repr(literal[:80]))
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                self.visit(part)


def _starts_period(literal: str, *, followed_by_value: bool) -> bool:
    """Whether a template's first literal part starts writing a filing period."""
    return bool(_PERIOD_TEXT_START.match(literal)) or (followed_by_value and bool(_YEAR_BEFORE_VALUE.match(literal)))


def _opaque_texts(node: ast.AST) -> Iterator[int]:
    """The texts a comparison operand writes directly or through nested literals, compared as written."""
    if isinstance(node, (ast.Constant, ast.JoinedStr)):
        yield id(node)
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for element in node.elts:
            yield from _opaque_texts(element)
    elif isinstance(node, ast.Dict):
        for part in (*node.keys, *node.values):
            if part is not None:
                yield from _opaque_texts(part)


def _measures(node: ast.AST) -> bool:
    """Whether a comparison operand counts or measures something, which a year never does."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and _name(inner.func) == "len":
            return True
        if isinstance(inner, (ast.Name, ast.Attribute)) and _MEASURE_WORDS.search(_name(inner)):
            return True
    return False


def python_findings(source: str, path: str) -> list[Finding]:
    """Every year written into one Python source text."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Finding(path=path, line=error.lineno or 0, rule="unreadable", text=str(error.msg))]
    visitor = _PythonVisitor(source)
    visitor.visit(tree)
    unique = dict.fromkeys(visitor.found)
    return sorted(Finding(path=path, line=line, rule=rule, text=text) for line, rule, text in unique)


# TypeScript ------------------------------------------------------------------

#: A year bound in TypeScript: the filing century, the nineteenth- and
#: twentieth-century floors a year field once spelled, and the four-digit cap.
_TS_YEAR = r"(?<![\w.])(?:1[89]\d\d|2\d\d\d|9999)(?![\w.])"
#: A date's year: only the filing century, since epochs such as 1970 build no coordinate.
_TS_CENTURY = r"(?<![\w.])20\d\d(?![\w.])"
_TS_COMPARE = r"(?:[<>]=?|[!=]==?)"
_TS_COUNT_OPERAND = re.compile(
    rf"\.(?:length|size)\s*{_TS_COMPARE}\s*\(?\s*{_TS_YEAR}|{_TS_YEAR}\s*{_TS_COMPARE}\s*[\w.?!]*\.(?:length|size)\b"
)
_TS_COUNT_EXPECTED = re.compile(r"\.(?:length|size|count\(\))\s*\)\s*\.(?:not\.)?to(?:Be|Equal|StrictEqual)\(")
_TS_RULES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "year compared",
        re.compile(rf"{_TS_COMPARE}\s*\(?\s*{_TS_YEAR}|{_TS_YEAR}\s*\)?\s*(?:[<>]=?(?![/>])|[!=]==?)"),
    ),
    ("year clamped", re.compile(rf"Math\.(?:min|max)\([^()]*{_TS_YEAR}")),
    (
        "year expected",
        re.compile(
            rf"\.(?:not\.)?(?:toBe|toEqual|toStrictEqual)\(\s*{_TS_YEAR}\s*\)"
            rf"|(?:[Yy]ear|ejercicio)[^;]*\.(?:not\.)?toBe(?:Greater|Less)Than(?:OrEqual)?\(\s*{_TS_YEAR}\s*\)"
        ),
    ),
    (
        "year constant",
        re.compile(
            rf"\b(?:\w*(?:YEAR|Year|year|ejercicio|Ejercicio)\w*|Y)"
            rf"\s*(?::\s*[\w<>\[\]| ]+?)?\s*[=:](?![=>])\s*{_TS_YEAR}"
        ),
    ),
    (
        "year argument",
        re.compile(
            rf"\b(?:served\w*|\w*(?:[Yy]ear|[Cc]laim|[Hh]andoff|[Ee]dition|[Pp]eriod)\w*)\s*\((?:[^()]*,\s*)?{_TS_YEAR}\s*[,)]"
        ),
    ),
    (
        "year date",
        re.compile(rf"\bnew\s+Date\(\s*{_TS_CENTURY}\s*,|\bDate\.UTC\(\s*{_TS_CENTURY}\s*,"),
    ),
    (
        "edition worked out",
        re.compile(
            rf"\b(?:authored_filing_year|projected|revision_id)\s*:\s*[^,}}\n]*(?:{_TS_COMPARE}|Math\.|[-+*/%]\s*[\w(])"
            rf"|\bauthored_filing_year\s*(?:{_TS_COMPARE}|[-+*/%](?!=))"
            rf"|(?:{_TS_COMPARE}|[-+*/%])\s*[\w.?!]*\bauthored_filing_year\b"
        ),
    ),
)
_TS_STRING = re.compile(r"""(?P<quote>["'`])(?P<body>(?:\\.|(?!(?P=quote))[^\\\n])*)(?P=quote)""")
#: A call that turns the text opened right after it into a date, an instant or a year.
_TS_PARSER_OPEN = re.compile(
    r"(?:\bDate\.parse|\bnew\s+Date|\bTemporal\.\w+\.from|\bdayjs|\bmoment|\bDateTime\.fromISO|\bparseISO"
    r"|\b\w*(?:[Pp]arse|[Ff]rom)\w*(?:Date|Time|Instant|Day|Iso|ISO)\w*)\s*\(\s*$"
)
#: An expectation whose argument is the expected value, written as it is compared.
_TS_EXPECT_OPEN = re.compile(
    r"\.(?:not\.)?(?:toBe|toEqual|toStrictEqual|toContain|toContainEqual|toMatchObject|toHaveText|toHaveValue"
    r"|toHaveAttribute|toHaveProperty|toMatch|toHaveBeenCalledWith|toHaveBeenLastCalledWith|toHaveBeenNthCalledWith)$"
)
_TS_COMPARED_BEFORE = re.compile(r"(?:[!=]==?|\bcase)\s*$")
_TS_COMPARED_AFTER = re.compile(r"^\s*[!=]==?")


def _expected_quotes(blanked: list[str]) -> set[tuple[int, int]]:
    """The line and column of every quote that opens text inside an expectation's argument."""
    inside: set[tuple[int, int]] = set()
    stack: list[bool] = []
    for number, line in enumerate(blanked, start=1):
        for column, char in enumerate(line):
            if char == "(":
                stack.append(_TS_EXPECT_OPEN.search(line[:column]) is not None)
            elif char == ")" and stack:
                stack.pop()
            elif char in "\"'`" and any(stack):
                inside.add((number, column))
    return inside


def blank_text(source: str) -> str:
    """Blank comments and string text, keeping template expressions and every newline."""
    out: list[str] = []
    length = len(source)

    def blank(chunk: str) -> str:
        return re.sub(r"[^\n]", " ", chunk)

    def template(start: int) -> int:
        at = start
        while at < length and source[at] != "`":
            if source[at] == "\\":
                out.append(blank(source[at : at + 2]))
                at += 2
                continue
            if source.startswith("${", at):
                out.append("${")
                at = code(at + 2, closing="}")
                out.append("}")
                at += 1
                continue
            out.append(blank(source[at]))
            at += 1
        out.append("`")
        return at + 1

    def code(start: int, closing: str | None) -> int:
        at = start
        depth = 0
        while at < length:
            char = source[at]
            if closing is not None and depth == 0 and char == closing:
                return at
            if source.startswith("//", at):
                end = source.find("\n", at)
                end = length if end < 0 else end
                out.append(blank(source[at:end]))
                at = end
                continue
            if source.startswith("/*", at):
                end = source.find("*/", at + 2)
                end = length if end < 0 else end + 2
                out.append(blank(source[at:end]))
                at = end
                continue
            if char in "\"'":
                end = at + 1
                while end < length and source[end] != char and source[end] != "\n":
                    end += 2 if source[end] == "\\" else 1
                if end < length and source[end] == char:
                    out.append(char + blank(source[at + 1 : end]) + char)
                    at = end + 1
                else:
                    # An unpaired quote, such as a JSX apostrophe, ends at the line and keeps its newline.
                    out.append(blank(source[at:end]))
                    at = end
                continue
            if char == "`":
                out.append("`")
                at = template(at + 1)
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            out.append(char)
            at += 1
        return at

    index = 0
    while index < length:
        index = code(index, closing=None)
    return "".join(out)


def _comment_free(source: str) -> str:
    """Blank comments only, keeping string text, so string coordinates stay readable."""
    return re.sub(
        r"/\*.*?\*/|(?<![:\"'\\])//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match.group()), source, flags=re.S
    )


def _ts_coordinate_text(body: str, *, template: bool) -> str | None:
    """The rule a string or template body breaks by writing a date or a period, if any."""
    if DATE_TEXT.match(body) or (template and _DATE_TEXT_START.match(body)):
        return "date text"
    if PERIOD_TEXT.match(body):
        return "period text"
    if template:
        literal, _, rest = body.partition("${")
        if _starts_period(literal, followed_by_value=bool(rest)):
            return "period text"
    return None


def typescript_findings(source: str, path: str) -> list[Finding]:
    """Every year bound, edition computation and year coordinate in one TypeScript source text."""
    found: list[Finding] = []
    blanked = blank_text(source).splitlines()
    for number, line in enumerate(blanked, start=1):
        for rule, pattern in _TS_RULES:
            if pattern.search(line) is None:
                continue
            if (
                rule == "year compared"
                and _TS_COUNT_OPERAND.search(line)
                and not pattern.search(_TS_COUNT_OPERAND.sub("", line))
            ):
                continue
            if rule == "year expected" and _TS_COUNT_EXPECTED.search(line):
                continue
            found.append(Finding(path=path, line=number, rule=rule, text=line.strip()))
            break
    expected = _expected_quotes(blanked)
    original = _comment_free(source).splitlines()
    for number, line in enumerate(original, start=1):
        for match in _TS_STRING.finditer(line):
            body = match.group("body")
            if _TS_PARSER_OPEN.search(line[: match.start()]) and _YEAR_IN_TEXT.search(body):
                found.append(Finding(path=path, line=number, rule="year date", text=line.strip()[:80]))
            elif (kind := _ts_coordinate_text(body, template=match.group("quote") == "`")) is not None:
                compared = (
                    (number, match.start()) in expected
                    or _TS_COMPARED_BEFORE.search(line[: match.start()])
                    or _TS_COMPARED_AFTER.match(line[match.end() :])
                )
                if not compared:
                    found.append(Finding(path=path, line=number, rule=kind, text=match.group()[:80]))
            elif _YEAR_TEXT.match(body):
                found.append(Finding(path=path, line=number, rule="year text", text=match.group()))
            elif is_edition_id(body) or _EDITION_IN_TEXT.search(body):
                found.append(Finding(path=path, line=number, rule="edition id", text=match.group()[:80]))
    return sorted(set(found))


# The walk --------------------------------------------------------------------


def governed_sources(root: Path = REPO_ROOT) -> list[str]:
    """Every Python and TypeScript module under ``root`` outside the authority's data root."""
    return [
        relative
        for relative in repository_files(root)
        if Path(relative).suffix in PYTHON_SUFFIXES | TYPESCRIPT_SUFFIXES
        and not relative.startswith(AUTHORITY_DATA_ROOTS)
    ]


def findings_for(relative: str, source: str) -> list[Finding]:
    """The findings of one module, read by the rules of its language."""
    if Path(relative).suffix in TYPESCRIPT_SUFFIXES:
        return typescript_findings(source, relative)
    return python_findings(source, relative)


def scan(root: Path = REPO_ROOT) -> Iterator[Finding]:
    """Every finding under ``root``, module by module."""
    for relative in governed_sources(root):
        yield from findings_for(relative, (root / relative).read_text(encoding="utf-8", errors="replace"))


def main(argv: list[str] | None = None, root: Path = REPO_ROOT) -> int:
    """Print every year written into code and return the process exit status.

    ``--summary`` prints counts by rule and top-level area instead of each
    finding. A walk that reads no module is refused rather than reported
    clean, because an empty population means the walk did not read the tree.
    """
    arguments = sys.argv[1:] if argv is None else argv
    if not governed_sources(root):
        print(f"found no Python or TypeScript module under {root}, so nothing was read", file=sys.stderr)
        return 1
    found = list(scan(root))
    if "--summary" in arguments:
        by_rule: dict[str, int] = {}
        for finding in found:
            by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
        for rule, count in sorted(by_rule.items(), key=lambda item: -item[1]):
            print(f"{rule}: {count}")
    else:
        for finding in found:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.text}")
    if found:
        files = len({finding.path for finding in found})
        print(f"{len(found)} years written into code in {files} modules; read them from the authority")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

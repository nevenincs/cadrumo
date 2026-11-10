"""The year gate's TypeScript reader: year bounds, edition computations and year coordinates by line.

The rules it applies, and what they admit, are stated by the gate in
``dev.quality.year_literals``.
"""

from __future__ import annotations

import re
from typing import Final

from .typescript_text_blanking import blank_text, comment_free
from .year_literal_shapes import (
    DATE_TEXT,
    DATE_TEXT_START,
    EDITION_IN_TEXT,
    PERIOD_TEXT,
    YEAR_IN_TEXT,
    YEAR_TEXT,
    Finding,
    is_edition_id,
    starts_period,
)

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


def _ts_coordinate_text(body: str, *, template: bool) -> str | None:
    """The rule a string or template body breaks by writing a date or a period, if any."""
    if DATE_TEXT.match(body) or (template and DATE_TEXT_START.match(body)):
        return "date text"
    if PERIOD_TEXT.match(body):
        return "period text"
    if template:
        literal, _, rest = body.partition("${")
        if starts_period(literal, followed_by_value=bool(rest)):
            return "period text"
    return None


def _count_excused(rule: str, pattern: re.Pattern[str], line: str) -> bool:
    """Whether a line breaks ``rule`` only through a year-sized count, such as a ``.length`` compared."""
    if rule == "year compared":
        return bool(_TS_COUNT_OPERAND.search(line)) and not pattern.search(_TS_COUNT_OPERAND.sub("", line))
    return rule == "year expected" and bool(_TS_COUNT_EXPECTED.search(line))


def _line_rule(line: str) -> str | None:
    """The first rule a blanked line breaks, if any."""
    for rule, pattern in _TS_RULES:
        if pattern.search(line) is not None and not _count_excused(rule, pattern, line):
            return rule
    return None


def _string_finding(
    path: str, number: int, line: str, match: re.Match[str], expected: set[tuple[int, int]]
) -> Finding | None:
    """The finding a string or template written on a comment-free line makes, if any."""
    body = match.group("body")
    if _TS_PARSER_OPEN.search(line[: match.start()]) and YEAR_IN_TEXT.search(body):
        return Finding(path=path, line=number, rule="year date", text=line.strip()[:80])
    kind = _ts_coordinate_text(body, template=match.group("quote") == "`")
    if kind is not None:
        compared = (
            (number, match.start()) in expected
            or _TS_COMPARED_BEFORE.search(line[: match.start()])
            or _TS_COMPARED_AFTER.match(line[match.end() :])
        )
        return None if compared else Finding(path=path, line=number, rule=kind, text=match.group()[:80])
    if YEAR_TEXT.match(body):
        return Finding(path=path, line=number, rule="year text", text=match.group())
    if is_edition_id(body) or EDITION_IN_TEXT.search(body):
        return Finding(path=path, line=number, rule="edition id", text=match.group()[:80])
    return None


def typescript_findings(source: str, path: str) -> list[Finding]:
    """Every year bound, edition computation and year coordinate in one TypeScript source text."""
    blanked = blank_text(source).splitlines()
    found = [
        Finding(path=path, line=number, rule=rule, text=line.strip())
        for number, line in enumerate(blanked, start=1)
        if (rule := _line_rule(line)) is not None
    ]
    expected = _expected_quotes(blanked)
    for number, line in enumerate(comment_free(source).splitlines(), start=1):
        for match in _TS_STRING.finditer(line):
            finding = _string_finding(path, number, line, match, expected)
            if finding is not None:
                found.append(finding)
    return sorted(set(found))

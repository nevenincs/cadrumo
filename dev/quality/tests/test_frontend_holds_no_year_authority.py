"""Gate: the desktop frontend holds no year bound, no scenario year and works out no edition.

The registry declares the supported filing years once, and the backend resolves
each tax year's edition, whether that edition is projected, and the bounds a
year field admits. The frontend renders what the backend serves, its scenario
fixtures, stories and tests included: they read those facts from the recordings
the backend's own resolvers write, and a scenario's year from the scenario's
own date or served data. A year written into frontend source as a bound, or an edition
worked out there, is a second declaration that drifts the day the horizon or an
edition moves, and nothing else notices.

What counts
-----------
Source is read with its comments and the text of its strings blanked, keeping
the expressions inside template literals, so a date written in a string or a
sentence is not a bound. In what is left, each of these is a finding:

- a four-digit year compared with anything (``<``, ``<=``, ``>``, ``>=``,
  ``==``, ``===``, ``!=``, ``!==``), except a comparison of a ``.length`` or
  ``.size``, which counts characters or entries, not years;
- a four-digit year inside a ``Math.min`` or ``Math.max`` clamp;
- a four-digit year a test expects to equal (``toBe``, ``toEqual``,
  ``toStrictEqual``), except of a ``.length``, ``.size`` or ``.count()``; and
  one an ordering matcher (``toBeGreaterThan`` and its kin) holds against on a
  line that names a year, since scroll offsets and counts share the digits;
- a name containing ``YEAR``, ``Year``, ``year`` or ``ejercicio``, or the name
  ``Y``, assigned or defaulted to a four-digit year;
- a four-digit year passed to a ``served`` lookup, or to a call whose name
  speaks of a year, claim, handoff, edition or period;
- an edition field (``authored_filing_year``, ``projected``, ``revision_id``)
  set from a comparison, ``Math`` or arithmetic, or ``authored_filing_year``
  compared or computed with.

An edition stated as a value is data, not logic, and is not counted here.

How to satisfy the gate
-----------------------
Read the fact from the backend: an operation's result, or for a scenario
fixture the recording the backend writes for it. A scenario year that must sit
inside, at the edge of or outside the support envelope is expressed from the
recorded floor and horizon; a scenario's own year is read from its date. There
is no allowance list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts"})

_YEAR = r"(?<![\w.])(?:1[89]\d\d|2\d\d\d|9999)(?![\w.])"
_COMPARE = r"(?:[<>]=?|[!=]==?)"
_COUNT_OPERAND = re.compile(
    rf"\.(?:length|size)\s*{_COMPARE}\s*\(?\s*{_YEAR}|{_YEAR}\s*{_COMPARE}\s*[\w.?!]*\.(?:length|size)\b"
)
_COUNT_EXPECTED = re.compile(r"\.(?:length|size|count\(\))\s*\)\s*\.(?:not\.)?to(?:Be|Equal|StrictEqual)\(")

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "year compared",
        re.compile(rf"{_COMPARE}\s*\(?\s*{_YEAR}|{_YEAR}\s*\)?\s*(?:[<>]=?(?![/>])|[!=]==?)"),
    ),
    ("year clamped", re.compile(rf"Math\.(?:min|max)\([^()]*{_YEAR}")),
    (
        "year expected",
        re.compile(
            rf"\.(?:not\.)?(?:toBe|toEqual|toStrictEqual)\(\s*{_YEAR}\s*\)"
            rf"|(?:[Yy]ear|ejercicio)[^;]*\.(?:not\.)?toBe(?:Greater|Less)Than(?:OrEqual)?\(\s*{_YEAR}\s*\)"
        ),
    ),
    (
        "year constant",
        re.compile(rf"\b(?:\w*(?:YEAR|Year|year|ejercicio)\w*|Y)\s*(?::\s*[\w<>\[\]| ]+?)?\s*=(?![=>])\s*{_YEAR}"),
    ),
    (
        "year argument",
        re.compile(
            rf"\b(?:served\w*|\w*(?:[Yy]ear|[Cc]laim|[Hh]andoff|[Ee]dition|[Pp]eriod)\w*)\s*\((?:[^()]*,\s*)?{_YEAR}\s*[,)]"
        ),
    ),
    (
        "edition worked out",
        re.compile(
            rf"\b(?:authored_filing_year|projected|revision_id)\s*:\s*[^,}}\n]*(?:{_COMPARE}|Math\.|[-+*/%]\s*[\w(])"
            rf"|\bauthored_filing_year\s*(?:{_COMPARE}|[-+*/%](?!=))"
            rf"|(?:{_COMPARE}|[-+*/%])\s*[\w.?!]*\bauthored_filing_year\b"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One year bound or edition computation in frontend source."""

    path: str
    line: int
    rule: str
    text: str


def blank_text(source: str) -> str:
    """Blank comments and string text, keeping template expressions and every newline."""
    out: list[str] = []
    index = 0
    length = len(source)

    def blank(chunk: str) -> str:
        return re.sub(r"[^\n]", " ", chunk)

    def template(start: int) -> int:
        """Copy a template literal from just past its backtick; return the index past its close."""
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
        """Copy code from ``start``; stop before ``closing`` at depth zero, or at the end."""
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

    while index < length:
        index = code(index, closing=None)
    return "".join(out)


def findings_in(source: str, path: str) -> list[Finding]:
    """Every year bound and edition computation in one source text."""
    found: list[Finding] = []
    for number, line in enumerate(blank_text(source).splitlines(), start=1):
        for rule, pattern in _RULES:
            match = pattern.search(line)
            if match is None:
                continue
            if (
                rule == "year compared"
                and _COUNT_OPERAND.search(line)
                and not pattern.search(_COUNT_OPERAND.sub("", line))
            ):
                continue
            if rule == "year expected" and _COUNT_EXPECTED.search(line):
                continue
            found.append(Finding(path=path, line=number, rule=rule, text=line.strip()))
            break
    return found


def _frontend_files() -> list[Path]:
    return sorted(
        path
        for path in _FRONTEND.rglob("*")
        if path.is_file() and path.suffix in _SUFFIXES and "node_modules" not in path.relative_to(_FRONTEND).parts
    )


def test_the_frontend_source_holds_no_year_bound_and_works_out_no_edition() -> None:
    files = _frontend_files()
    found = [
        finding
        for path in files
        for finding in findings_in(path.read_text(encoding="utf-8"), path.relative_to(REPO_ROOT).as_posix())
    ]

    assert _FRONTEND / "src" / "dev" / "assetsFixture.ts" in files
    assert _FRONTEND / "tests" / "ledger-assets-contract.spec.ts" in files
    assert _FRONTEND / "src" / "components" / "ledger" / "assets" / "AssetForms.stories.tsx" in files
    assert not found, "\n".join(f"{item.path}:{item.line}: {item.rule}: {item.text}" for item in found)


@pytest.mark.parametrize(
    ("planted", "rule"),
    [
        ("if (year < 2022) return null;", "year compared"),
        ("const late = row.tax_year >= 2026;", "year compared"),
        ("if (2099 < year) invalid();", "year compared"),
        ("if (year === 2026) return [];", "year compared"),
        ("const shown = `${year > 2025 ? 'later' : 'now'}`;", "year compared"),
        ("const capped = Math.min(year, 2025);", "year clamped"),
        ("const FIRST_SUPPORTED_YEAR = 2022;", "year constant"),
        ("const [firstYear = 1970] = parts;", "year constant"),
        ("export const YEAR_MAX: number = 2200;", "year constant"),
        ("const Y = 2026;", "year constant"),
        ("const ask = (series: string, year = 2026) => series;", "year constant"),
        ('export const Claim = claiming("furgoneta", 2027, {});', "year argument"),
        ("const boxes = servedHandoffOf(2025)!;", "year argument"),
        ('await choosePeriod(target, 2026, "3T");', "year argument"),
        ("expect(stepYear(2026, 1)).toBe(next);", "year argument"),
        ("expect(row.tax_year).toBe(2022);", "year expected"),
        ("expect(served.default_year).toBe(2026);", "year expected"),
        ("expect(first).not.toEqual(2025);", "year expected"),
        ("expect(row.tax_year).toBeGreaterThanOrEqual(2022);", "year expected"),
        ("const edition = { projected: year > horizon };", "edition worked out"),
        ("const edition = { revision_id: String(Math.min(year, last)) };", "edition worked out"),
        ("const behind = row.edition.authored_filing_year < year;", "edition worked out"),
        ("const gap = year - row.edition?.authored_filing_year;", "edition worked out"),
    ],
)
def test_a_planted_bound_or_edition_computation_is_found(planted: str, rule: str) -> None:
    source = f"// a planted defect\nexport function sample(year: number) {{\n  {planted}\n}}\n"

    assert [finding.rule for finding in findings_in(source, "planted.ts")] == [rule]


@pytest.mark.parametrize(
    "clean",
    [
        'const label = "Since 2000, or before 2022";',
        "// years before 2022 carry no edition",
        "if (servedAdmits(year) && !servedBeyondLastAdmitted(year)) years.push(year);",
        "if ([...words].length <= 2048) keep(words);",
        "const edition = servedEditionOf(year);",
        "const row = { edition: { revision_id: '2025', authored_filing_year: 2025, projected: true } };",
        'const date = "2026-03-02T10:00:00Z";',
        "const when = `${year}-01-01`;",
        "const amount = 2026.5 > total;",
        "const first = Number(range.from_date.slice(0, 4));",
        "export const MAX_ANSWER_CHARS = 2048;",
        'await notes.fill(" ".repeat(2049));',
        "const wide = columnLayout(columns, 16, 2000);",
        "const NOW = new Date(2026, 9, 30, 12, 0, 0);",
        "const scenarioYear = Number(TODAY.slice(0, 4));",
        "await choosePeriod(target, scenarioYear - 1, code);",
        "expect(answer.length).toBe(2048);",
        'expect(await list.locator(".record").count()).toBe(2000);',
        "  .toBeGreaterThan(2000);",
        "expect(served.default_year).toBe(scenarioYear);",
    ],
)
def test_served_reads_text_and_counts_are_not_findings(clean: str) -> None:
    source = f"export function sample(year: number) {{\n  {clean}\n}}\n"

    assert findings_in(source, "clean.ts") == []


def test_an_unpaired_jsx_apostrophe_hides_no_later_finding_and_keeps_line_numbers() -> None:
    source = "export const Note = () => (\n  <p>Don't file twice</p>\n);\nif (year < 2022) refuse();\n"

    assert blank_text(source).count("\n") == source.count("\n")
    assert [(finding.line, finding.rule) for finding in findings_in(source, "planted.tsx")] == [(4, "year compared")]

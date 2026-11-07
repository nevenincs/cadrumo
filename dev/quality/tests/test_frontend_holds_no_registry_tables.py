"""Gate: the desktop frontend's scenario fixtures hold no registry table and cite no provision.

The registry owns the amortization tables, the methods a kind admits, the stages a
basis is stated at and the provisions a charge rests on. The backend serves them,
and the window's scenario fixtures under ``native/desktop/frontend/src/dev`` read
them from the recordings the backend's own producers write. A table restated in
frontend source is a second declaration that drifts the day an official design
moves, and a provision named there is a legal citation nothing grounded.

What counts
-----------
Source is read with its comments blanked, keeping the text of its strings,
because a table and a provision are written inside strings. What tells them from
a sentence shown to a person is their shape: a provision key carries a number
after its series, and a token is lower-case words joined by underscores. Each of
these is a finding in ``src/dev``:

- a **legal reference**: a quoted identifier of an official provision, such as
  a ``ley-``, ``rd-``, ``rdl-``, ``real-decreto`` or ``orden-`` key, an
  ``:art-`` fragment or a BOE reference;
- a **rate table**: a registry corridor field (``maximum_coefficient``,
  ``minimum_coefficient``, ``annual_rate``, ``maximum_period_years``,
  ``linear_coefficient``) set from a literal number or decimal string, or a
  quoted token mapped straight onto a decimal;
- a **token table**: an array or set literal of two or more quoted tokens held
  under a name that speaks of methods, stages, conditions, shapes, authority
  classes, groups, reasons or a table.

A corridor field used in a product, quotient or sum is registry arithmetic and
belongs here too. The clause is not enrolled yet: the plan a newly created
element starts with still works its minimum and its maximum period out from the
corridor the registry serves, because the register answered no plan for a
request the window invents. Enrolling the clause waits on recording those
answers; until then the three clauses above hold the data out.

How to satisfy the gate
-----------------------
Read the answer from the backend: for a scenario fixture, the recording its
producer writes. Where the register answered no figure for the request in hand,
refuse it rather than work one out. There is no allowance list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURES = REPO_ROOT / "native" / "desktop" / "frontend" / "src" / "dev"
_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts"})

_CORRIDOR = r"(?:maximum_coefficient|minimum_coefficient|annual_rate|maximum_period_years|linear_coefficient)"
_QUOTED_WORD = r"\"[a-z][a-z0-9]{2,}(?:_[a-z0-9]+)*\""
_TABLE_NAME = r"\w*(?:METHOD|STAGE|CONDITION|SHAPE|CLASSES|CLASS_|GROUP|REASON|TABLE)\w*"

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "legal reference",
        re.compile(
            r"\"[^\"]*(?:\b(?:ley|rd|rdl|real-decreto|orden|boe)-(?:\d|[a-z]{2,}-\d)|:art-|\bart[-_.]\d)[^\"]*\""
            r"|'[^']*(?:\b(?:ley|rd|rdl|real-decreto|orden|boe)-(?:\d|[a-z]{2,}-\d)|:art-|\bart[-_.]\d)[^']*'"
        ),
    ),
    (
        "rate table",
        re.compile(
            rf"\b{_CORRIDOR}\s*:\s*(?:\{{\s*decimal\s*:\s*)?[\"']?\d*\.\d"
            rf"|\b{_CORRIDOR}\s*=(?![=>])\s*(?:\{{\s*decimal\s*:\s*)?[\"']?\d*\.\d"
            rf"|{_QUOTED_WORD}\s*:\s*[\"']\d*\.\d"
        ),
    ),
    (
        "corridor arithmetic",
        re.compile(rf"\b{_CORRIDOR}\b[\w.?!\[\]()]*\s*[*/+-](?![=>])|[*/+-]\s*[\w.?!(\[\]]*\b{_CORRIDOR}\b"),
    ),
    (
        "token table",
        re.compile(
            rf"\b{_TABLE_NAME}\b[^=\n]*=(?![=>])\s*(?:new Set(?:<[^>]*>)?\()?\[\s*{_QUOTED_WORD}\s*,\s*{_QUOTED_WORD}"
        ),
    ),
)


def blank_comments(source: str) -> str:
    """Blank line and block comments, keeping every string, every token and every newline.

    A provision key and a token table live inside strings, so the text of a
    string is kept and a comment is not: a note about ``ley-35-2006`` is prose
    about the registry, not a citation the fixture makes.
    """
    out: list[str] = []
    at = 0
    length = len(source)
    while at < length:
        char = source[at]
        if source.startswith("//", at):
            end = source.find("\n", at)
            end = length if end < 0 else end
            out.append(re.sub(r"[^\n]", " ", source[at:end]))
            at = end
            continue
        if source.startswith("/*", at):
            end = source.find("*/", at + 2)
            end = length if end < 0 else end + 2
            out.append(re.sub(r"[^\n]", " ", source[at:end]))
            at = end
            continue
        if char in "\"'`":
            end = at + 1
            while end < length and source[end] != char and (char == "`" or source[end] != "\n"):
                end += 2 if source[end] == "\\" else 1
            out.append(source[at : min(end + 1, length)])
            at = min(end + 1, length)
            continue
        out.append(char)
        at += 1
    return "".join(out)


@dataclass(frozen=True, slots=True)
class Finding:
    """One restated registry table or legal reference in a fixture source."""

    path: str
    line: int
    rule: str
    text: str


def findings_in(source: str, path: str) -> list[Finding]:
    """Every restated registry table and legal reference in one source text."""
    found: list[Finding] = []
    for number, line in enumerate(blank_comments(source).splitlines(), start=1):
        for rule, pattern in _RULES:
            if pattern.search(line) is None:
                continue
            found.append(Finding(path=path, line=number, rule=rule, text=line.strip()))
            break
    return found


def _fixture_files() -> list[Path]:
    return sorted(
        path
        for path in _FIXTURES.rglob("*")
        if path.is_file() and path.suffix in _SUFFIXES and "node_modules" not in path.relative_to(_FIXTURES).parts
    )


def test_the_window_fixtures_hold_no_registry_table_and_cite_no_provision() -> None:
    files = _fixture_files()
    found = [
        finding
        for path in files
        for finding in findings_in(path.read_text(encoding="utf-8"), path.relative_to(REPO_ROOT).as_posix())
    ]

    assert _FIXTURES / "assetsFixtureRegister.ts" in files
    assert _FIXTURES / "assetsFixtureWrites.ts" in files
    assert _FIXTURES / "assetsRegister.ts" in files
    assert not found, "\n".join(f"{item.path}:{item.line}: {item.rule}: {item.text}" for item in found)


@pytest.mark.parametrize(
    ("planted", "rule"),
    [
        ('source_reference: "ley-35-2006:art-28",', "legal reference"),
        ('const cited = ["rdl-4-2004:art-11"];', "legal reference"),
        ("const cite = 'orden-hap-72-2013';", "legal reference"),
        ('const where = "boe-2015-11742";', "legal reference"),
        ('const row = { maximum_coefficient: { decimal: "0.12" } };', "rate table"),
        ("const limits = { minimum_coefficient: 0.05 };", "rate table"),
        ('const group = { annual_rate: "0.10" };', "rate table"),
        ('const years = { maximum_period_years: "18" , minimum_coefficient: 0.5 };', "rate table"),
        ('const corridor = { "transporte_externo": "0.16" };', "rate table"),
        ('const TABLE_METHODS = ["linear", "constant_percentage"];', "token table"),
        ('const BASIS_STAGES = ["taxpayer_owned", "business_allocated"];', "token table"),
        ('const SHAPES = new Set<string>(["primary_purchase", "acquired_outside_ledger"]);', "token table"),
        ("const charge = basis * Number(group.minimum_coefficient.decimal);", "corridor arithmetic"),
        ("const annual = Number(group.maximum_coefficient.decimal) * cents;", "corridor arithmetic"),
        ("const ends = first + Number(group.maximum_period_years.decimal);", "corridor arithmetic"),
        ("const share = cents / Number(election.linear_coefficient);", "corridor arithmetic"),
        ("const left = basis - Number(row.annual_rate);", "corridor arithmetic"),
        ("const when = `${first + Number(group.maximum_period_years.decimal)}`;", "corridor arithmetic"),
    ],
)
def test_a_planted_table_or_provision_is_found(planted: str, rule: str) -> None:
    source = f"// a planted defect\nexport function sample(basis: number) {{\n  {planted}\n}}\n"

    assert [finding.rule for finding in findings_in(source, "planted.ts")] == [rule]


@pytest.mark.parametrize(
    "clean",
    [
        'const label = "Amortización según la Ley del IRPF";',
        "// the registry cites ley-35-2006 for this charge",
        "const cited = structuredClone(like.limits.legal_citations);",
        "const corridor = group.maximum_coefficient;",
        "const shown = row.coefficient?.decimal ?? null;",
        "const reference = charge.source_reference;",
        "const groups = TABLE_GROUPS[kind]!.find((found) => found.class_key === key);",
        "const methods = ADMITTED_METHODS[kind]!;",
        "const stated = BASIS_STAGES.some((found) => found.stage === basis.stage);",
        'const kinds = ["material", "intangible"];',
        "const period = group.maximum_period_years.decimal;",
    ],
)
def test_served_reads_and_sentences_are_not_findings(clean: str) -> None:
    source = f"export function sample(basis: number) {{\n  {clean}\n}}\n"

    assert findings_in(source, "clean.ts") == []

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
- ``year text``: a string that is exactly a year, unless the code places it
  as a casilla id (see below);
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
- A casilla id that reads like a year: the official designs number boxes
  ``2003``, ``2038`` or ``2057``, and a box number is no year. A string is a
  casilla id only where the code places it as one: the text given to
  ``validated_casilla_id`` or a key of the mapping given to
  ``validated_casilla_id_map``; a value, element or key typed ``CasillaId``; a
  value, element or mapping key held by a keyword, parameter, assignment target
  or dictionary key whose name says casilla; the key of a subscript of a
  casilla-named mapping (``casillas_by_id["2003"]``); or the other side of a
  comparison with a casilla-named operand (``casilla.id in {"2003", "2004"}``).
  A name says casilla when one of its words is ``casilla`` or ``casillas`` and
  none speaks of time (a year word, ``revision``, ``edition``, ``period``,
  ``predecessor``, ``successor``, ``baseline``, ``epoch``, ``date``), so
  ``casillas_by_revision["2024"]``, ``casilla_storage_baseline="2024"`` and
  ``ejercicio_casilla`` still hold years. Value range never decides it: a
  positional argument to a casilla-named helper (``casilla("2024", "0001")``),
  a value stored under a casilla key (``{EJERCICIO_CASILLA: "2025"}``) and a
  ``box``-named keyword stay findings.
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

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

from .year_literal_python import python_findings
from .year_literal_shapes import Finding
from .year_literal_typescript import typescript_findings

PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx", ".mts", ".cts"})

#: The bundled authority's data root: the one place a year is declared.
AUTHORITY_DATA_ROOTS: Final[tuple[str, ...]] = ("src/cadrumo/_data/",)


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

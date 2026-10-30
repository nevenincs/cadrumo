"""Compiled amortization tables against the primary text they transcribe.

The normal table is parsed from the consolidated LIS article 12.1.a and the
simplified table from the Orden de 27 de marzo de 1998 reprint in the Renta
manual. Neither expectation is restated here: both are read from the bundled
corpus and compared, as multisets of (maximum linear coefficient, maximum
period) pairs, with the parameters the registry compiles for every supported
tax year.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PARAMETER_PREFIX = "renta-actividad-inmovilizado-amortizacion-"
_NORMAL = ("normal-coeficiente-lineal-maximo", "normal-periodo-maximo-anos")
_SIMPLIFIED = ("simplificada-coeficiente-lineal-maximo", "simplificada-periodo-maximo-anos")

_NORMAL_HEADING = (
    "a) Sea el resultado de aplicar los coeficientes de amortización lineal establecidos en la siguiente tabla:"
)
_NORMAL_END = "Reglamentariamente se podrán modificar los coeficientes"
_NORMAL_COLUMN_HEADERS = frozenset({"Tipo de elemento", "Coeficiente lineal máximo", "Periodo de años máximo"})
_SIMPLIFIED_HEADING = "Tabla de amortizaciones simplificada"
_SIMPLIFIED_FOOTNOTE = "(*) Para los activos nuevos"

_PERCENT = re.compile(r"(\d+(?:,\d+)?)%")
_INTEGER = re.compile(r"\d+")
_SIMPLIFIED_ROW_START = re.compile(r"\d{1,2} \D")
_SIMPLIFIED_ROW = re.compile(r"(\d+(?:,\d+)?) por 100 (\d+) años")

Pairs = Counter[tuple[Decimal, Decimal]]


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


def _lines(*parts: str) -> list[str]:
    return bundled_path(*parts).read_text(encoding="utf-8").splitlines()


def _parse_normal_table(lines: list[str]) -> Pairs:
    """Read the LIS table, where each cell is a line and group headers are bare lines."""
    start = next(index for index, line in enumerate(lines) if line.strip() == _NORMAL_HEADING)
    end = next(index for index in range(start, len(lines)) if lines[index].startswith(_NORMAL_END))
    pairs: Pairs = Counter()
    cells = [line.strip() for line in lines[start + 1 : end] if line.strip() not in _NORMAL_COLUMN_HEADERS]
    for index, cell in enumerate(cells):
        percent = _PERCENT.fullmatch(cell)
        if percent is None:
            continue
        assert index + 1 < len(cells) and _INTEGER.fullmatch(cells[index + 1]), cells[index - 1 : index + 2]
        pairs[(Decimal(percent.group(1).replace(",", ".")), Decimal(cells[index + 1]))] += 1
    return pairs


def _parse_simplified_table(lines: list[str]) -> Pairs:
    """Read the reprint, whose rows may continue on following lines and cross a page break."""
    start = next(index for index, line in enumerate(lines) if line.strip() == _SIMPLIFIED_HEADING)
    rows: list[str] = []
    footnotes = 0
    for line in lines[start + 1 :]:
        if line.startswith(_SIMPLIFIED_FOOTNOTE):
            footnotes += 1
            if footnotes == 2:
                break
        elif _SIMPLIFIED_ROW_START.match(line):
            rows.append(line)
        elif rows and not footnotes:
            rows[-1] += " " + line
    pairs: Pairs = Counter()
    for row in rows:
        match = _SIMPLIFIED_ROW.search(row)
        assert match is not None, row
        pairs[(Decimal(match.group(1).replace(",", ".")), Decimal(match.group(2)))] += 1
    return pairs


def _compiled_pairs(revision: ModeloRevision, ids: tuple[str, str], on: date) -> Pairs:
    """Pair the coefficient and period tables key by key, among the entries in force on a date."""
    by_id = {parameter.id: parameter for parameter in revision.parameters}
    in_force: list[dict[str, Decimal]] = []
    for parameter_id in ids:
        table: dict[str, tuple[date, Decimal]] = {}
        for entry in by_id[_PARAMETER_PREFIX + parameter_id].keyed_brackets or ():
            if entry.valid_from <= on and (entry.valid_to is None or entry.valid_to >= on):
                held = table.get(entry.key)
                if held is None or held[0] < entry.valid_from:
                    table[entry.key] = (entry.valid_from, Decimal(str(entry.value)))
        in_force.append({key: value for key, (_, value) in table.items()})
    coefficients, periods = in_force
    assert coefficients.keys() == periods.keys(), sorted(coefficients.keys() ^ periods.keys())
    return Counter((coefficients[key], periods[key]) for key in coefficients)


def _differences(printed: Pairs, compiled: Pairs) -> dict[str, list[tuple[Decimal, Decimal]]]:
    return {
        "printed_only": sorted((printed - compiled).elements()),
        "compiled_only": sorted((compiled - printed).elements()),
    }


def _assert_same_table(printed: Pairs, compiled: Pairs) -> None:
    assert printed.total() == compiled.total(), (printed.total(), compiled.total())
    assert printed == compiled, _differences(printed, compiled)


@cache
def _printed_normal() -> Pairs:
    return _parse_normal_table(_lines("corpus", "normatives", "html", "ley-27-2014-art-12-full.html.extracted.md"))


@cache
def _printed_simplified() -> Pairs:
    return _parse_simplified_table(_lines("corpus", "manuals", "renta", "2025", "part1", "source.pdf.extracted.md"))


def _revision(year: int) -> ModeloRevision:
    return compiled_bundled_authority().snapshot("100", filing_year=year, period="0A").revision


def test_the_printed_tables_are_read_in_full() -> None:
    """A parser that read nothing would let every comparison below pass vacuously."""
    assert _printed_normal().total() > 20
    assert _printed_simplified().total() == 10


@pytest.mark.parametrize("year", _supported_years())
def test_the_normal_table_matches_the_lis(year: int) -> None:
    _assert_same_table(_printed_normal(), _compiled_pairs(_revision(year), _NORMAL, date(year, 1, 1)))


@pytest.mark.parametrize("year", _supported_years())
def test_the_simplified_table_matches_the_orden_reprint(year: int) -> None:
    _assert_same_table(_printed_simplified(), _compiled_pairs(_revision(year), _SIMPLIFIED, date(year, 1, 1)))


def _altered(pairs: Pairs, replace: Mapping[tuple[Decimal, Decimal], tuple[Decimal, Decimal]]) -> Pairs:
    altered = Counter(pairs)
    for old, new in replace.items():
        altered[old] -= 1
        altered[new] += 1
    return +altered


def _first_pair(pairs: Iterable[tuple[Decimal, Decimal]]) -> tuple[Decimal, Decimal]:
    return min(pairs)


@pytest.mark.parametrize("printed", [_printed_normal, _printed_simplified])
def test_the_comparison_detects_an_altered_value_or_a_missing_row(printed: Callable[[], Pairs]) -> None:
    pairs = printed()
    _assert_same_table(pairs, Counter(pairs))

    victim = _first_pair(pairs)
    for compiled in (
        _altered(pairs, {victim: (victim[0] + 1, victim[1])}),
        _altered(pairs, {victim: (victim[0], victim[1] + 1)}),
        pairs - Counter([victim]),
        pairs + Counter([victim]),
    ):
        with pytest.raises(AssertionError):
            _assert_same_table(pairs, compiled)

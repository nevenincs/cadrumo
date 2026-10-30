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
_GROUP_NUMBER = re.compile(r"^\s*\d{1,2} ")
_SIMPLIFIED_ROW = re.compile(r"(\d+(?:,\d+)?) por 100 (\d+) años")

Pairs = Counter[tuple[Decimal, Decimal]]


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


def _lines(*parts: str) -> list[str]:
    return bundled_path(*parts).read_text(encoding="utf-8").splitlines()


def _label(text: str) -> str:
    """Normalize a printed element name so layout and trailing punctuation do not matter."""
    return " ".join(text.split()).rstrip(".").casefold()


def _parse_normal_rows(lines: list[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """Read the LIS table, where each cell is a line and group headers are bare lines.

    A row is the element name on the line before its coefficient line; group headers have no
    coefficient after them and are not rows.
    """
    start = next(index for index, line in enumerate(lines) if line.strip() == _NORMAL_HEADING)
    end = next(index for index in range(start, len(lines)) if lines[index].startswith(_NORMAL_END))
    rows: dict[str, tuple[Decimal, Decimal]] = {}
    cells = [line.strip() for line in lines[start + 1 : end] if line.strip() not in _NORMAL_COLUMN_HEADERS]
    for index, cell in enumerate(cells):
        percent = _PERCENT.fullmatch(cell)
        if percent is None:
            continue
        assert index + 1 < len(cells) and _INTEGER.fullmatch(cells[index + 1]), cells[index - 1 : index + 2]
        name = _label(cells[index - 1])
        assert name not in rows, name
        rows[name] = (Decimal(percent.group(1).replace(",", ".")), Decimal(cells[index + 1]))
    return rows


def _parse_simplified_rows(lines: list[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """Read the reprint, whose rows may continue on following lines and cross a page break."""
    start = next(index for index, line in enumerate(lines) if line.strip() == _SIMPLIFIED_HEADING)
    rows: list[str] = []
    footnotes = 0
    in_footnote = False
    for line in lines[start + 1 :]:
        if line.strip() == _SIMPLIFIED_HEADING:
            in_footnote = False
        elif line.startswith(_SIMPLIFIED_FOOTNOTE):
            in_footnote = True
            footnotes += 1
            if footnotes == 2:
                break
        elif _SIMPLIFIED_ROW_START.match(line):
            rows.append(line)
        elif rows and not in_footnote:
            rows[-1] += " " + line
    parsed: dict[str, tuple[Decimal, Decimal]] = {}
    for row in rows:
        match = _SIMPLIFIED_ROW.search(row)
        assert match is not None, row
        name = _label(_GROUP_NUMBER.sub("", row[: match.start()] + " " + row[match.end() :], count=1))
        assert name not in parsed, name
        parsed[name] = (Decimal(match.group(1).replace(",", ".")), Decimal(match.group(2)))
    return parsed


def _compiled_rows(revision: ModeloRevision, ids: tuple[str, str], on: date) -> dict[str, tuple[Decimal, Decimal]]:
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
    return {key: (coefficients[key], periods[key]) for key in coefficients}


def _compiled_pairs(revision: ModeloRevision, ids: tuple[str, str], on: date) -> Pairs:
    return Counter(_compiled_rows(revision, ids, on).values())


def _differences(printed: Pairs, compiled: Pairs) -> dict[str, list[tuple[Decimal, Decimal]]]:
    return {
        "printed_only": sorted((printed - compiled).elements()),
        "compiled_only": sorted((compiled - printed).elements()),
    }


def _assert_same_table(printed: Pairs, compiled: Pairs) -> None:
    assert printed.total() == compiled.total(), (printed.total(), compiled.total())
    assert printed == compiled, _differences(printed, compiled)


@cache
def _printed_normal_rows() -> dict[str, tuple[Decimal, Decimal]]:
    return _parse_normal_rows(_lines("corpus", "normatives", "html", "ley-27-2014-art-12-full.html.extracted.md"))


@cache
def _printed_simplified_rows() -> dict[str, tuple[Decimal, Decimal]]:
    return _parse_simplified_rows(_lines("corpus", "manuals", "renta", "2025", "part1", "source.pdf.extracted.md"))


def _printed_normal() -> Pairs:
    return Counter(_printed_normal_rows().values())


def _printed_simplified() -> Pairs:
    return Counter(_printed_simplified_rows().values())


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


# The registry keys carry no printed text, so each key is tied to the element name printed on its row.
# Only names are held here; coefficients and periods are always read from the primary text.
_NORMAL_KEY_LABELS = {
    "obra-civil-general": "Obra civil general",
    "obra-civil-pavimentos": "Pavimentos",
    "obra-civil-infraestructuras-mineras": "Infraestructuras y obras mineras",
    "central-hidraulica": "Centrales hidráulicas",
    "central-nuclear": "Centrales nucleares",
    "central-carbon": "Centrales de carbón",
    "central-renovable": "Centrales renovables",
    "central-otra": "Otras centrales",
    "edificio-industrial": "Edificios industriales",
    "terreno-escombrera": "Terrenos dedicados exclusivamente a escombreras",
    "almacen-deposito": "Almacenes y depósitos (gaseosos, líquidos y sólidos)",
    "edificio-comercial-administrativo-servicios-vivienda": (
        "Edificios comerciales, administrativos, de servicios y viviendas"
    ),
    "instalacion-subestacion-red": "Subestaciones. Redes de transporte y distribución de energía",
    "instalacion-cables": "Cables",
    "instalacion-resto": "Resto instalaciones",
    "maquinaria": "Maquinaria",
    "equipo-medico": "Equipos médicos y asimilados",
    "transporte-locomotora-vagon-traccion": "Locomotoras, vagones y equipos de tracción",
    "transporte-buque-aeronave": "Buques, aeronaves",
    "transporte-interno": "Elementos de transporte interno",
    "transporte-externo": "Elementos de transporte externo",
    "transporte-autocamion": "Autocamiones",
    "mobiliario": "Mobiliario",
    "lenceria": "Lencería",
    "cristaleria": "Cristalería",
    "util-herramienta": "Útiles y herramientas",
    "molde-matriz-modelo": "Moldes, matrices y modelos",
    "enseres-otros": "Otros enseres",
    "equipo-electronico": "Equipos electrónicos",
    "equipo-proceso-informacion": "Equipos para procesos de información",
    "intangible-software": "Sistemas y programas informáticos.",
    "intangible-audiovisual": "Producciones cinematográficas, fonográficas, videos y series audiovisuales",
    "otro-elemento": "Otros elementos",
}
_SIMPLIFIED_KEY_LABELS = {
    "edificio-otra-construccion": "Edificios y otras construcciones",
    "instalacion-mobiliario-enseres-resto-material": (
        "Instalaciones, mobiliario, enseres y resto del inmovilizado material"
    ),
    "maquinaria": "Maquinaria",
    "transporte": "Elementos de transporte",
    "equipo-informacion-software": ("Equipos para tratamiento de la información y sistemas y programas informáticos"),
    "util-herramienta": "Útiles y herramientas",
    "ganado-vacuno-porcino-ovino-caprino": "Ganado vacuno, porcino, ovino y caprino",
    "ganado-equino-frutal-no-citrico": "Ganado equino y frutales no cítricos",
    "frutal-citrico-vinedo": "Frutales cítricos y viñedos",
    "olivar": "Olivar",
}


def _assert_rows_match(
    printed: Mapping[str, tuple[Decimal, Decimal]],
    compiled: Mapping[str, tuple[Decimal, Decimal]],
    labels: Mapping[str, str],
) -> None:
    """Each registry key must hold the pair printed on the row of its own element name."""
    names = [_label(name) for name in labels.values()]
    assert len(set(names)) == len(names), "two keys share one printed row"
    assert set(labels) == set(compiled), sorted(set(labels) ^ set(compiled))
    assert set(names) == set(printed), sorted(set(names) ^ set(printed))
    wrong = {
        key: {"registry": compiled[key], "printed": printed[_label(name)], "row": name}
        for key, name in labels.items()
        if compiled[key] != printed[_label(name)]
    }
    assert not wrong, wrong


@pytest.mark.parametrize("year", _supported_years())
def test_each_normal_class_holds_the_pair_printed_on_its_row(year: int) -> None:
    compiled = _compiled_rows(_revision(year), _NORMAL, date(year, 1, 1))
    _assert_rows_match(_printed_normal_rows(), compiled, _NORMAL_KEY_LABELS)


@pytest.mark.parametrize("year", _supported_years())
def test_each_simplified_class_holds_the_pair_printed_on_its_row(year: int) -> None:
    compiled = _compiled_rows(_revision(year), _SIMPLIFIED, date(year, 1, 1))
    _assert_rows_match(_printed_simplified_rows(), compiled, _SIMPLIFIED_KEY_LABELS)


@pytest.mark.parametrize(
    ("printed", "labels"),
    [(_printed_normal_rows, _NORMAL_KEY_LABELS), (_printed_simplified_rows, _SIMPLIFIED_KEY_LABELS)],
)
def test_the_row_comparison_detects_swapped_classes_and_unpaired_keys(
    printed: Callable[[], dict[str, tuple[Decimal, Decimal]]], labels: Mapping[str, str]
) -> None:
    rows = printed()
    correct = {key: rows[_label(name)] for key, name in labels.items()}
    _assert_rows_match(rows, correct, labels)

    first, second = next((a, b) for a in correct for b in correct if correct[a] != correct[b])
    swapped = {**correct, first: correct[second], second: correct[first]}
    # The multiset comparison cannot see this defect; the row comparison must.
    assert Counter(swapped.values()) == Counter(correct.values())
    with pytest.raises(AssertionError):
        _assert_rows_match(rows, swapped, labels)

    with pytest.raises(AssertionError):
        _assert_rows_match(rows, {k: v for k, v in correct.items() if k != first}, labels)
    with pytest.raises(AssertionError):
        _assert_rows_match(rows, {**correct, "unlisted-class": correct[first]}, labels)
    with pytest.raises(AssertionError):
        _assert_rows_match(rows, correct, {**labels, second: labels[first]})

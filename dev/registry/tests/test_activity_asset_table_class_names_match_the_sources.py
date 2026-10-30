"""The official names of the amortization table classes are the rows of the legal tables.

The names are authored once as registry data and served with each class. Each
test reads the table rows from the bundled source text, so a name that drifts
from its row, a row left without a name, or a name attached to the wrong
coefficient and period fails here. The normal modality's rows come from the
consolidated LIS art. 12.1.a table; the simplified modality's rows come from the
Orden de 27 de marzo de 1998 table that each bundled Renta manual reprints.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetTableGroup,
    activity_asset_form_options,
    resolve_activity_asset_class_labels,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LIS_TABLE = ("corpus", "normatives", "html", "ley-27-2014-art-12-full.html.extracted.md")
_LIS_TABLE_START = "Periodo de años máximo"
_LIS_TABLE_END = "Reglamentariamente se podrán modificar"
_SIMPLIFIED_HEADING = "Tabla de amortizaciones simplificada"
_SIMPLIFIED_END = "(*)"
_SIMPLIFIED_ROW = re.compile(r"(\d+) (.+?) (\d+) por 100 (\d+) años")
_SIMPLIFIED_HEADER_LINES = ("Coeficiente lineal", "Grupo Descripción")

_SourceRow = tuple[str, Decimal, Decimal]


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _lis_rows() -> tuple[_SourceRow, ...]:
    """Each LIS table row as printed: its name, linear coefficient in percent and period in years."""
    lines = bundled_path(*_LIS_TABLE).read_text(encoding="utf-8").splitlines()
    first = lines.index(_LIS_TABLE_START) + 1
    last = next(index for index, line in enumerate(lines) if line.startswith(_LIS_TABLE_END))
    rows: list[_SourceRow] = []
    index = first
    while index < last:
        is_row = (
            index + 2 < last
            and re.fullmatch(r"\d+%", lines[index + 1]) is not None
            and re.fullmatch(r"\d+", lines[index + 2]) is not None
        )
        if is_row:
            rows.append(
                (lines[index].rstrip("."), Decimal(lines[index + 1].removesuffix("%")), Decimal(lines[index + 2]))
            )
            index += 3
        else:
            index += 1
    return tuple(rows)


def _manual_lines(year: int) -> list[str]:
    path = bundled_path("corpus", "manuals", "renta", str(year), "part1", "source.pdf.extracted.md")
    return path.read_text(encoding="utf-8").splitlines()


def _simplified_rows(lines: list[str], start: int) -> tuple[_SourceRow, ...]:
    """The rows of one reprint of the simplified table, joining a description a page line wrapped."""
    end = next(index for index in range(start, len(lines)) if lines[index].startswith(_SIMPLIFIED_END))
    rows: list[list[str]] = []
    for line in lines[start + 1 : end]:
        match = _SIMPLIFIED_ROW.fullmatch(line)
        if match is not None:
            rows.append([match.group(2), match.group(3), match.group(4)])
        elif rows and not line.startswith(_SIMPLIFIED_HEADER_LINES):
            rows[-1][0] += f" {line}"
    return tuple((name, Decimal(coefficient), Decimal(period)) for name, coefficient, period in rows)


@cache
def _simplified_table(year: int) -> tuple[_SourceRow, ...]:
    """The simplified table of one year's manual; every reprint in it must agree."""
    lines = _manual_lines(year)
    starts = [index for index, line in enumerate(lines) if line == _SIMPLIFIED_HEADING]
    # A heading repeated at a page break carries no rows; only a reprint that has rows is a table.
    tables = {rows for start in starts if (rows := _simplified_rows(lines, start))}
    assert len(tables) == 1, f"the {year} manual does not reprint one simplified table"
    return next(iter(tables))


def _manual_years() -> tuple[int, ...]:
    return tuple(sorted(set(manual_editions_printing("renta", _SIMPLIFIED_HEADING)) & set(_supported_years())))


def _edition(year: int) -> ModeloRevision:
    return compiled_bundled_authority().snapshot("100", filing_year=year, period="0A").revision


def _groups(year: int, regime: DirectEstimationRegime) -> dict[str, ActivityAssetTableGroup]:
    labels = resolve_activity_asset_class_labels(compiled_bundled_authority(), regime=regime, tax_year=year)
    groups: dict[str, ActivityAssetTableGroup] = {}
    for kind in AssetKind:
        options = activity_asset_form_options(
            _edition(year),
            tax_year=year,
            asset_kind=kind,
            regime=regime,
            class_labels=labels,
        )
        groups.update({group.class_key: group for group in options.table_groups})
    return groups


def _assert_names_are_the_rows(groups: dict[str, ActivityAssetTableGroup], rows: tuple[_SourceRow, ...]) -> None:
    printed = {name: (coefficient, period) for name, coefficient, period in rows}
    assert len(printed) == len(rows), "a table prints one name twice"
    authored = {group.class_label: group for group in groups.values()}
    assert len(authored) == len(groups), "two classes share one name"
    assert set(authored) == set(printed)
    for name, group in authored.items():
        coefficient, period = printed[name]
        assert group.maximum_coefficient == coefficient / Decimal(100), name
        assert group.maximum_period_years == period, name


def test_the_lis_table_was_read_in_full() -> None:
    assert len(_lis_rows()) > 1
    assert all(coefficient * period >= Decimal(100) for _, coefficient, period in _lis_rows())


@pytest.mark.parametrize("year", _supported_years())
def test_every_normal_modality_class_is_named_as_its_lis_row(year: int) -> None:
    _assert_names_are_the_rows(_groups(year, DirectEstimationRegime.NORMAL), _lis_rows())


def test_some_supported_year_has_a_manual_printing_the_simplified_table() -> None:
    assert set(_manual_years()) & set(_supported_years())


@pytest.mark.parametrize("year", _manual_years())
def test_every_simplified_modality_class_is_named_as_its_order_row(year: int) -> None:
    _assert_names_are_the_rows(_groups(year, DirectEstimationRegime.SIMPLIFIED), _simplified_table(year))


@pytest.mark.parametrize("regime", list(DirectEstimationRegime))
@pytest.mark.parametrize("year", _supported_years())
def test_no_name_is_authored_for_a_class_the_tables_do_not_offer(year: int, regime: DirectEstimationRegime) -> None:
    labels = resolve_activity_asset_class_labels(compiled_bundled_authority(), regime=regime, tax_year=year)

    assert set(labels) == set(_groups(year, regime))

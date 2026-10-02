"""Modelo 222's 2022 edition follows the 2019-2022 design and instructions, not the 2023 ones.

AEAT publishes the 2019-2022 diseno de registro and instructions separately from
the 2023-2024 ones. Against the later design, 2022 lacks the page-1 flag the 2023
design adds and boxes [59] and [60], which 2023 folds into [10]; everything else is
the same concept, so the 2022 edition is the storage baseline and 2023 stores only
those differences against it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import validated_casilla_id_map
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import (
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
)
from cadrumo.domain.calculations.registry.schema_base import NUMERIC_CASILLA_DATA_TYPES
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.registry_schema_support import committed_modelo
from .authored_edition_support import legal_text_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN = "aeat-dr-222-2019-2022"
_INSTRUCTIONS = "aeat-modelo-222-instructions-2019-2022"
_MONTHS = {"abril": 4, "octubre": 10, "diciembre": 12}


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("222")


@cache
def _year() -> int:
    """The last filing year the 2019-2022 design governs, read from its own catalogue window."""
    _, catalogues = _modelo()
    applies_to = catalogues.sources[_DESIGN].applies_to
    assert applies_to is not None
    return applies_to.year


def _selected(year: int, period: str = "1P") -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period=period, support=catalogues.supported_filing_years)


def _references(expression: FormulaExpression) -> set[str]:
    found: set[str] = set()
    if expression.casilla_id is not None:
        found.add(str(expression.casilla_id))
    for arg in expression.args:
        found |= _references(arg)
    return found


def _formula_for(revision: ModeloRevision, target: str) -> FormulaDefinition:
    (formula,) = (formula for formula in revision.formulas if str(formula.target_casilla_id) == target)
    return formula


def test_the_year_is_authored_at_calculation_grade_on_its_own_design() -> None:
    _, catalogues = _modelo()
    year = _year()
    revision = _selected(year)
    resolution = revision_temporal_resolution(
        revision, filing_year=year, period="1P", support=catalogues.supported_filing_years
    )
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    assert revision.authority_grade is RegistryAuthorityGrade.CALCULATION
    _, catalogues = _modelo()
    cited_designs = {
        str(casilla.id): {ref for ref in casilla.source_refs if catalogues.sources[ref].kind == "record_design"}
        for casilla in revision.casillas
    }
    assert {design for designs in cited_designs.values() for design in designs} == {_DESIGN}
    (layout,) = revision.export_layouts
    assert _DESIGN in layout.source_refs


def test_the_year_snapshots_on_sources_that_govern_it() -> None:
    year = _year()
    snapshot = compiled_bundled_authority().snapshot(
        "222", filing_year=year, period="1P", grade=RegistryAuthorityGrade.CALCULATION
    )
    assert str(snapshot.revision.id) == str(_selected(year).id)
    (expectation,) = snapshot.revision.verification_expectations
    assert set(expectation.source_refs) == {_DESIGN, _INSTRUCTIONS}
    computed = {str(formula.target_casilla_id) for formula in snapshot.revision.formulas}
    assert set(expectation.reconcile_when_present_casilla_ids) == computed


def test_boxes_59_and_60_begin_with_the_next_design() -> None:
    year = _year()
    current, following = _selected(year), _selected(year + 1)
    assert {"59", "60"}.isdisjoint(str(casilla.id) for casilla in current.casillas)
    assert {"59", "60"} <= {str(casilla.id) for casilla in following.casillas}

    current_ten = _formula_for(current, "10")
    assert _references(current_ten.expression) == {"04", "38", "39"}
    assert _references(_formula_for(following, "10").expression) == {"04", "38", "39", "59", "60"}
    assert {str(citation.source_ref) for citation in current_ten.source_citations} == {_INSTRUCTIONS}


def test_every_formula_cites_the_instructions_of_its_own_era() -> None:
    revision = _selected(_year())
    for formula in revision.formulas:
        assert {str(citation.source_ref) for citation in formula.source_citations} == {_INSTRUCTIONS}, formula.id


def _calculate(year: int, values: Mapping[str, str]) -> dict[str, Decimal]:
    """Run the real engine over the year's snapshot with every unnamed manual box at zero."""
    snapshot = compiled_bundled_authority().snapshot(
        "222", filing_year=year, period="1P", grade=RegistryAuthorityGrade.CALCULATION
    )
    manual: dict[object, Decimal] = {
        str(casilla.id): Decimal(values.get(str(casilla.id), "0"))
        for casilla in snapshot.revision.casillas
        if casilla.input_kind is not InputKind.COMPUTED and casilla.data_type in NUMERIC_CASILLA_DATA_TYPES
    }
    assert set(values) <= set(manual)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=validated_casilla_id_map(manual, surface="modelo 222 manual boxes"),
        date_context={"filing_period": date(year, 4, 20)},
    )
    return {str(entry.target_casilla_id): entry.value for entry in result.entries}


# Hand-worked from the printed formulas: [16] and [19] are both
# [13] + [44] + [45] - [46] - [14] - [15] + [47] - [48], and B.2 splits that base
# as [23] = [19] - [20]. The following edition adds [59] - [60] into [10]:
#   2019-2022: [13] = 100000;               base 100000 - 10000 = 90000; [23] = 60000
#   2023-2024: [13] = 100000 + 5000 - 2000; base 103000 - 10000 = 93000; [23] = 63000
# [22] = 30000 x 15 / 100 = 4500, [25] = [23] x 24 / 100, [26] = [22] + [25], and
# [32] = [26] x 100 / 100 - 1000.
@pytest.mark.parametrize(
    ("following", "extra", "expected"),
    [
        (0, {}, {"16": "90000", "19": "90000", "23": "60000", "25": "14400", "26": "18900", "32": "17900"}),
        (
            1,
            {"59": "5000", "60": "2000"},
            {"16": "93000", "19": "93000", "23": "63000", "25": "15120", "26": "19620", "32": "18620"},
        ),
    ],
    ids=["2019-2022 design", "2023-2024 design"],
)
def test_several_rates_group_splits_the_same_base_the_single_rate_lane_uses(
    following: int, extra: Mapping[str, str], expected: Mapping[str, str]
) -> None:
    computed = _calculate(
        _year() + following,
        {"04": "100000", "14": "10000", "20": "30000", "21": "15", "24": "24", "29": "100", "30": "1000", **extra},
    )

    assert {box: computed[box] for box in expected} == {box: Decimal(value) for box, value in expected.items()}
    assert computed["22"] == Decimal("4500")
    assert computed["18"] == Decimal("0")  # no single percentage [17] is declared
    assert computed["34"] == computed["32"]  # the minimum [33] is zero


def test_single_rate_group_settles_through_the_b1_lane() -> None:
    computed = _calculate(_year(), {"04": "100000", "14": "10000", "17": "24", "29": "100"})

    assert computed["16"] == Decimal("90000")  # 100000 - 10000
    assert computed["18"] == Decimal("21600")  # 90000 x 24 / 100
    assert computed["26"] == Decimal("0")  # no B.2 percentage is declared
    assert computed["32"] == Decimal("21600")
    assert computed["34"] == Decimal("21600")


def test_the_modalidad_rate_covers_the_year() -> None:
    year = _year()
    (parameter,) = (item for item in _selected(year).parameters if str(item.id) == "is.modalidad_cuota.percentage")
    assert [value.valid_from for value in parameter.values] == [date(year, 1, 1)]


def test_the_windows_follow_the_statutory_plazo() -> None:
    year = _year()
    pattern = r"durante los primeros (\w+) dias naturales de los meses de ([a-z, y]+)"
    text = legal_text_match("orden-hfp-227-2017:art-5", pattern)
    days = {"veinte": 20}[text.group(1)]
    months = [_MONTHS[name] for name in re.findall(r"[a-z]+", text.group(2)) if name in _MONTHS]
    windows = sorted(_selected(year).deadline_windows, key=lambda window: window.opens_on)
    assert [(window.opens_on, window.closes_on) for window in windows] == [
        (date(year, month, 1), date(year, month, days)) for month in months
    ]
    assert all(window.filing_year == year for window in windows)

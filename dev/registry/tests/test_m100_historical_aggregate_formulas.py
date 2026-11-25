"""Historical sums must not consume later reuse of a printed box number."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions
from dev.registry.compiler.loader import load_modelo_directory

# Authored Modelo 100 editions, oldest first: formulas are pinned per edition by ordinal, and a later edition appends.
_E = tuple(str(revision.id) for revision in authored_revisions("100"))

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def modelo100():
    return load_modelo_directory(
        Path(__file__).resolve().parents[3] / "src/cadrumo/_data/registry/aeat/modelos/100",
    )


@pytest.mark.parametrize(
    ("year", "target", "expected"),
    [
        (_E[0], "0288", ("0282", "0286")),
        (_E[0], "0297", ("0292", "0296")),
        (_E[0], "0306", ("0299", "0300", "0301", "0302", "0303", "0304")),
        (_E[1], "0288", ("0282", "0286")),
        (_E[1], "0297", ("0292", "0296")),
        (_E[1], "0306", ("0299", "0300", "0301", "0302", "0303", "0304", "0266", "0279")),
        (_E[5], "0288", ("0282", "0286", "0360")),
        (_E[5], "0297", ("0292", "0296", "0361")),
    ],
)
def test_historical_gain_sums_follow_their_own_official_form(modelo100, year, target, expected):
    """AEAT dictionaries SUMGAN/G1RT10/SUM1G1 define these exact sums."""
    formula = next(item for item in modelo100.revisions[year].formulas if item.target_casilla_id == target)
    assert formula.expression.op == "sum"
    assert tuple(arg.casilla_id for arg in formula.expression.args) == expected
    assert all(arg.op is None for arg in formula.expression.args)


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (_E[0], "subtract(1548,1549)"),
        (_E[1], "subtract(1548,1549)"),
        (_E[2], "sum(1548,negate(1549),negate(0160))"),
        (_E[3], "sum(1548,negate(1549),negate(0160))"),
        (_E[4], "sum(1548,negate(1549),negate(0162),negate(0160))"),
        (_E[5], "subtract(1548,1549)"),
    ],
)
def test_agricultural_reductions_follow_temporary_edition_scope(modelo100, year, expected):
    """E5AF subtracts La Palma/DANA only before those box numbers are reused."""
    formula = next(item for item in modelo100.revisions[year].formulas if item.target_casilla_id == "1550")

    def expression_signature(expression):
        if expression.casilla_id is not None:
            return str(expression.casilla_id)
        return f"{expression.op}({','.join(expression_signature(arg) for arg in expression.args)})"

    assert expression_signature(formula.expression) == expected

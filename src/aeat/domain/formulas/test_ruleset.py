"""Tests for :class:`aeat.domain.formulas._ruleset.Ruleset` structural invariants.

Covers casilla-reference validation, evaluation-order acyclicity,
parameter-table resolution, and end-to-end loading of a shipped
ruleset.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...core.errors import (
    CasillaNotDefinedError,
    FormulaCycleError,
    RulesetValidationError,
)
from ..casillas import CasillaDataType
from ..modelos import LegalCitation, LegalCitationSource, ModeloCode
from ._casilla import CasillaDefinition
from ._formula import (
    FormulaCasillaRef,
    FormulaDefinition,
    Literal,
    ParamRef,
    RoundFormula,
    SubFormula,
)
from ._ruleset import ParameterTable, ParameterValue, Ruleset
from ._rulesets.modelo_130_2024 import RULESET as MODELO_130_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_FIXTURE_CITATION = LegalCitation(
    source=LegalCitationSource.REAL_DECRETO,
    article="110",
    url=None,
    quoted_text_es=(
        "Fixture-only citation for the Ruleset structural-invariant tests; not authored as a binding ruleset reference."
    ),
    retrieval_date=date(2026, 4, 25),
    is_curated_summary=True,
)


def _make_casilla(casilla_id: str, *, computed: bool) -> CasillaDefinition:
    legal_basis: tuple[LegalCitation, ...] = (_FIXTURE_CITATION,) if computed else ()
    return CasillaDefinition(
        casilla_id=casilla_id,
        label={"es": f"Casilla {casilla_id}", "en": f"box {casilla_id}", "hu": "rovat"},
        computed=computed,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=legal_basis,
    )


@pytest.mark.unit
def test_modelo_130_2024_loads() -> None:
    """The shipped 2024 ruleset loads without error."""
    assert MODELO_130_2024.ruleset_id == "modelo_130.2024"
    assert len(MODELO_130_2024.casillas) == 19
    assert len(MODELO_130_2024.formulas) == 9


@pytest.mark.unit
def test_dangling_casilla_ref_raises() -> None:
    """A formula referencing an undeclared casilla raises CasillaNotDefinedError."""
    body = SubFormula(
        operands=(  # type: ignore[arg-type]
            FormulaCasillaRef(casilla_id="01"),
            FormulaCasillaRef(casilla_id="99"),
        )
    )
    with pytest.raises(CasillaNotDefinedError):
        Ruleset(
            ruleset_id="test.dangling",
            modelo=ModeloCode.MODELO_130,
            effective_from=date(2024, 1, 1),
            casillas=(
                _make_casilla("01", computed=False),
                _make_casilla("03", computed=True),
            ),
            formulas=(
                FormulaDefinition(
                    casilla_id="03",
                    formula_id="test.dangling.03",
                    formula=RoundFormula(operands=(body,)),  # type: ignore[arg-type]
                ),
            ),
        )


@pytest.mark.unit
def test_cycle_raises_formula_cycle_error() -> None:
    """A self-referential formula raises FormulaCycleError."""
    body = SubFormula(
        operands=(  # type: ignore[arg-type]
            FormulaCasillaRef(casilla_id="03"),
            Literal(value=Decimal("1")),
        )
    )
    with pytest.raises(FormulaCycleError) as excinfo:
        Ruleset(
            ruleset_id="test.cycle",
            modelo=ModeloCode.MODELO_130,
            effective_from=date(2024, 1, 1),
            casillas=(_make_casilla("03", computed=True),),
            formulas=(
                FormulaDefinition(
                    casilla_id="03",
                    formula_id="test.cycle.03",
                    formula=RoundFormula(operands=(body,)),  # type: ignore[arg-type]
                ),
            ),
        )
    assert "03" in "->".join(excinfo.value.cycle)


@pytest.mark.unit
def test_formula_bound_to_non_computed_casilla_raises() -> None:
    """Formulas must target a casilla flagged ``computed=True``."""
    body = SubFormula(
        operands=(  # type: ignore[arg-type]
            FormulaCasillaRef(casilla_id="01"),
            Literal(value=Decimal("1")),
        )
    )
    with pytest.raises(RulesetValidationError):
        Ruleset(
            ruleset_id="test.noncomputed",
            modelo=ModeloCode.MODELO_130,
            effective_from=date(2024, 1, 1),
            casillas=(_make_casilla("01", computed=False),),
            formulas=(
                FormulaDefinition(
                    casilla_id="01",
                    formula_id="test.noncomputed.01",
                    formula=RoundFormula(operands=(body,)),  # type: ignore[arg-type]
                ),
            ),
        )


@pytest.mark.unit
def test_missing_param_ref_raises() -> None:
    """A formula referencing a parameter not declared in the table is rejected."""
    body = SubFormula(
        operands=(  # type: ignore[arg-type]
            ParamRef(param_id="missing.rate"),
            Literal(value=Decimal("1")),
        )
    )
    with pytest.raises(RulesetValidationError):
        Ruleset(
            ruleset_id="test.missing_param",
            modelo=ModeloCode.MODELO_130,
            effective_from=date(2024, 1, 1),
            casillas=(_make_casilla("03", computed=True),),
            formulas=(
                FormulaDefinition(
                    casilla_id="03",
                    formula_id="test.missing_param.03",
                    formula=RoundFormula(operands=(body,)),  # type: ignore[arg-type]
                ),
            ),
        )


@pytest.mark.unit
def test_parameter_table_resolves_on_date() -> None:
    """ParameterTable.resolve returns the active value for a date."""
    table = ParameterTable(
        entries={
            "irpf.rate": (
                ParameterValue(
                    effective_from=date(2024, 1, 1),
                    effective_to=date(2024, 12, 31),
                    value=Decimal("0.20"),
                ),
                ParameterValue(
                    effective_from=date(2025, 1, 1),
                    effective_to=None,
                    value=Decimal("0.25"),
                ),
            )
        }
    )
    assert table.resolve("irpf.rate", on=date(2024, 6, 15)) == Decimal("0.20")
    assert table.resolve("irpf.rate", on=date(2025, 1, 1)) == Decimal("0.25")


@pytest.mark.unit
def test_evaluation_order_is_acyclic() -> None:
    """The 2024 ruleset produces a deterministic topological order."""
    order = MODELO_130_2024.evaluation_order()
    positions = {casilla_id: idx for idx, casilla_id in enumerate(order)}
    # Computed casillas must follow their references.
    assert positions["03"] > positions["01"]
    assert positions["03"] > positions["02"]
    assert positions["04"] > positions["03"]
    assert positions["07"] > positions["04"]
    assert positions["07"] > positions["05"]
    assert positions["07"] > positions["06"]
    assert positions["12"] > positions["07"]
    assert positions["12"] > positions["11"]
    assert positions["14"] > positions["12"]
    assert positions["17"] > positions["14"]
    assert positions["17"] > positions["15"]
    assert positions["17"] > positions["16"]
    assert positions["19"] > positions["17"]
    assert positions["19"] > positions["18"]

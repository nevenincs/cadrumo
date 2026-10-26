"""Independent examples for the arithmetic printed on Modelo 322's four pages."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema import FormulaDefinition

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _evaluate(formula: FormulaDefinition, values: dict[str, Decimal]) -> Decimal:
    return evaluate_expression(
        formula.expression,
        values=values,
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )


@pytest.mark.parametrize(
    "target,inputs,expected",
    [
        (
            "38",
            {
                "161": 1,
                "173": 2,
                "03": 3,
                "164": 4,
                "06": 5,
                "09": 6,
                "11": -7,
                "152": 8,
                "167": 9,
                "14": 10,
                "155": 11,
                "17": 12,
                "20": 13,
                "22": 14,
                "24": 15,
                "26": -16,
                "158": 17,
                "170": 18,
                "29": 19,
                "32": 20,
                "35": 21,
                "37": -22,
            },
            163,
        ),
        (
            "62",
            {
                "40": 10,
                "42": 20,
                "44": -5,
                "46": 30,
                "48": 40,
                "50": 50,
                "52": 60,
                "54": 70,
                "56": 80,
                "58": -15,
                "59": 90,
                "60": -25,
                "61": 35,
            },
            440,
        ),
        ("63", {"38": 1000, "62": 300, "76": -50}, 650),
        ("65", {"63": 1000, "64": 75}, 750),
        ("65", {"63": -1000, "64": 100}, -1000),
        ("65", {"63": 1000, "64": 0}, 0),
        ("68", {"65": 650, "77": 120, "66": 200, "67": -30}, 540),
        ("70", {"68": 540, "69": 40, "112": 125}, 375),
        (
            "88",
            {
                "80": 1000,
                "81": 200,
                "93": 300,
                "94": 400,
                "83": 500,
                "84": 600,
                "125": 700,
                "126": 800,
                "127": 900,
                "128": 1100,
                "86": 1200,
                "95": 1300,
                "96": 1400,
                "97": 1500,
                "98": 1600,
                "79": 175,
                "99": 225,
            },
            13100,
        ),
        (
            "717",
            {"701": 10, "703": 20, "705": 30, "707": 40, "709": 50, "711": 60, "713": 70, "715": -15, "716": -25},
            240,
        ),
        (
            "735",
            {"719": 10, "721": 20, "723": 30, "725": 40, "727": 50, "729": 60, "731": 70, "733": -15, "734": -25},
            240,
        ),
    ],
)
@pytest.mark.parametrize("revision_id", ["2008-2022", "2023", "2024-2025", "2026-y-siguientes"])
def test_printed_total_uses_every_operand_and_refuses_missing_values(
    target: str, inputs: dict[str, int], expected: int, revision_id: str
) -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322"))
    revision = modelo.revisions[revision_id]
    inputs = dict(inputs)
    if target == "38" and revision_id in {"2008-2022", "2023"}:
        # The three later rate rows are absent from the January2023 paper form.
        for later_box in ("173", "167", "170"):
            expected -= inputs.pop(later_box)
        if revision_id == "2008-2022":
            for later_box in ("161", "164", "152", "155", "158"):
                expected -= inputs.pop(later_box)
    if target == "70" and revision_id != "2026-y-siguientes":
        # The advance-payment deduction first appears in the February2026 form.
        expected += inputs.pop("112")
    formula = next(f for f in revision.formulas if f.target_casilla_id == target)
    values = {key: Decimal(value) for key, value in inputs.items()}
    assert _evaluate(formula, values) == Decimal(expected)
    owner = next(c for c in revision.casillas if c.id == target)
    assert owner.input_kind == "computed"
    assert owner.formula == formula.id
    assert {
        "2008-2022": "boe-modelo-322-2021-form-pdf",
        "2023": "boe-modelo-322-2023-form-pdf",
        "2024-2025": "boe-modelo-322-2024-form-pdf",
        "2026-y-siguientes": "boe-modelo-390-2026-form",
    }[revision_id] in formula.source_refs
    for missing in inputs:
        with pytest.raises(RegistryValidationError, match="referenced before evaluation"):
            _evaluate(formula, {key: value for key, value in values.items() if key != missing})

"""Country matching must use declared text, never a monetary channel."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_formulas import validate_text_comparison_operands

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("numeric", [False, True])
def test_text_comparison_validates_actual_registry_channel(numeric):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]
    channel = "decimal" if numeric else "text"
    binding = next(item for item in revision.bindings if item.value.channel == channel)
    expression = FormulaExpression(op="text_equal", args=(FormulaExpression(binding=binding.id),) * 2)
    formula = revision.formulas[0].model_copy(update={"expression": expression})
    failures = validate_text_comparison_operands("test", formula, revision=revision)
    assert bool(failures) is numeric


@pytest.mark.parametrize("numeric", [False, True])
def test_literal_comparison_still_checks_the_other_operand_channel(numeric):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]
    binding = next(item for item in revision.bindings if item.value.channel == ("decimal" if numeric else "text"))
    expression = FormulaExpression(
        op="text_equal", args=(FormulaExpression(binding=binding.id), FormulaExpression(text_literal="DE"))
    )
    formula = revision.formulas[0].model_copy(update={"expression": expression})
    assert bool(validate_text_comparison_operands("test", formula, revision=revision)) is numeric


@pytest.mark.parametrize("nested", [False, True])
def test_compiler_refuses_text_literal_as_numeric_formula_result(nested):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]
    expression = FormulaExpression(text_literal="19")
    if nested:
        expression = FormulaExpression.model_construct(op="sum", args=(expression,))
    formula = revision.formulas[0].model_copy(update={"expression": expression})
    failures = validate_text_comparison_operands("test", formula, revision=revision)
    assert len(failures) == 1
    assert "text_literal may only be an operand of text_equal" in failures[0]

"""A row-absence predicate must refer to a declared fixed-record slot."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_formulas import validate_record_row_operands

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("kind", ["record", "unknown", "nonrecord"])
def test_row_predicate_validates_nested_binding_ownership(kind):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]
    binding = next(
        binding
        for binding in revision.bindings
        if isinstance(binding.provider, ManualInputProvider) and binding.provider.record is not None
    )
    if kind == "nonrecord":
        binding = binding.model_copy(update={"provider": binding.provider.model_copy(update={"record": None})})
        revision = revision.model_copy(update={"bindings": (binding,)})
    expression = FormulaExpression(
        op="copy",
        args=(
            FormulaExpression(
                op="record_row_unused",
                args=(FormulaExpression(binding="unknown" if kind == "unknown" else binding.id),),
            ),
        ),
    )
    formula = revision.formulas[0].model_copy(update={"expression": expression})
    failures = validate_record_row_operands("test", formula, revision=revision)
    assert bool(failures) is (kind != "record")

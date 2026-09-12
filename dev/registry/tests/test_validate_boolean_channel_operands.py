"""Detector teeth for the boolean-channel arithmetic-operand refusal.

A binding whose value contract declares the boolean channel carries a truth
value. The evaluator projects it to ``1``/``0`` at the leaf, which is only
meaningful where a formula asks a yes/no question of it. Consumed under ``add``,
``multiply`` or ``subtract`` that same projection manufactures a filing-grade
quantity out of a fact with no magnitude, so the compiler refuses the
declaration before the revision can be published.

Each case provokes the refusal by editing a COPY of a converted modelo in a
temporary tree and compiling it through the mutable loader; the live corpus is
never touched and no production module is patched. The normal path is proved in
the same suite, because a fixture that stops refusing its own defect would also
stop refusing the corpus.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_formulas import validate_boolean_channel_operands

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

_MODELO = "131"
_REVISION = "2025"
_FORMULA_FRAGMENT = f"revisions/{_REVISION}/formulas/0001-formulas.toml"
_FORMULA_ID = "modelo-131-pago-fraccionado-sin-datos-base"
_BOOLEAN_BINDING = "modelo-131.page1.discapacidad-33"
_CASILLA = "03"
_AUTHORED_EXPRESSION = (
    'expression = { op = "percent", args = [{ casilla_id = "03" }, '
    '{ parameter = "irpf.objective_no_base_fractional_payment_rate" }] }'
)


def _copy_modelo(tmp_path: Path) -> Path:
    destination = tmp_path / _MODELO
    shutil.copytree(_MODELOS_ROOT / _MODELO, destination)
    return destination


def _rewrite_expression(tree: Path, new_expression: str) -> None:
    """Replace the authored formula expression in the copied fragment."""
    path = tree / _FORMULA_FRAGMENT
    text = path.read_text(encoding="utf-8")
    if text.count(_AUTHORED_EXPRESSION) != 1:
        message = (
            f"fixture edit is not unique: {_AUTHORED_EXPRESSION!r} appears {text.count(_AUTHORED_EXPRESSION)} times"
        )
        raise AssertionError(message)
    path.write_text(text.replace(_AUTHORED_EXPRESSION, new_expression), encoding="utf-8")


def _failures(tree: Path) -> list[str]:
    modelo = load_modelo_directory(tree)
    revision = modelo.revisions[_REVISION]
    formula = next(candidate for candidate in revision.formulas if candidate.id == _FORMULA_ID)
    return validate_boolean_channel_operands(f"{_MODELO}/{_REVISION}", formula, revision=revision)


def test_the_binding_under_test_really_declares_the_boolean_channel(tmp_path: Path) -> None:
    """Without this, every case below would pass for the wrong reason.

    The refusal keys off the binding's declared channel. Were the declaration to
    move to the Decimal channel, no case in this module would provoke anything
    and the suite would go quietly green while detecting nothing.
    """
    modelo = load_modelo_directory(_copy_modelo(tmp_path))
    binding = next(candidate for candidate in modelo.revisions[_REVISION].bindings if candidate.id == _BOOLEAN_BINDING)

    assert binding.value.channel is BindingValueChannel.BOOLEAN


def test_the_authored_formula_is_accepted_unedited(tmp_path: Path) -> None:
    """The published formula consumes no boolean binding and raises nothing."""
    assert _failures(_copy_modelo(tmp_path)) == []


def test_a_bare_boolean_leaf_as_the_whole_expression_is_accepted(tmp_path: Path) -> None:
    """The projection onto a yes/no casilla is legitimate and stays legitimate.

    The published corpus uses this shape -- Modelo 100 casilla 0245, "si el
    matrimonio ha estado vigente durante todo el ano" -- where 1/0 is the record
    design's own encoding of the answer rather than a quantity the registry
    invented. No operator consumes the leaf, so nothing reads it as an amount.
    """
    tree = _copy_modelo(tmp_path)
    _rewrite_expression(tree, f'expression = {{ binding = "{_BOOLEAN_BINDING}" }}')

    assert _failures(tree) == []


@pytest.mark.parametrize(
    ("operator", "argument_index"),
    [("equal", 0), ("equal", 1), ("if_then_else", 0)],
)
def test_predicate_positions_are_accepted(tmp_path: Path, operator: str, argument_index: int) -> None:
    """The two positions that ask a yes/no question of the binding stay legal."""
    operands = [f'{{ casilla_id = "{_CASILLA}" }}'] * 3
    operands[argument_index] = f'{{ binding = "{_BOOLEAN_BINDING}" }}'
    arity = 3 if operator == "if_then_else" else 2
    tree = _copy_modelo(tmp_path)
    _rewrite_expression(tree, f'expression = {{ op = "{operator}", args = [{", ".join(operands[:arity])}] }}')

    assert _failures(tree) == []


@pytest.mark.parametrize("operator", ["add", "multiply", "subtract", "min"])
def test_an_arithmetic_operand_is_refused(tmp_path: Path, operator: str) -> None:
    """A truth value summed, multiplied or subtracted is refused by name.

    The failure names the formula, the binding and the consuming position, so
    the author is sent to the declaration rather than to a filing that came out
    one euro high.
    """
    tree = _copy_modelo(tmp_path)
    _rewrite_expression(
        tree,
        f'expression = {{ op = "{operator}", args = [{{ casilla_id = "{_CASILLA}" }}, '
        f'{{ binding = "{_BOOLEAN_BINDING}" }}] }}',
    )

    failures = _failures(tree)

    assert len(failures) == 1
    assert _FORMULA_ID in failures[0]
    assert _BOOLEAN_BINDING in failures[0]
    assert f"{operator!r} argument 1" in failures[0]


def test_an_arithmetic_operand_nested_under_a_legal_predicate_is_still_refused(tmp_path: Path) -> None:
    """Depth does not launder the defect.

    A boolean binding buried inside the arithmetic that FEEDS an ``equal``
    comparison is consumed as a quantity just as surely as one at the top; the
    walk carries the consuming operator down with it rather than accepting any
    subtree of an allowed operator.
    """
    tree = _copy_modelo(tmp_path)
    _rewrite_expression(
        tree,
        'expression = { op = "equal", args = ['
        f'{{ op = "add", args = [{{ casilla_id = "{_CASILLA}" }}, {{ binding = "{_BOOLEAN_BINDING}" }}] }}, '
        f'{{ casilla_id = "{_CASILLA}" }}] }}',
    )

    failures = _failures(tree)

    assert len(failures) == 1
    assert "'add' argument 1" in failures[0]

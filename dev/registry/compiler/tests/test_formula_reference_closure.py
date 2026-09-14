"""Reference-closure checks for the binding operands of a formula expression.

A formula reads a binding through one of two leaves. ``binding`` carries the
decimal channel and ``date_binding`` carries a date-valued fact the
``age_at_year_end`` operator consumes; they are two leaves over ONE binding id
namespace, and the runtime populates each from that namespace separately. The
closure check therefore has to hold both to it: a ``date_binding`` naming an id
no binding declares is exactly as unresolvable as a ``binding`` one, and the
evaluator meets it as a missing date rather than as a refusal.

Built on real schema models in memory, so no committed registry file is read.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from ..validate_formulas import validate_formula_expression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DECLARED: BindingId = "renta-profile-taxpayer-birth-date"


def _age_expression(date_binding: BindingId) -> FormulaExpression:
    """Return the published ``age_at_year_end`` shape over one date-binding leaf."""
    return FormulaExpression(
        op="age_at_year_end",
        args=(FormulaExpression(date_binding=date_binding),),
    )


def test_a_declared_date_binding_operand_closes() -> None:
    """The positive path: the leaf names a binding the revision declares."""
    failures = validate_formula_expression(
        "modelo 100 revision 2025",
        "minimo-contribuyente",
        _age_expression(_DECLARED),
        casillas=set(),
        bindings={_DECLARED},
        parameters=set(),
    )

    assert failures == []


def test_an_unknown_date_binding_operand_is_refused() -> None:
    """Teeth: the leaf that used to be walked past now names itself in a failure."""
    failures = validate_formula_expression(
        "modelo 100 revision 2025",
        "minimo-contribuyente",
        _age_expression("renta-profile-taxpayer-birth-date-typo"),
        casillas=set(),
        bindings={_DECLARED},
        parameters=set(),
    )

    assert failures == [
        "modelo 100 revision 2025: formula 'minimo-contribuyente' references unknown date binding "
        "'renta-profile-taxpayer-birth-date-typo'",
    ]


def test_the_two_binding_leaves_are_held_to_one_namespace() -> None:
    """A decimal leaf and a date leaf naming the same unknown id both report."""
    expression = FormulaExpression(
        op="add",
        args=(
            FormulaExpression(binding="absent"),
            FormulaExpression(date_binding="absent"),
        ),
    )

    failures = validate_formula_expression(
        "modelo 100 revision 2025",
        "minimo-contribuyente",
        expression,
        casillas=set(),
        bindings={_DECLARED},
        parameters=set(),
    )

    assert len(failures) == 2
    assert any("unknown binding 'absent'" in failure for failure in failures)
    assert any("unknown date binding 'absent'" in failure for failure in failures)

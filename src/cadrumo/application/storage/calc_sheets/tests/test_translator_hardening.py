"""Hardening checks for calc-sheets formula translation errors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_revision

from .....domain.calculations.registry.schema_formula import FormulaExpression
from .._translator import TranslationError, translate_formula
from ..layout import plan_layout
from ..records import SheetCellAddress, TabName

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_layout():
    revision = published_revision("130", "2019-y-siguientes")
    return plan_layout(revision, bracket_filter_date=date(2025, 12, 31))


def test_text_comparison_uses_exact_and_refuses_blank_or_numeric_cells():
    layout = _m130_layout().model_copy(
        update={
            "binding_cells": {"country": SheetCellAddress.at(TabName.ENTRADAS, 10, 4)},
            "entradas_cells": {"destination": SheetCellAddress.at(TabName.ENTRADAS, 11, 4)},
        }
    )
    expression = FormulaExpression(
        op="text_equal",
        args=(
            FormulaExpression(binding="country"),
            FormulaExpression(casilla_id="destination"),
        ),
    )
    a, b = "'Entradas'!D10", "'Entradas'!D11"
    assert translate_formula(expression, layout=layout) == (
        f"IF(AND(ISTEXT({a}),ISTEXT({b}),LEN({a})>0,LEN({b})>0),IF(EXACT({a},{b}),1,0),NA())"
    )


@pytest.mark.parametrize("literal,quoted", [('a"b,c', '"a""b,c"'), ("=1+1", '"=1+1"'), ("DE", '"DE"')])
def test_text_literal_is_quoted_inside_the_existing_exact_comparison(literal, quoted):
    layout = _m130_layout()
    expression = FormulaExpression(
        op="text_equal", args=(FormulaExpression(text_literal=literal), FormulaExpression(casilla_id="01"))
    )
    reference = layout.entradas_cells["01"].qualified()
    assert translate_formula(expression, layout=layout) == (
        f"IF(AND(ISTEXT({quoted}),ISTEXT({reference}),LEN({quoted})>0,LEN({reference})>0),"
        f"IF(EXACT({quoted},{reference}),1,0),NA())"
    )


def test_numeric_translation_rejects_text_literals_even_when_schema_was_bypassed():
    text = FormulaExpression(text_literal="1")
    layout = _m130_layout()
    with pytest.raises(TranslationError):
        translate_formula(text, layout=layout)
    expression = FormulaExpression.model_construct(op="add", args=(text, FormulaExpression(literal=Decimal(1))))
    with pytest.raises(TranslationError):
        translate_formula(expression, layout=layout)
    assert translate_formula(FormulaExpression(literal=Decimal(1)), layout=layout) == "1"


def test_unsupported_translation_op_does_not_render_raw_op() -> None:
    unsupported_op = "irnr_resolve_tipo_gravamen"
    # The registry declares this op with an exact 5-arg contract; the args'
    # values are irrelevant here since the assertions below only exercise the
    # calc-sheets translator's op-name rejection, never the args themselves.
    expression = FormulaExpression(
        op=unsupported_op,
        args=tuple(FormulaExpression(literal=Decimal("1")) for _ in range(5)),
    )

    with pytest.raises(TranslationError) as raised:
        translate_formula(expression, layout=_m130_layout())

    error = raised.value
    assert str(error) == "formula expression cannot be translated to a spreadsheet formula"
    assert unsupported_op not in str(error)
    assert unsupported_op not in str(error.context)
    assert error.context == {"reason": "formula_translation_failed", "unsupported_op": True}
    assert error.op is None
    assert error.translated_message == "application.storage.calc_sheets.translator.errors.translation_failed"


def test_missing_parameter_anchor_does_not_render_raw_parameter_id() -> None:
    sensitive_parameter = "private-parameter-token"
    expression = FormulaExpression(parameter=sensitive_parameter)

    with pytest.raises(TranslationError) as raised:
        translate_formula(expression, layout=_m130_layout())

    error = raised.value
    assert str(error) == "formula expression cannot be translated to a spreadsheet formula"
    assert sensitive_parameter not in str(error)
    assert sensitive_parameter not in str(error.context)
    assert error.context == {"reason": "formula_translation_failed"}
    assert error.op is None
    assert error.translated_message == "application.storage.calc_sheets.translator.errors.translation_failed"

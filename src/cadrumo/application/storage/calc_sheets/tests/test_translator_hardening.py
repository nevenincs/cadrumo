"""Hardening checks for calc-sheets formula translation errors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from cadrumo.domain.calculations.registry.schema import FormulaExpression
from .._layout import plan_layout
from .._translator import TranslationError, translate_formula

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_layout():
    revision = resources().modelos.get("130").revisions["2019-y-siguientes"]
    return plan_layout(revision, bracket_filter_date=date(2025, 12, 31))


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

"""Declared transient money operand and its exact operation lifetime."""

from __future__ import annotations

from datetime import timedelta

from ..operations.financial_operand import OperationTransientFinancialOperandDeclaration
from .edit_value_grammar import MONEY_OPERAND_MAXIMUM

MODELO_EDIT_MANUAL_OVERRIDE_OPERAND_KIND = "modelo.edit.manual_casilla_override"


#: Declared but not yet reachable from inside the executor: the manual
#: override amount already crosses fully typed and pre-admitted as part of
#: ModeloEditSubmissionV1 (the Edit Contract admission phase already
#: validated it), so nothing here asks the operator for it mid-flight today.
#: The declaration documents the operand this family is defined over and lets
#: a future mid-flight ask enroll under it. The broker side is reachable:
#: OperationExecutorContext exposes a financial_operand accessor, so an
#: executor that needs a mid-flight amount can ask for one under this kind.
MODELO_EDIT_MANUAL_OVERRIDE_OPERAND = OperationTransientFinancialOperandDeclaration(
    operand_kind=MODELO_EDIT_MANUAL_OVERRIDE_OPERAND_KIND,
    currency="EUR",
    scale=2,
    minimum=-MONEY_OPERAND_MAXIMUM,
    maximum=MONEY_OPERAND_MAXIMUM,
    lifetime=timedelta(minutes=5),
)

"""Deterministic, sandboxed formula evaluator.

Public surface: :class:`Engine` with two methods —

* :meth:`Engine.derive` — forward evaluation of every computed casilla
  in the ruleset, producing a :class:`ComputationLedger`.
* :meth:`Engine.audit_against` — reverse evaluation comparing a caller-
  supplied value set against a freshly-derived ledger, emitting a
  :class:`AuditReport` with any :class:`Discrepancy` records.

Both modes treat missing user-input casillas as ``Decimal('0')`` per
AEAT Instrucciones (a blank Modelo 130 casilla equals zero).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from ..errors import CasillaNotDefinedError, EvaluationError
from ..logging import get_logger
from ._codes import FormulaOp
from ._formula import (
    AddFormula,
    BracketsFormula,
    CasillaRef,
    ClampPositiveFormula,
    DivFormula,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
    iter_casilla_refs,
)
from ._ledger import AuditReport, ComputationLedger, Discrepancy, LedgerEntry
from ._ruleset import Ruleset

__all__ = ["Engine"]

_log = get_logger(__name__)

_ZERO = Decimal("0")
_DEFAULT_TOLERANCE = Decimal("0.01")


class Engine:
    """Stateless evaluator for a :class:`Ruleset`."""

    def derive(
        self,
        *,
        ruleset: Ruleset,
        inputs: Mapping[str, Decimal],
    ) -> ComputationLedger:
        """Evaluate every computed casilla using the supplied inputs."""
        self._reject_non_decimal(inputs)
        self._reject_unknown(ruleset, inputs.keys())

        values: dict[str, Decimal] = {}
        for casilla in ruleset.casillas:
            if not casilla.computed:
                if casilla.casilla_id in inputs:
                    values[casilla.casilla_id] = inputs[casilla.casilla_id]
                else:
                    values[casilla.casilla_id] = _ZERO
                    _log.debug(
                        "ruleset=%s casilla=%s defaulted to 0 (missing-input contract)",
                        ruleset.ruleset_id,
                        casilla.casilla_id,
                    )

        entries: list[LedgerEntry] = []
        on_date = ruleset.effective_from

        with localcontext() as ctx:
            ctx.prec = 28
            for casilla_id in ruleset.evaluation_order():
                formula_def = ruleset.formula_for(casilla_id)
                if formula_def is None:
                    continue
                try:
                    value = self._evaluate_operand(
                        formula_def.formula,
                        values=values,
                        ruleset=ruleset,
                        on_date=on_date,
                    )
                except (ArithmeticError, ValueError) as exc:
                    raise EvaluationError(f"ruleset={ruleset.ruleset_id} casilla={casilla_id}: {exc}") from exc

                values[casilla_id] = value
                refs = tuple(iter_casilla_refs(formula_def.formula))
                ref_values = tuple(values[ref] for ref in refs if ref in values)
                entry = LedgerEntry(
                    casilla_id=casilla_id,
                    value=value,
                    op=FormulaOp(formula_def.formula.op),
                    formula_id=formula_def.formula_id,
                    operand_refs=refs,
                    operand_values=ref_values,
                    ruleset_id=ruleset.ruleset_id,
                )
                entries.append(entry)

        ledger = ComputationLedger(
            ruleset_id=ruleset.ruleset_id,
            entries=tuple(entries),
        )
        _log.info(
            "derived ruleset=%s entries=%d",
            ruleset.ruleset_id,
            len(ledger.entries),
        )
        return ledger

    def audit_against(
        self,
        *,
        ruleset: Ruleset,
        provided: Mapping[str, Decimal],
        tolerance: Decimal = _DEFAULT_TOLERANCE,
    ) -> AuditReport:
        """Recompute and compare against caller-supplied values."""
        if tolerance < _ZERO:
            raise ValueError("tolerance must be non-negative")

        user_inputs = {
            casilla.casilla_id: provided[casilla.casilla_id]
            for casilla in ruleset.casillas
            if not casilla.computed and casilla.casilla_id in provided
        }
        ledger = self.derive(ruleset=ruleset, inputs=user_inputs)

        discrepancies: list[Discrepancy] = []
        for entry in ledger.entries:
            if entry.casilla_id not in provided:
                continue
            user_value = provided[entry.casilla_id]
            delta = user_value - entry.value
            if abs(delta) > tolerance:
                discrepancies.append(
                    Discrepancy(
                        casilla_id=entry.casilla_id,
                        user_value=user_value,
                        computed_value=entry.value,
                        delta=delta,
                        formula_id=entry.formula_id,
                        contributing_casillas=entry.operand_refs,
                        ruleset_id=entry.ruleset_id,
                    )
                )
        return AuditReport(ledger=ledger, discrepancies=tuple(discrepancies))

    # -- internal helpers --------------------------------------------

    def _reject_non_decimal(self, inputs: Mapping[str, Any]) -> None:
        for name, value in inputs.items():
            if isinstance(value, bool) or not isinstance(value, Decimal):
                raise ValueError(f"input {name!r} must be a Decimal instance; got {type(value).__name__}")

    def _reject_unknown(self, ruleset: Ruleset, keys: Iterable[str]) -> None:
        declared = {casilla.casilla_id for casilla in ruleset.casillas}
        for name in keys:
            if name not in declared:
                raise CasillaNotDefinedError(f"ruleset={ruleset.ruleset_id} does not declare casilla {name!r}")

    def _evaluate_operand(
        self,
        operand: object,
        *,
        values: Mapping[str, Decimal],
        ruleset: Ruleset,
        on_date: Any,
    ) -> Decimal:
        if isinstance(operand, Literal):
            return operand.value
        if isinstance(operand, CasillaRef):
            if operand.casilla_id not in values:
                raise EvaluationError(f"casilla {operand.casilla_id!r} referenced before evaluation")
            return values[operand.casilla_id]
        if isinstance(operand, ParamRef):
            return ruleset.parameters.resolve(operand.param_id, on=on_date)

        if isinstance(operand, AddFormula):
            result = _ZERO
            for child in operand.operands:
                result = result + self._evaluate_operand(child, values=values, ruleset=ruleset, on_date=on_date)
            return result
        if isinstance(operand, SubFormula):
            lhs_val = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            rhs_val = self._evaluate_operand(operand.operands[1], values=values, ruleset=ruleset, on_date=on_date)
            return lhs_val - rhs_val
        if isinstance(operand, MulFormula):
            result = Decimal("1")
            for child in operand.operands:
                result = result * self._evaluate_operand(child, values=values, ruleset=ruleset, on_date=on_date)
            return result
        if isinstance(operand, DivFormula):
            num = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            den = self._evaluate_operand(operand.operands[1], values=values, ruleset=ruleset, on_date=on_date)
            if den == _ZERO:
                raise EvaluationError("division by zero")
            return (num / den).quantize(operand.quantize)
        if isinstance(operand, MinFormula):
            evaluated = [
                self._evaluate_operand(child, values=values, ruleset=ruleset, on_date=on_date)
                for child in operand.operands
            ]
            return min(evaluated)
        if isinstance(operand, MaxFormula):
            evaluated = [
                self._evaluate_operand(child, values=values, ruleset=ruleset, on_date=on_date)
                for child in operand.operands
            ]
            return max(evaluated)
        if isinstance(operand, ClampPositiveFormula):
            inner = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            return inner if inner > _ZERO else _ZERO
        if isinstance(operand, PercentFormula):
            rate = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            base = self._evaluate_operand(operand.operands[1], values=values, ruleset=ruleset, on_date=on_date)
            return rate * base
        if isinstance(operand, BracketsFormula):
            probe = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            for bracket in operand.brackets:
                if bracket.upper_inclusive is None or probe <= bracket.upper_inclusive:
                    return bracket.value
            raise EvaluationError("brackets exhausted without a match")
        if isinstance(operand, RoundFormula):
            inner = self._evaluate_operand(operand.operands[0], values=values, ruleset=ruleset, on_date=on_date)
            quantum = Decimal("1").scaleb(-operand.digits)
            return inner.quantize(quantum, rounding=ROUND_HALF_UP)

        raise EvaluationError(f"unsupported operand {type(operand).__name__}")

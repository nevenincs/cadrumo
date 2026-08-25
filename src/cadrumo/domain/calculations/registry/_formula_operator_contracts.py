"""Canonical arity contracts for registry formula operators.

The registry schema and calculation runtime consume the same table so an
operator cannot be accepted by the authored authority with a shape the runtime
will later refuse.  Leaf-kind requirements remain with the specialised runtime
evaluators; this module owns the operator-wide argument-count contract only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .errors import RegistryValidationError
from ._schema_base import FormulaOperator

__all__ = ["FORMULA_OPERATOR_ARITIES", "FormulaOperatorArity", "require_formula_operator_arity"]


@dataclass(frozen=True, slots=True)
class FormulaOperatorArity:
    """Inclusive argument-count bounds for one formula operator."""

    minimum: int
    maximum: int | None = None

    def accepts(self, count: int) -> bool:
        """Return whether ``count`` satisfies these bounds."""
        return count >= self.minimum and (self.maximum is None or count <= self.maximum)


def _exact(count: int) -> FormulaOperatorArity:
    return FormulaOperatorArity(minimum=count, maximum=count)


_ONE_OR_MORE = FormulaOperatorArity(minimum=1)
_UNARY = _exact(1)
_BINARY = _exact(2)
_TERNARY = _exact(3)


FORMULA_OPERATOR_ARITIES: Final[dict[FormulaOperator, FormulaOperatorArity]] = {
    "add": _ONE_OR_MORE,
    "subtract": _BINARY,
    "multiply": _ONE_OR_MORE,
    "divide": _BINARY,
    "percent": _BINARY,
    "less_than": _BINARY,
    "less_equal": _BINARY,
    "greater_than": _BINARY,
    "greater_equal": _BINARY,
    "equal": _BINARY,
    "sum": _ONE_OR_MORE,
    "min": _ONE_OR_MORE,
    "max": _ONE_OR_MORE,
    "clamp": _TERNARY,
    "negate": _UNARY,
    "copy": _UNARY,
    "if_then_else": _TERNARY,
    "lookup_parameter": _UNARY,
    "lookup_bracket": _BINARY,
    "lookup_bracket_by_ccaa": _TERNARY,
    "m100_resolve_renta_inmobiliaria_imputada": _exact(9),
    "irnr_resolve_tipo_gravamen": _exact(5),
    "m210_resolve_base_imponible": _exact(12),
    "lookup_parameter_by_entity_type": _TERNARY,
    "lookup_bracket_by_entity_type": _TERNARY,
    "previous_period_value": _UNARY,
    "previous_period_sum": _ONE_OR_MORE,
    "cross_model_sum": _UNARY,
    "age_at_year_end": _UNARY,
    "m131_resolve_modulos_previo": _exact(9),
    "m131_resolve_modulos_minoracion_empleo": _exact(6),
    "m131_resolve_modulos_indice_exceso": _exact(4),
    "m131_resolve_modulos_indices_generales": _exact(7),
    "m131_resolve_modulos_pequena_dimension_ignorado_flag": _BINARY,
    "m131_resolve_modulos_temporada_inicio_conflicto_flag": _BINARY,
    "m100_resolve_eo_agraria_indices_correctores": _exact(9),
}


def require_formula_operator_arity(op: str, count: int) -> None:
    """Refuse an argument count outside the canonical contract for ``op``."""
    if op not in FORMULA_OPERATOR_ARITIES:
        raise RegistryValidationError(f"formula expression uses unsupported op {op!r}")
    contract = FORMULA_OPERATOR_ARITIES[op]
    if contract.accepts(count):
        return
    if contract.maximum == contract.minimum:
        expectation = f"{contract.minimum} arg" + ("s" if contract.minimum != 1 else "")
    elif contract.maximum is None:
        expectation = f"at least {contract.minimum} arg" + ("s" if contract.minimum != 1 else "")
    else:
        expectation = f"{contract.minimum}..{contract.maximum} args"
    raise RegistryValidationError(f"formula op {op!r} expects {expectation}, got {count}")

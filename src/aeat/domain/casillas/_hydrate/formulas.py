from decimal import Decimal
from aeat.domain.formulas._formula import (
    AddFormula,
    BracketsFormula,
    ClampPositiveFormula,
    DivFormula,
    FormulaCasillaRef,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
)

def _format_decimal(value: Decimal) -> str:
    s = format(value.normalize(), "f")
    if "." in s and "e" not in s.lower():
        s = s.rstrip("0").rstrip(".")
    return s or "0"

def _render_param_value(param_id: str, params: dict[str, Decimal] | None) -> str:
    if not params or param_id not in params:
        return param_id
    value = params[param_id]
    if Decimal("0") < value < Decimal("1") and abs(value) >= Decimal("0.0001"):
        pct = value * Decimal(100)
        return f"{_format_decimal(pct)}%"
    return _format_decimal(value)

def _render_operand(node: object, *, params: dict[str, Decimal] | None = None) -> str:
    if isinstance(node, FormulaCasillaRef):
        return node.casilla_id
    if isinstance(node, Literal):
        v = node.value
        if isinstance(v, Decimal):
            return _format_decimal(v)
        return str(v)
    if isinstance(node, ParamRef):
        return _render_param_value(node.param_id, params)
    if isinstance(node, RoundFormula):
        return _render_operand(node.operands[0], params=params)
    if isinstance(node, AddFormula):
        return "(" + " + ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, SubFormula):
        return (
            "("
            + _render_operand(node.operands[0], params=params)
            + " - "
            + _render_operand(node.operands[1], params=params)
            + ")"
        )
    if isinstance(node, MulFormula):
        return "(" + " * ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, DivFormula):
        return (
            "("
            + _render_operand(node.operands[0], params=params)
            + " / "
            + _render_operand(node.operands[1], params=params)
            + ")"
        )
    if isinstance(node, MaxFormula):
        return "max(" + ", ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, MinFormula):
        return "min(" + ", ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, ClampPositiveFormula):
        return "max(0, " + _render_operand(node.operands[0], params=params) + ")"
    if isinstance(node, PercentFormula):
        rate, base = node.operands
        return "(" + _render_operand(rate, params=params) + " * " + _render_operand(base, params=params) + ")"
    if isinstance(node, BracketsFormula):
        return "brackets(" + _render_operand(node.operands[0], params=params) + ")"
    return repr(node)

def _collect_casilla_refs(node: object) -> list[str]:
    seen: list[str] = []
    def walk(n: object) -> None:
        if isinstance(n, FormulaCasillaRef):
            if n.casilla_id not in seen:
                seen.append(n.casilla_id)
            return
        operands = getattr(n, "operands", None)
        if operands is not None:
            for op in operands:
                walk(op)
    walk(node)
    return seen

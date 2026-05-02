"""Discriminated-union pydantic models for every formula node.

The :class:`aeat.domain.formulas.Engine` never evaluates strings. Every
node is a pydantic v2 model tagged by
:class:`aeat.domain.formulas.FormulaOp`. The public :data:`Operand` alias
covers the four possible operands of a formula: a decimal literal, a
casilla reference, a parameter reference, or a nested formula.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from typing import Literal as TLiteral

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)


def _coerce_decimal(value: Any) -> Any:
    """Reject floats and coerce ints / strings to :class:`decimal.Decimal`.

    Floats are rejected because their binary representation is lossy for
    monetary literals (e.g. ``0.1``). Callers must supply ``"0.1"`` as a
    string or a :class:`decimal.Decimal` instance.

    Args:
        value: Candidate value coming through pydantic validation.

    Returns:
        Either the original :class:`decimal.Decimal`, or a freshly
        constructed one. Other types are returned untouched so the
        downstream :class:`pydantic.ValidationError` carries a precise
        message.

    Raises:
        ValueError: When ``value`` is a :class:`bool` or :class:`float`.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid Decimal literal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, float):
        raise ValueError("float literals are forbidden; pass a string or Decimal instance")
    return value


_DecimalField = Annotated[Decimal, BeforeValidator(_coerce_decimal)]


class _FormulaStrictFrozenModel(BaseModel):
    """Shared base for every formula-node model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


# -- Leaf operands --------------------------------------------------------


class Literal(_FormulaStrictFrozenModel):
    """A decimal literal inside a formula."""

    op: TLiteral["literal"] = "literal"
    value: _DecimalField


class FormulaCasillaRef(_FormulaStrictFrozenModel):
    """Reference to another casilla's value inside the current evaluation."""

    op: TLiteral["casilla_ref"] = "casilla_ref"
    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]


class ParamRef(_FormulaStrictFrozenModel):
    """Reference to a named parameter in the ruleset's parameter table."""

    op: TLiteral["param_ref"] = "param_ref"
    param_id: Annotated[str, Field(min_length=1, max_length=128)]


# -- Compound operators ---------------------------------------------------


class AddFormula(_FormulaStrictFrozenModel):
    """N-ary addition."""

    op: TLiteral["add"] = "add"
    operands: tuple[Operand, ...] = Field(min_length=2)


class SubFormula(_FormulaStrictFrozenModel):
    """Binary subtraction (``a - b``)."""

    op: TLiteral["sub"] = "sub"
    operands: tuple[Operand, Operand]


class MulFormula(_FormulaStrictFrozenModel):
    """N-ary multiplication."""

    op: TLiteral["mul"] = "mul"
    operands: tuple[Operand, ...] = Field(min_length=2)


class DivFormula(_FormulaStrictFrozenModel):
    """Binary division with an explicit quantize to cap precision."""

    op: TLiteral["div"] = "div"
    operands: tuple[Operand, Operand]
    quantize: _DecimalField = Decimal("0.0001")


class MinFormula(_FormulaStrictFrozenModel):
    """N-ary minimum."""

    op: TLiteral["min"] = "min"
    operands: tuple[Operand, ...] = Field(min_length=2)


class MaxFormula(_FormulaStrictFrozenModel):
    """N-ary maximum."""

    op: TLiteral["max"] = "max"
    operands: tuple[Operand, ...] = Field(min_length=2)


class ClampPositiveFormula(_FormulaStrictFrozenModel):
    """Unary ``max(0, x)`` clamp."""

    op: TLiteral["clamp_positive"] = "clamp_positive"
    operands: tuple[Operand]


class PercentFormula(_FormulaStrictFrozenModel):
    """Binary ``rate x base`` (both Decimal)."""

    op: TLiteral["percent"] = "percent"
    operands: tuple[Operand, Operand]


class Bracket(_FormulaStrictFrozenModel):
    """One bracket in a :class:`BracketsFormula` step function."""

    upper_inclusive: _DecimalField | None = None
    value: _DecimalField


class BracketsFormula(_FormulaStrictFrozenModel):
    """Step function over a single operand.

    Walks ``brackets`` in order; the first bracket whose
    ``upper_inclusive`` is ``None`` or ``>= operand_value`` applies.
    Brackets must be ordered ascending by ``upper_inclusive`` with
    exactly one terminal ``None`` bracket as the default.
    """

    op: TLiteral["brackets"] = "brackets"
    operands: tuple[Operand]
    brackets: tuple[Bracket, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_brackets(self) -> BracketsFormula:
        tail = self.brackets[-1]
        if tail.upper_inclusive is not None:
            raise ValueError("final bracket must have upper_inclusive=None (default tier)")
        for idx, bracket in enumerate(self.brackets[:-1]):
            if bracket.upper_inclusive is None:
                raise ValueError(f"non-terminal bracket {idx} must declare upper_inclusive")
            if idx > 0:
                previous = self.brackets[idx - 1]
                if previous.upper_inclusive is None or previous.upper_inclusive >= bracket.upper_inclusive:
                    raise ValueError("brackets must be strictly ascending by upper_inclusive")
        return self


class RoundFormula(_FormulaStrictFrozenModel):
    """Terminal rounding to a declared precision.

    The engine enforces that no :class:`RoundFormula` contains another
    :class:`RoundFormula` anywhere in its operand tree — the
    single-rounding invariant.
    """

    op: TLiteral["round"] = "round"
    operands: tuple[Operand]
    digits: Annotated[int, Field(ge=0, le=6)] = 2
    rounding: TLiteral["ROUND_HALF_UP"] = "ROUND_HALF_UP"

    @model_validator(mode="after")
    def _reject_nested_round(self) -> RoundFormula:
        if _contains_round(self.operands[0]):
            raise ValueError("RoundFormula may not contain another RoundFormula (single-rounding invariant)")
        return self


Formula = Annotated[
    AddFormula
    | SubFormula
    | MulFormula
    | DivFormula
    | MinFormula
    | MaxFormula
    | ClampPositiveFormula
    | PercentFormula
    | BracketsFormula
    | RoundFormula,
    Field(discriminator="op"),
]


Operand = Annotated[
    Literal
    | FormulaCasillaRef
    | ParamRef
    | AddFormula
    | SubFormula
    | MulFormula
    | DivFormula
    | MinFormula
    | MaxFormula
    | ClampPositiveFormula
    | PercentFormula
    | BracketsFormula
    | RoundFormula,
    Field(discriminator="op"),
]


_CompoundFormula = (
    AddFormula
    | SubFormula
    | MulFormula
    | DivFormula
    | MinFormula
    | MaxFormula
    | ClampPositiveFormula
    | PercentFormula
    | BracketsFormula
    | RoundFormula
)


def _is_compound(operand: object) -> bool:
    """Return ``True`` when ``operand`` is a compound-operator formula node."""
    return isinstance(
        operand,
        (
            AddFormula,
            SubFormula,
            MulFormula,
            DivFormula,
            MinFormula,
            MaxFormula,
            ClampPositiveFormula,
            PercentFormula,
            BracketsFormula,
            RoundFormula,
        ),
    )


def _compound_operands(operand: object) -> tuple[object, ...]:
    """Return the operand tuple of a compound formula node."""
    if isinstance(
        operand,
        (
            AddFormula,
            SubFormula,
            MulFormula,
            DivFormula,
            MinFormula,
            MaxFormula,
            ClampPositiveFormula,
            PercentFormula,
            BracketsFormula,
            RoundFormula,
        ),
    ):
        return tuple(operand.operands)
    return ()


def _contains_round(operand: object) -> bool:
    """Return ``True`` if ``operand`` contains a :class:`RoundFormula`."""
    if isinstance(operand, RoundFormula):
        return True
    if _is_compound(operand):
        for child in _compound_operands(operand):
            if _contains_round(child):
                return True
    return False


class FormulaDefinition(_FormulaStrictFrozenModel):
    """Binding of a computed casilla to the formula that derives it."""

    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]
    formula_id: Annotated[str, Field(min_length=1, max_length=128)]
    formula: Formula


# -- Traversal helpers (used by :mod:`_ruleset` for invariant checks) ----


def iter_casilla_refs(operand: object) -> list[str]:
    """Collect every :class:`FormulaCasillaRef.casilla_id` in ``operand``."""
    refs: list[str] = []
    _collect_casilla_refs(operand, refs)
    return refs


def _collect_casilla_refs(operand: object, into: list[str]) -> None:
    if isinstance(operand, FormulaCasillaRef):
        into.append(operand.casilla_id)
        return
    if _is_compound(operand):
        for child in _compound_operands(operand):
            _collect_casilla_refs(child, into)


def iter_param_refs(operand: object) -> list[str]:
    """Collect every :class:`ParamRef.param_id` in ``operand``."""
    refs: list[str] = []
    _collect_param_refs(operand, refs)
    return refs


def _collect_param_refs(operand: object, into: list[str]) -> None:
    if isinstance(operand, ParamRef):
        into.append(operand.param_id)
        return
    if _is_compound(operand):
        for child in _compound_operands(operand):
            _collect_param_refs(child, into)


# Rebuild forward references so pydantic resolves the self-referential
# Operand union before external code constructs a model.
AddFormula.model_rebuild()
SubFormula.model_rebuild()
MulFormula.model_rebuild()
DivFormula.model_rebuild()
MinFormula.model_rebuild()
MaxFormula.model_rebuild()
ClampPositiveFormula.model_rebuild()
PercentFormula.model_rebuild()
BracketsFormula.model_rebuild()
RoundFormula.model_rebuild()
FormulaDefinition.model_rebuild()

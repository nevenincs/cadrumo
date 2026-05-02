"""Closed enumerations for the :mod:`aeat.domain.formulas` engine.

Declares two enums:

* :class:`FormulaOp` — the fixed set of operator tags used by every
  pydantic formula node. The set is deliberately minimal so the engine's
  audit and attack surface stays small; new operators require a design
  review before they land.
* :class:`Quarter` — fiscal quarter identifiers used by
  :class:`aeat.domain.formulas.FiscalPeriod`.
"""

from __future__ import annotations

from enum import StrEnum


class FormulaOp(StrEnum):
    """Operator tags for pydantic formula nodes.

    Thirteen members total. Adding operators expands the engine's audit
    and attack surface and so requires an explicit design review.

    Attributes:
        LITERAL: Decimal literal leaf.
        CASILLA_REF: Reference to another casilla in the same evaluation.
        PARAM_REF: Reference to a named parameter table entry.
        ADD: N-ary addition.
        SUB: Binary subtraction.
        MUL: N-ary multiplication.
        DIV: Binary division with explicit quantize.
        MIN: N-ary minimum.
        MAX: N-ary maximum.
        CLAMP_POSITIVE: Unary ``max(0, x)``.
        PERCENT: Binary ``rate * base``.
        BRACKETS: Step function over a single operand.
        ROUND: Terminal rounding to a declared precision.
    """

    LITERAL = "literal"
    CASILLA_REF = "casilla_ref"
    PARAM_REF = "param_ref"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MIN = "min"
    MAX = "max"
    CLAMP_POSITIVE = "clamp_positive"
    PERCENT = "percent"
    BRACKETS = "brackets"
    ROUND = "round"


class Quarter(StrEnum):
    """Fiscal quarter identifiers matching AEAT's trimester labels.

    Attributes:
        Q1: January through March.
        Q2: April through June.
        Q3: July through September.
        Q4: October through December.
    """

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

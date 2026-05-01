"""Closed enumerations for the :mod:`aeat.domain.formulas` engine.

Declares two enums:

* :class:`FormulaOp` — the fixed set of operator tags used by every
  pydantic formula node. The set is deliberately minimal — only the
  operators that the Modelo 130 DAG requires are present.
  New operators are added in a future wave behind a fresh ADR.
* :class:`Quarter` — fiscal quarter identifiers used by
  :class:`aeat.domain.formulas.FiscalPeriod`.
"""

from __future__ import annotations

from enum import StrEnum


class FormulaOp(StrEnum):
    """Operator tags for pydantic formula nodes.

    Thirteen members total. Adding operators requires an ADR because
    each expands the engine's audit and attack surface.
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
    """Fiscal quarter identifiers matching AEAT's trimester labels."""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

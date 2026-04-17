"""Per-modelo calculation formula engine (#173).

Public API surface for the deterministic, sandboxed, period-aware
tax-formula engine. See the ADR at
``.vault/adr/2026-04-17-modelo-formulas-adr.md`` for the design
rationale. The implementation ships Modelo 130 (2024 and 2025)
as the proof-of-concept ruleset; future waves extend to Modelo
303 / 100 / 390 / ...
"""

from __future__ import annotations

from ..errors import (
    AmbiguousPeriodError,
    AuditDiscrepancyError,
    CasillaNotDefinedError,
    EvaluationError,
    FormulaCycleError,
    FormulasError,
    MissingRulesetError,
    RulesetValidationError,
)
from ._casilla import CasillaDefinition
from ._codes import FormulaOp, Quarter
from ._engine import Engine
from ._formula import (
    AddFormula,
    BracketsFormula,
    CasillaRef,
    ClampPositiveFormula,
    DivFormula,
    Formula,
    FormulaDefinition,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    Operand,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
)
from ._ledger import AuditReport, ComputationLedger, Discrepancy, LedgerEntry
from ._period import FiscalPeriod
from ._registry import RulesetRegistry, get_registry
from ._ruleset import Bracket, ParameterTable, ParameterValue, Ruleset

__all__ = [
    "AddFormula",
    "AmbiguousPeriodError",
    "AuditDiscrepancyError",
    "AuditReport",
    "Bracket",
    "BracketsFormula",
    "CasillaDefinition",
    "CasillaNotDefinedError",
    "CasillaRef",
    "ClampPositiveFormula",
    "ComputationLedger",
    "Discrepancy",
    "DivFormula",
    "Engine",
    "EvaluationError",
    "FiscalPeriod",
    "Formula",
    "FormulaCycleError",
    "FormulaDefinition",
    "FormulaOp",
    "FormulasError",
    "LedgerEntry",
    "Literal",
    "MaxFormula",
    "MinFormula",
    "MissingRulesetError",
    "MulFormula",
    "Operand",
    "ParamRef",
    "ParameterTable",
    "ParameterValue",
    "PercentFormula",
    "Quarter",
    "RoundFormula",
    "Ruleset",
    "RulesetRegistry",
    "RulesetValidationError",
    "SubFormula",
    "get_registry",
]

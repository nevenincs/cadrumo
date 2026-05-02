"""Per-modelo calculation formula engine.

Public API surface for the deterministic, sandboxed, period-aware tax-formula
engine. The engine evaluates pydantic-typed formula trees over a
period-versioned :class:`Ruleset`, producing a :class:`ComputationLedger` (or
an :class:`AuditReport` when comparing against caller-supplied values).

Key types:

- :class:`Engine` — stateless evaluator with ``derive`` and
  ``audit_against`` methods.
- :class:`Ruleset` — period-versioned bundle of casillas, formulas,
  parameters, and legal citations.
- :class:`RulesetRegistry` — lookup by ``(modelo, variant, period)``.
- :class:`FiscalPeriod` — closed period identifier.
"""

from __future__ import annotations

from ...core.errors import (
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
    ClampPositiveFormula,
    DivFormula,
    Formula,
    FormulaCasillaRef,
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
from ._rulesets import MODELO_100_SUMMARY_2025
from ._rulesets.modelo_100._amortization import LIS_ART_12_LINEAL_TABLE, AssetClass
from ._rulesets.modelo_100._ccaa import CCAA, compute_cuota_autonomica_general
from ._rulesets.modelo_100._inventario import ValuationMethod

__all__ = [
    "CCAA",
    "LIS_ART_12_LINEAL_TABLE",
    "MODELO_100_SUMMARY_2025",
    "AddFormula",
    "AmbiguousPeriodError",
    "AssetClass",
    "AuditDiscrepancyError",
    "AuditReport",
    "Bracket",
    "BracketsFormula",
    "CasillaDefinition",
    "CasillaNotDefinedError",
    "ClampPositiveFormula",
    "ComputationLedger",
    "Discrepancy",
    "DivFormula",
    "Engine",
    "EvaluationError",
    "FiscalPeriod",
    "Formula",
    "FormulaCasillaRef",
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
    "ValuationMethod",
    "compute_cuota_autonomica_general",
    "get_registry",
]

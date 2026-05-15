"""Schema-to-sheet engine that translates a `RegistrySnapshot` into a
Google Sheets workbook whose formulas evaluate, in Sheets, to the same
per-casilla rounded values that the local registry runtime produces.

The package exposes three layers:

- Records (`_records`) — strict frozen pydantic v2 types describing the
  workbook the engine intends to produce. The records are the shared
  vocabulary between the engine driver, the apply adapter, the parity
  oracle, and the pull adapter.
- Translator (`_translator`) — pure function that walks a registry
  `FormulaExpression` AST and emits a Sheets A1 formula string,
  resolving casilla references through the layout planner.
- Engine driver (`_engine`) — consumes a `RegistrySnapshot` plus a
  caller-supplied `OperatorInputs` payload and assembles a
  `SheetExportPlan` ready for the apply adapter.

Operator-facing CLI surface lives under
`src/aeat/entrypoints/cli/_config/_google.py`; this package contains
domain and application logic only.
"""

from ._engine import build_export_plan
from ._layout import BracketRanges, SheetLayout, plan_layout
from ._records import (
    OperatorInput,
    OperatorInputs,
    ParameterCell,
    RelationValue,
    RelationValues,
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetProtectedRange,
    SheetProvenanceRow,
    SheetTariffTable,
    SheetTariffTableRow,
    SheetValueCell,
    TabName,
)
from ._translator import TranslationError, translate_formula

__all__ = [
    "BracketRanges",
    "OperatorInput",
    "OperatorInputs",
    "ParameterCell",
    "RelationValue",
    "RelationValues",
    "SheetCellAddress",
    "SheetExportMetadata",
    "SheetExportPlan",
    "SheetFormulaCell",
    "SheetGuideContent",
    "SheetLayout",
    "SheetProtectedRange",
    "SheetProvenanceRow",
    "SheetTariffTable",
    "SheetTariffTableRow",
    "SheetValueCell",
    "TabName",
    "TranslationError",
    "build_export_plan",
    "plan_layout",
    "translate_formula",
]

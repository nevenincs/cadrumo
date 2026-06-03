"""Google Sheets export engine for modelo registry snapshots.

Translates a ``RegistrySnapshot`` into a workbook whose formulas produce the same per-casilla
rounded values as the local registry runtime.

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

from ._engine import build_export_plan, collect_row_sets, registry_sha
from ._evidence import sheet_evidence_from_ledger_filing
from ._layout import BracketRanges, SheetLayout, plan_layout
from ._records import (
    OperatorInput,
    OperatorInputs,
    ParameterCell,
    RelationValue,
    RelationValues,
    SheetCellAddress,
    SheetCellConstraint,
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetAnchor,
    SheetFormulaCell,
    SheetGuideContent,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetProvenanceRow,
    SheetSectionHeader,
    SheetRowSet,
    SheetRowSetColumn,
    SheetTariffTable,
    SheetTariffTableRow,
    SheetValueCell,
    TabName,
)
from ._translator import TranslationError, translate_formula
from ._workbook_export import (
    OfflineWorkbookEvidenceSidecar,
    OfflineWorkbookExportResult,
    build_evidence_sidecar,
    build_offline_workbook,
    evidence_table,
    serialize_evidence_sidecar,
    serialize_offline_export,
    serialize_offline_workbook,
)

__all__ = [
    "BracketRanges",
    "OfflineWorkbookEvidenceSidecar",
    "OfflineWorkbookExportResult",
    "OperatorInput",
    "OperatorInputs",
    "ParameterCell",
    "RelationValue",
    "RelationValues",
    "SheetCellAddress",
    "SheetCellConstraint",
    "SheetEvidenceContributorRow",
    "SheetEvidenceFacet",
    "SheetEvidenceManualEntry",
    "SheetExportMetadata",
    "SheetExportPlan",
    "SheetFormulaCell",
    "SheetGuideContent",
    "SheetLayout",
    "SheetAnchor",
    "SheetNumberFormat",
    "SheetSectionHeader",
    "SheetProtectedRange",
    "SheetProvenanceRow",
    "SheetRowSet",
    "SheetRowSetColumn",
    "SheetTariffTable",
    "SheetTariffTableRow",
    "SheetValueCell",
    "TabName",
    "TranslationError",
    "build_evidence_sidecar",
    "build_export_plan",
    "build_offline_workbook",
    "collect_row_sets",
    "evidence_table",
    "plan_layout",
    "registry_sha",
    "serialize_evidence_sidecar",
    "serialize_offline_export",
    "serialize_offline_workbook",
    "sheet_evidence_from_ledger_filing",
    "translate_formula",
]

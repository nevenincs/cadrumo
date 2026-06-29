"""Workbook export planning engine for modelo registry snapshots.

Translates a :class:`RegistrySnapshot` into a :class:`SheetExportPlan` whose
formulas produce the same per-casilla rounded values as the local registry
runtime. The plan is shared by the Google Sheets apply adapter and the offline
XLSX materializer, so layout, formulas, styling, provenance, and evidence stay
on one contract.

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
- Offline export (`_workbook_export`) — serializes the same plan into XLSX
  bytes plus the machine-readable evidence sidecar.

Operator-facing CLI surface lives under
`src/aeat/entrypoints/cli/_config/_google.py`; this package contains
domain and application logic only.

See Also:
    :class:`aeat.domain.calculations.registry.RegistrySnapshot`
        Registry-authored calculation surface compiled by the engine.
    :class:`SheetExportPlan`
        Shared workbook plan consumed by online and offline renderers.
    :func:`serialize_offline_export`
        Offline XLSX plus evidence-sidecar serializer for operator-directed
        exports.
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
    SheetAnchor,
    SheetAutoFilter,
    SheetCellAddress,
    SheetCellConstraint,
    SheetColumnWidth,
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetFrozenView,
    SheetGuideContent,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetProvenanceRow,
    SheetRowSet,
    SheetRowSetColumn,
    SheetSectionHeader,
    SheetStyledRange,
    SheetTariffTable,
    SheetTariffTableRow,
    SheetValueCell,
    TabName,
)
from ._theme import (
    ROLE_STYLES,
    WORKBOOK_FONT_FAMILY,
    RoleStyle,
    StyleRole,
    hex_to_rgb_floats,
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
    "ROLE_STYLES",
    "WORKBOOK_FONT_FAMILY",
    "BracketRanges",
    "OfflineWorkbookEvidenceSidecar",
    "OfflineWorkbookExportResult",
    "OperatorInput",
    "OperatorInputs",
    "ParameterCell",
    "RelationValue",
    "RelationValues",
    "RoleStyle",
    "SheetAnchor",
    "SheetAutoFilter",
    "SheetCellAddress",
    "SheetCellConstraint",
    "SheetColumnWidth",
    "SheetEvidenceContributorRow",
    "SheetEvidenceFacet",
    "SheetEvidenceManualEntry",
    "SheetExportMetadata",
    "SheetExportPlan",
    "SheetFormulaCell",
    "SheetFrozenView",
    "SheetGuideContent",
    "SheetLayout",
    "SheetNumberFormat",
    "SheetProtectedRange",
    "SheetProvenanceRow",
    "SheetRowSet",
    "SheetRowSetColumn",
    "SheetSectionHeader",
    "SheetStyledRange",
    "SheetTariffTable",
    "SheetTariffTableRow",
    "SheetValueCell",
    "StyleRole",
    "TabName",
    "TranslationError",
    "build_evidence_sidecar",
    "build_export_plan",
    "build_offline_workbook",
    "collect_row_sets",
    "evidence_table",
    "hex_to_rgb_floats",
    "plan_layout",
    "registry_sha",
    "serialize_evidence_sidecar",
    "serialize_offline_export",
    "serialize_offline_workbook",
    "sheet_evidence_from_ledger_filing",
    "translate_formula",
]

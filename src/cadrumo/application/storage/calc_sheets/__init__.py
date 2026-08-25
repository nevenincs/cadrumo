"""Workbook export planning engine for modelo registry snapshots.

Translates a
:class:`domain.calculations.registry.RegistrySnapshot` into a
:class:`application.storage.calc_sheets.SheetExportPlan` whose formulas
produce the same per-casilla rounded values as the local registry runtime. The
plan is shared by the Google Sheets apply adapter and the offline XLSX
materializer, so layout, formulas, styling, provenance, and evidence stay on
one contract.

The package exposes three layers:

- Records (:mod:`application.storage.calc_sheets._records`) — strict
  frozen pydantic v2 types describing the workbook the engine intends to
  produce. The records are the shared vocabulary between the engine driver, the
  apply adapter, the parity oracle, and the pull adapter.
- Translator (:mod:`application.storage.calc_sheets._translator`) — pure
  function that walks a registry
  :class:`domain.calculations.registry.FormulaExpression` AST and emits a
  Sheets A1 formula string, resolving casilla references through the layout
  planner.
- Engine driver (:mod:`application.storage.calc_sheets._engine`) —
  consumes a
  :class:`domain.calculations.registry.RegistrySnapshot` plus a
  caller-supplied
  :class:`application.storage.calc_sheets.OperatorInputs` payload and
  assembles a
  :class:`application.storage.calc_sheets.SheetExportPlan` ready for the
  apply adapter.
- Offline export
  (:mod:`application.storage.calc_sheets._workbook_export`) — serializes
  the same plan into XLSX bytes plus the machine-readable evidence sidecar.

Operator-facing CLI surface lives under
`src/cadrumo/entrypoints/cli/_config/_google.py`; this package contains
domain and application logic only.

See Also:
    :class:`domain.calculations.registry.RegistrySnapshot`
        Registry-authored calculation surface compiled by the engine.
    :class:`application.storage.calc_sheets.SheetExportPlan`
        Shared workbook plan consumed by online and offline renderers.
    :func:`application.storage.calc_sheets.serialize_offline_export`
        Offline XLSX plus evidence-sidecar serializer for operator-directed
        exports.
"""

from ._engine import CALC_SHEETS_ENGINE_VERSION, build_export_plan, collect_row_sets, registry_sha
from ._errors import CalcSheetsEngineError, CalcSheetsParityError, CalcSheetsRecordError
from ._evidence import sheet_evidence_from_ledger_filing
from ._export_service import export_modelo_to_sheets
from ._layout import BracketRanges, SheetLayout, plan_layout
from ._parity_comparison import CasillaParity, collect_parity_rows, resolve_parity_verdict
from ._parity_harness import OperatorInputScenario, verify_modelo_parity
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
    column_index_to_letters,
    column_letters_to_index,
)
from ._row_set_assembly import assemble_row_sets_for_snapshot
from ._theme import (
    ROLE_STYLES,
    STYLED_RANGE_VERTICAL_ALIGN,
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
    guide_stamps,
    serialize_evidence_sidecar,
    serialize_offline_export,
    serialize_offline_workbook,
)

__all__ = [
    "CALC_SHEETS_ENGINE_VERSION",
    "ROLE_STYLES",
    "STYLED_RANGE_VERTICAL_ALIGN",
    "WORKBOOK_FONT_FAMILY",
    "BracketRanges",
    "CalcSheetsEngineError",
    "CalcSheetsParityError",
    "CalcSheetsRecordError",
    "CasillaParity",
    "OfflineWorkbookEvidenceSidecar",
    "OfflineWorkbookExportResult",
    "OperatorInput",
    "OperatorInputScenario",
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
    "assemble_row_sets_for_snapshot",
    "build_evidence_sidecar",
    "build_export_plan",
    "build_offline_workbook",
    "collect_parity_rows",
    "collect_row_sets",
    "column_index_to_letters",
    "column_letters_to_index",
    "evidence_table",
    "export_modelo_to_sheets",
    "guide_stamps",
    "hex_to_rgb_floats",
    "plan_layout",
    "registry_sha",
    "resolve_parity_verdict",
    "serialize_evidence_sidecar",
    "serialize_offline_export",
    "serialize_offline_workbook",
    "sheet_evidence_from_ledger_filing",
    "translate_formula",
    "verify_modelo_parity",
]

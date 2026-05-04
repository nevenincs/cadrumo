"""Registry-backed AEAT legal calculation authority."""

from __future__ import annotations

from ._bindings import resolve_bound_casilla_inputs
from ._errors import RegistryError, RegistryLoadError, RegistrySnapshotError, RegistryValidationError
from ._export import ResolvedExportLayout, export_fields_for_casilla, resolve_export_layout
from ._formula_runtime import RegistryCalculationEntry, RegistryCalculationResult, calculate_registry_snapshot
from ._legal import verify_legal_catalogue, verify_legal_reference
from ._loader import load_catalogue_file, load_modelo_file, load_registry_tree
from ._relations import resolve_relation_values
from ._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    RemoteStateGuardResult,
    assert_remote_operation_allowed,
    evaluate_remote_operation,
)
from ._runtime_graph import expression_casilla_refs
from ._schema import (
    ApplicationLinkDefinition,
    CasillaDefinition,
    DataBindingDefinition,
    ExtractionProfileDefinition,
    FormulaDefinition,
    FormulaExpression,
    LegalReference,
    LiveCrossReferenceDecision,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistrySnapshot,
    SourceReference,
    VerificationExpectationDefinition,
    WorkbookParityReference,
)
from ._snapshot import build_snapshot
from ._sources import verify_source_catalogue, verify_source_file
from ._validate import RegistryValidator
from ._workbook_parity import (
    SyntheticInputSet,
    SyntheticInputValue,
    WorkbookArtefactReport,
    WorkbookBackendVerificationReport,
    WorkbookCellRef,
    WorkbookModeloCoverage,
    WorkbookParityComparison,
    WorkbookParityRunReport,
    WorkbookRunnerAvailability,
    WorkbookScanOptions,
    compare_registry_to_workbook,
    detect_workbook_runner,
    discover_workbooks,
    inventory_workbook_coverage,
    run_workbook_with_excel_com,
    scan_workbook,
    verify_workbook_backend,
)

__all__ = [
    "ApplicationLinkDefinition",
    "CasillaDefinition",
    "DataBindingDefinition",
    "ExtractionProfileDefinition",
    "FormulaDefinition",
    "FormulaExpression",
    "LegalReference",
    "LiveCrossReferenceDecision",
    "ModeloDefinition",
    "ModeloRevision",
    "ParameterDefinition",
    "RegistryCalculationEntry",
    "RegistryCalculationResult",
    "RegistryCatalogues",
    "RegistryError",
    "RegistryLoadError",
    "RegistrySnapshot",
    "RegistrySnapshotError",
    "RegistryValidationError",
    "RegistryValidator",
    "RemoteOperation",
    "RemoteStateGuardPolicy",
    "RemoteStateGuardResult",
    "ResolvedExportLayout",
    "SourceReference",
    "SyntheticInputSet",
    "SyntheticInputValue",
    "VerificationExpectationDefinition",
    "WorkbookArtefactReport",
    "WorkbookBackendVerificationReport",
    "WorkbookCellRef",
    "WorkbookModeloCoverage",
    "WorkbookParityComparison",
    "WorkbookParityReference",
    "WorkbookParityRunReport",
    "WorkbookRunnerAvailability",
    "WorkbookScanOptions",
    "assert_remote_operation_allowed",
    "build_snapshot",
    "calculate_registry_snapshot",
    "compare_registry_to_workbook",
    "detect_workbook_runner",
    "discover_workbooks",
    "evaluate_remote_operation",
    "export_fields_for_casilla",
    "expression_casilla_refs",
    "inventory_workbook_coverage",
    "load_catalogue_file",
    "load_modelo_file",
    "load_registry_tree",
    "resolve_bound_casilla_inputs",
    "resolve_export_layout",
    "resolve_relation_values",
    "run_workbook_with_excel_com",
    "scan_workbook",
    "verify_legal_catalogue",
    "verify_legal_reference",
    "verify_source_catalogue",
    "verify_source_file",
    "verify_workbook_backend",
]

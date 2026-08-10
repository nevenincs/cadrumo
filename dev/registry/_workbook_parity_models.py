"""Workbook parity data contracts exposed through the parity facade."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, override

from pydantic import BaseModel, Field, model_validator

from cadrumo.core import STRICT_FROZEN_CONFIG, CasillaId
from cadrumo.core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from cadrumo.core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from cadrumo.domain.calculations.registry import (
    BindingId,
    EvidenceTier,
    LegalRefId,
    RegistryValidationError,
    SourceRefId,
    WorkbookOutputId,
)

from ._workbook_parity_types import (
    ParityStatus,
    WorkbookConversionStatus,
    WorkbookKind,
    WorkbookRunnerEngine,
    WorkbookRunnerStatus,
    WorkbookScanStatus,
)

# Static literal type for the workbook-extension fields. ``Literal[...]`` only
# accepts literal forms, not the ``Final[Literal[...]]`` constants, so the
# alias is declared here and pinned to the central constants below.
_WorkbookExtension = Literal[".xlsx", ".xls"]
_ConvertedExtension = Literal[".xlsx"]
WorkbookExtension = _WorkbookExtension
assert _XLSX_EXTENSION == ".xlsx" and _XLS_EXTENSION == ".xls"

__all__ = [
    "SyntheticInputSet",
    "SyntheticInputValue",
    "WorkbookArtefactReport",
    "WorkbookBackendVerificationReport",
    "WorkbookCellRef",
    "WorkbookConversionReport",
    "WorkbookExtension",
    "WorkbookModeloCoverage",
    "WorkbookParityComparison",
    "WorkbookParityModel",
    "WorkbookParityRunReport",
    "WorkbookRunnerAvailability",
]


class WorkbookParityModel(BaseModel):
    """Strict frozen base for workbook parity records."""

    model_config = STRICT_FROZEN_CONFIG


class WorkbookCellRef(WorkbookParityModel):
    """A cell participating in official workbook parity evidence."""

    sheet: str
    coordinate: str
    formula: str | None = None

    @override
    def __hash__(self) -> int:
        return hash((self.sheet, self.coordinate, self.formula))


class WorkbookArtefactReport(WorkbookParityModel):
    """Discovery report for one AEAT workbook artefact."""

    path: str
    modelo: str | None
    extension: _WorkbookExtension
    bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    sheets: tuple[str, ...] = ()
    formula_cells: int = Field(ge=0)
    input_candidates: tuple[WorkbookCellRef, ...] = ()
    output_candidates: tuple[WorkbookCellRef, ...] = ()
    workbook_kind: WorkbookKind
    evidence_tier: EvidenceTier | None
    not_evidence_for: tuple[EvidenceTier, ...] = ()
    scan_status: WorkbookScanStatus
    error: str | None = None
    elapsed_seconds: Decimal

    @model_validator(mode="after")
    def _validate_status(self) -> WorkbookArtefactReport:
        unreadable_kinds = {WorkbookKind.UNREADABLE, WorkbookKind.UNSUPPORTED_BINARY_XLS}
        if self.scan_status == WorkbookScanStatus.SCANNED and self.workbook_kind in unreadable_kinds:
            raise RegistryValidationError("scanned workbook cannot be unreadable or unsupported")
        if self.scan_status != WorkbookScanStatus.SCANNED and self.error is None:
            raise RegistryValidationError("non-scanned workbook report must include an error")
        return self


class WorkbookConversionReport(WorkbookParityModel):
    """Safe isolated conversion report for one binary XLS artefact."""

    path: str
    modelo: str | None
    bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    converted_extension: _ConvertedExtension | None = None
    sheets: tuple[str, ...] = ()
    formula_cells: int = Field(ge=0)
    input_candidates: tuple[WorkbookCellRef, ...] = ()
    output_candidates: tuple[WorkbookCellRef, ...] = ()
    workbook_kind: WorkbookKind
    evidence_tier: EvidenceTier | None
    not_evidence_for: tuple[EvidenceTier, ...]
    conversion_status: WorkbookConversionStatus
    error: str | None = None
    elapsed_seconds: Decimal

    @model_validator(mode="after")
    def _validate_status(self) -> WorkbookConversionReport:
        if self.conversion_status == "converted" and self.error is not None:
            raise RegistryValidationError("converted workbook report must not include an error")
        if self.conversion_status == "failed" and self.error is None:
            raise RegistryValidationError("failed workbook conversion report must include an error")
        return self


class SyntheticInputValue(WorkbookParityModel):
    """One synthetic value shared by registry and workbook parity execution."""

    id: str
    value: Decimal | int | str | bool
    workbook_cell: WorkbookCellRef | None = None
    registry_binding: BindingId | CasillaId | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> SyntheticInputValue:
        if self.workbook_cell is None and self.registry_binding is None:
            raise RegistryValidationError("synthetic input must target a workbook cell, registry binding, or both")
        return self


class SyntheticInputSet(WorkbookParityModel):
    """Synthetic parity fixture applied to both registry and workbook execution."""

    id: str
    modelo: str
    revision: str
    values: tuple[SyntheticInputValue, ...] = Field(min_length=1)


class WorkbookRunnerAvailability(WorkbookParityModel):
    """Availability of a local workbook recalculation runner."""

    status: WorkbookRunnerStatus
    engine: WorkbookRunnerEngine | None = None
    executable: str | None = None
    detail: str


class WorkbookParityComparison(WorkbookParityModel):
    """One registry-vs-workbook output comparison."""

    output_id: WorkbookOutputId
    workbook_cell: WorkbookCellRef
    expected_workbook_value: Decimal | int | str | bool | None
    actual_registry_value: Decimal | int | str | bool | None
    status: ParityStatus
    tolerance: Decimal = Decimal("0")
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    detail: str | None = None


class WorkbookParityRunReport(WorkbookParityModel):
    """Trace report for one parity execution attempt."""

    synthetic_input_id: str
    registry_snapshot_id: str | None = None
    workbook: WorkbookArtefactReport
    runner: WorkbookRunnerAvailability
    comparisons: tuple[WorkbookParityComparison, ...] = ()
    status: ParityStatus


class WorkbookModeloCoverage(WorkbookParityModel):
    """Per-modelo workbook coverage summary for model-law ledgers."""

    modelo: str
    workbook_count: int = Field(ge=0)
    formula_workbook_count: int = Field(ge=0)
    unsupported_xls_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        """Return True if all workbooks are supported and scanned successfully."""
        return self.unsupported_xls_count == 0 and self.failed_count == 0


class WorkbookBackendVerificationReport(WorkbookParityModel):
    """Backend-level verification report for workbook calculation coverage."""

    root: str
    workbook_count: int = Field(ge=0)
    scanned_count: int = Field(ge=0)
    formula_workbook_count: int = Field(ge=0)
    unsupported_xls_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    runner: WorkbookRunnerAvailability
    reports: tuple[WorkbookArtefactReport, ...]
    modelo_coverage: tuple[WorkbookModeloCoverage, ...] = ()

    @property
    def backend_exists(self) -> bool:
        """Return whether discovery and guardable reports exist."""
        return self.workbook_count > 0 and self.scanned_count + self.unsupported_xls_count + self.failed_count > 0

    @property
    def passed(self) -> bool:
        """Return True if all workbooks are supported and scanned successfully."""
        return self.unsupported_xls_count == 0 and self.failed_count == 0

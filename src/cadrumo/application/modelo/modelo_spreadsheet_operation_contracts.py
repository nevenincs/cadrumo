"""Exact-profile spreadsheet operation wire contracts and canonical service ports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self, override
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.public_period import PublicPeriod
from ..storage.calc_sheets.workbook_export import SheetWorkbookMaterializer, WorkbookPlanBuilder
from .modelo_spreadsheet_operation_projections import ModeloSpreadsheetExportProjection, ModeloSpreadsheetProjection

MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID = "modelo.spreadsheet.export"


_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]


class ModeloSpreadsheetRequest(BaseModel):
    """The admitted profile and canonical registry filing coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod


class ModeloSpreadsheetExportRequest(ModeloSpreadsheetRequest):
    """Explicit local export election; the supervisor stores its path securely."""

    output_path: _PathText
    replace_existing: bool = False
    prefill_relations: bool = False

    @model_validator(mode="after")
    def _absolute_output(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("spreadsheet output path must be absolute")
        return self


class SpreadsheetOutputPathRefusal(BaseModel):
    """Closed local publication facts; raw operating-system errors are excluded."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["output_path"] = "output_path"
    output_path: _PathText
    reason: Literal[
        "empty", "existing_directory", "existing_file", "missing_parent", "parent_not_directory", "publication_failed"
    ]


type SpreadsheetRefusal = SpreadsheetOutputPathRefusal


def spreadsheet_refusal_code(detail: SpreadsheetRefusal) -> str:
    """Return the registered refusal code for its closed explanation type."""
    return "REFUSED_MODELO_EXPORT_OUTPUT_PATH"


class ModeloSpreadsheetOutcome(ModeloSpreadsheetProjection):
    """Receipt-correlated successful report or deliberately retained refusal facts."""

    outcome: Literal["succeeded", "refused"]
    refusal: SpreadsheetRefusal | None = None

    def report(self) -> ModeloSpreadsheetProjection | None:
        """Return the concrete family report for common coordinate validation."""
        raise NotImplementedError

    @model_validator(mode="after")
    def _complete_outcome(self) -> Self:
        result = self.report()
        outcome_error = _outcome_result_error(self, result)
        if outcome_error is not None:
            raise ValueError(outcome_error)
        return self


class ModeloSpreadsheetExportOutcome(ModeloSpreadsheetOutcome):
    """Local workbook publication outcome."""

    operation: Literal["export"] = "export"
    result: ModeloSpreadsheetExportProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetExportProjection | None:
        """Return the existing local workbook publication report."""
        return self.result


def _outcome_result_error(outcome: ModeloSpreadsheetOutcome, result: ModeloSpreadsheetProjection | None) -> str | None:
    if outcome.outcome == "succeeded":
        if (
            outcome.refusal is not None
            or result is None
            or result.profile_id != outcome.profile_id
            or result.modelo != outcome.modelo
            or result.revision != outcome.revision
            or result.period != outcome.period
        ):
            return "spreadsheet success coordinates are inconsistent"
        return None
    return "spreadsheet refusal is incomplete" if outcome.refusal is None or result is not None else None


MODELO_SPREADSHEET_OPERATION_CONTRACTS: dict[
    str, tuple[type[ModeloSpreadsheetRequest], type[ModeloSpreadsheetProjection], type[ModeloSpreadsheetOutcome]]
] = {
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID: (
        ModeloSpreadsheetExportRequest,
        ModeloSpreadsheetExportProjection,
        ModeloSpreadsheetExportOutcome,
    ),
}


class ModeloSpreadsheetExecutionResult(BaseModel):
    """Private settled evidence, distinct from each registered public projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ModeloSpreadsheetExportOutcome
    effect: Literal["none", "updated", "unknown"]


@dataclass(frozen=True, slots=True)
class ModeloSpreadsheetOperationPorts:
    """One worker's exact profile and retained authority, with lazy provider ports."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    materialize: SheetWorkbookMaterializer
    plan_builder: WorkbookPlanBuilder


class ModeloSpreadsheetOperationPortsFactory(Protocol):
    """Compose ports without credential hydration, refresh or provider discovery."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloSpreadsheetOperationPorts:
        """Compose lazy ports retaining the owning profile and authority pin."""
        ...


__all__ = [
    "MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_OPERATION_CONTRACTS",
    "ModeloSpreadsheetExecutionResult",
    "ModeloSpreadsheetExportOutcome",
    "ModeloSpreadsheetExportRequest",
    "ModeloSpreadsheetOperationPorts",
    "ModeloSpreadsheetOperationPortsFactory",
    "ModeloSpreadsheetOutcome",
    "ModeloSpreadsheetRequest",
    "SpreadsheetOutputPathRefusal",
    "SpreadsheetRefusal",
    "spreadsheet_refusal_code",
]

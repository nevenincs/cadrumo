"""Exact-profile spreadsheet operation wire contracts and canonical service ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self, override
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CoreValidationError
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
)
from ..operations.public_period import PublicPeriod
from ..storage.calc_sheets.parity_harness import OperatorInputScenario
from ..storage.calc_sheets.workbook_export import SheetWorkbookMaterializer, WorkbookPlanBuilder
from .modelo_spreadsheet_operation_projections import (
    ModeloSpreadsheetCalculateProjection,
    ModeloSpreadsheetExportProjection,
    ModeloSpreadsheetProjection,
    ModeloSpreadsheetPullProjection,
    ModeloSpreadsheetVerifyProjection,
    SpreadsheetCalculateFacts,
    SpreadsheetPullFacts,
    SpreadsheetVerifyFacts,
)

MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID = "modelo.spreadsheet.export"
MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID = "modelo.spreadsheet.pull"
MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID = "modelo.spreadsheet.calculate"
MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID = "modelo.spreadsheet.verify"
MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE = "REFUSED_MODELO_SPREADSHEET_ROW_INGRESS"


class ModeloSpreadsheetRowIngressRefusedError(CoreValidationError):
    """Declared spreadsheet ingress refusal, separate from registry corruption."""


_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
_Text = Annotated[str, Field(max_length=4096)]
_Handle = Annotated[str, Field(min_length=1, max_length=4096)]
_Count = Annotated[int, Field(ge=0)]


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


class ModeloSpreadsheetPullRequest(ModeloSpreadsheetRequest):
    """Read an existing remote workbook, optionally assembling its populated rows."""

    spreadsheet_id: _Handle
    assemble_observations: bool = False


class ModeloSpreadsheetCalculateRequest(ModeloSpreadsheetRequest):
    """Read a matching workbook and call its existing registry calculation service."""

    spreadsheet_id: _Handle


class ModeloSpreadsheetVerifyRequest(ModeloSpreadsheetRequest):
    """Optional immutable source reference for the existing parity scenario."""

    scenario_path: _PathText | None = None
    scenario_sha256: Hex64Str | None = None

    @model_validator(mode="after")
    def _scenario_reference(self) -> Self:
        if (self.scenario_path is None) != (self.scenario_sha256 is None):
            raise ValueError("scenario path and digest must be supplied together")
        if self.scenario_path is not None and not Path(self.scenario_path).is_absolute():
            raise ValueError("spreadsheet scenario path must be absolute")
        return self


class SpreadsheetOutputPathRefusal(BaseModel):
    """Closed local publication facts; raw operating-system errors are excluded."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["output_path"] = "output_path"
    output_path: _PathText
    reason: Literal[
        "empty", "existing_directory", "existing_file", "missing_parent", "parent_not_directory", "publication_failed"
    ]


class SpreadsheetRowIngressRefusal(BaseModel):
    """Canonical row ownership coordinates without submitted cell values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["row_ingress"] = "row_ingress"
    reason: Literal[
        "undeclared_grouping",
        "caller_binding_substitution",
        "unknown_field",
        "duplicate_cell_coordinate",
        "row_ownership_collision",
    ]
    grouping: _Text
    row_index: Annotated[int, Field(ge=1)]
    binding_id: _Text | None = None
    declared_grouping: _Handle | None = None
    first_row_set_index: _Count | None = None
    second_row_set_index: _Count | None = None

    @model_validator(mode="after")
    def _complete_coordinates(self) -> Self:
        binding_required = self.reason in {"caller_binding_substitution", "unknown_field", "duplicate_cell_coordinate"}
        collision = self.reason == "row_ownership_collision"
        if (
            (self.binding_id is not None) != binding_required
            or (self.declared_grouping is not None) != (self.reason == "caller_binding_substitution")
            or (self.first_row_set_index is not None) != collision
            or (self.second_row_set_index is not None) != collision
            or (collision and self.first_row_set_index == self.second_row_set_index)
        ):
            raise ValueError("row ingress refusal coordinates are incomplete")
        return self


class SpreadsheetSnapshotMismatchRefusal(BaseModel):
    """Explicit workbook binding metadata; no worksheet values or authored error text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["snapshot_mismatch"] = "snapshot_mismatch"
    condition: Literal["google.calc_sheets.pull.snapshot_aligned"] = "google.calc_sheets.pull.snapshot_aligned"
    snapshot_aligned: Literal[False] = False
    spreadsheet_id: _Handle
    metadata_match: Literal["matches", "stale", "missing"]
    workbook_modelo: _Text
    snapshot_modelo: ModeloId
    workbook_revision: _Text
    snapshot_revision: RevisionId
    workbook_engine_version: _Text
    expected_engine_version: _Handle
    workbook_registry_sha: _Text
    snapshot_registry_sha: Annotated[str, Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")]


type SpreadsheetRefusal = (
    SpreadsheetOutputPathRefusal | SpreadsheetRowIngressRefusal | SpreadsheetSnapshotMismatchRefusal
)


def spreadsheet_refusal_code(detail: SpreadsheetRefusal) -> str:
    """Return the registered refusal code for its closed explanation type."""
    if isinstance(detail, SpreadsheetOutputPathRefusal):
        return "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    if isinstance(detail, SpreadsheetRowIngressRefusal):
        return MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
    return "REFUSED_OUTBOUND_STORAGE_CONFLICT"


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
        if not _snapshot_refusal_matches(self):
            raise ValueError("spreadsheet refusal names another authority snapshot")
        return self


class ModeloSpreadsheetExportOutcome(ModeloSpreadsheetOutcome):
    """Local workbook publication outcome."""

    operation: Literal["export"] = "export"
    result: ModeloSpreadsheetExportProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetExportProjection | None:
        """Return the existing local workbook publication report."""
        return self.result


class ModeloSpreadsheetPullOutcome(ModeloSpreadsheetOutcome):
    """Remote workbook read and optional canonical ingress outcome."""

    operation: Literal["pull"] = "pull"
    result: ModeloSpreadsheetPullProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetPullProjection | None:
        """Return the complete normalized remote workbook read report."""
        return self.result


class ModeloSpreadsheetCalculateOutcome(ModeloSpreadsheetOutcome):
    """Remote matching-workbook calculation outcome."""

    operation: Literal["calculate"] = "calculate"
    result: ModeloSpreadsheetCalculateProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetCalculateProjection | None:
        """Return the matching-workbook canonical calculation report."""
        return self.result


class ModeloSpreadsheetVerifyOutcome(ModeloSpreadsheetOutcome):
    """Existing remote parity harness outcome."""

    operation: Literal["verify"] = "verify"
    result: ModeloSpreadsheetVerifyProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetVerifyProjection | None:
        """Return the existing canonical parity harness report."""
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


def _snapshot_refusal_matches(outcome: ModeloSpreadsheetOutcome) -> bool:
    detail = outcome.refusal
    return not isinstance(detail, SpreadsheetSnapshotMismatchRefusal) or (
        detail.snapshot_modelo == outcome.modelo and detail.snapshot_revision == outcome.revision
    )


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
    projection: (
        ModeloSpreadsheetExportOutcome
        | ModeloSpreadsheetPullOutcome
        | ModeloSpreadsheetCalculateOutcome
        | ModeloSpreadsheetVerifyOutcome
    )
    effect: Literal["none", "updated", "unknown"]


@dataclass(frozen=True, slots=True)
class SpreadsheetVerifyAcknowledgement:
    """Actual canonical adapter write confirmation; identity alone is insufficient."""

    facts: SpreadsheetVerifyFacts
    remote_write_confirmed: bool


type SpreadsheetProviderAdmission = Callable[[], None]
type SpreadsheetMutationHandoff = Callable[[], None]


class SpreadsheetPullPort(Protocol):
    """Lazy canonical remote pull and optional whole-pull assembly."""

    def __call__(
        self, request: ModeloSpreadsheetPullRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetPullFacts | SpreadsheetSnapshotMismatchRefusal:
        """Read the bound workbook after admission and retain its canonical facts."""
        ...


class SpreadsheetCalculatePort(Protocol):
    """Lazy canonical pull and existing guarded registry calculation."""

    def __call__(
        self, request: ModeloSpreadsheetCalculateRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetCalculateFacts | SpreadsheetSnapshotMismatchRefusal:
        """Calculate only through the canonical matching-workbook guard."""
        ...


class SpreadsheetVerifyPort(Protocol):
    """Lazy parity harness with separate provider admission and mutation handoff."""

    def __call__(
        self,
        request: ModeloSpreadsheetVerifyRequest,
        scenario: OperatorInputScenario,
        *,
        admit_provider: SpreadsheetProviderAdmission,
        before_mutation: SpreadsheetMutationHandoff,
    ) -> SpreadsheetVerifyAcknowledgement:
        """Run canonical parity after provider admission and explicit mutation handoff."""
        ...


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
    "MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_OPERATION_CONTRACTS",
    "MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE",
    "MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID",
    "ModeloSpreadsheetCalculateOutcome",
    "ModeloSpreadsheetCalculateRequest",
    "ModeloSpreadsheetExecutionResult",
    "ModeloSpreadsheetExportOutcome",
    "ModeloSpreadsheetExportRequest",
    "ModeloSpreadsheetOperationPorts",
    "ModeloSpreadsheetOperationPortsFactory",
    "ModeloSpreadsheetOutcome",
    "ModeloSpreadsheetPullOutcome",
    "ModeloSpreadsheetPullRequest",
    "ModeloSpreadsheetRequest",
    "ModeloSpreadsheetRowIngressRefusedError",
    "ModeloSpreadsheetVerifyOutcome",
    "ModeloSpreadsheetVerifyRequest",
    "SpreadsheetCalculatePort",
    "SpreadsheetMutationHandoff",
    "SpreadsheetOutputPathRefusal",
    "SpreadsheetProviderAdmission",
    "SpreadsheetPullPort",
    "SpreadsheetRefusal",
    "SpreadsheetRowIngressRefusal",
    "SpreadsheetSnapshotMismatchRefusal",
    "SpreadsheetVerifyAcknowledgement",
    "SpreadsheetVerifyPort",
    "spreadsheet_refusal_code",
]

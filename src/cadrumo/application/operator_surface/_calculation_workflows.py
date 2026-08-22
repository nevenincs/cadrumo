"""Supported calculation workflows derived from reconciled live operator leaves."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core import ModeloCalculationRouteId
from ._errors import OperatorSurfaceContractError
from ._manifest import OperatorSurfaceReconciliation

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")
_CALCULATION_WORKFLOW_PATHS = {
    "modelo.work.calculate": ("app", "modelo", "work", "calculate"),
    "modelo.work.wizard": ("app", "modelo", "work", "wizard"),
    "quickfile": ("app", "quickfile"),
}
_CALCULATION_WORKFLOW_SUBJECTS = frozenset(_CALCULATION_WORKFLOW_PATHS)


class SupportedModeloCalculationWorkflow(BaseModel):
    """One live operator workflow that can reach modelo calculation."""

    model_config = _STRICT_FROZEN

    entrypoint_id: Literal["cli"] = "cli"
    command_id: str = Field(min_length=1)
    route_id: ModeloCalculationRouteId
    canonical_cli_path: tuple[str, ...] = Field(min_length=1)

    @field_validator("command_id")
    @classmethod
    def _command_is_a_calculation_workflow(cls, value: str) -> str:
        if value not in _CALCULATION_WORKFLOW_SUBJECTS:
            raise ValueError("unsupported modelo calculation workflow identity")
        return value

    @field_validator("canonical_cli_path")
    @classmethod
    def _path_is_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not token or token != token.strip() or token.startswith("-") for token in value):
            raise ValueError("calculation workflow requires canonical CLI path tokens")
        return value


class SupportedModeloCalculationWorkflowCatalogue(BaseModel):
    """Deterministic application-owned catalogue projected from live reconciliation."""

    model_config = _STRICT_FROZEN

    workflows: tuple[SupportedModeloCalculationWorkflow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_deterministic_workflows(self) -> SupportedModeloCalculationWorkflowCatalogue:
        identities = tuple((row.entrypoint_id, row.command_id, row.route_id) for row in self.workflows)
        paths = tuple(row.canonical_cli_path for row in self.workflows)
        if len(set(identities)) != len(identities):
            raise ValueError("supported calculation workflow identities must be unique")
        if len(set(paths)) != len(paths):
            raise ValueError("supported calculation workflow canonical paths must be unique")
        if identities != tuple(sorted(identities)):
            raise ValueError("supported calculation workflows must use deterministic identity order")
        return self

    def supports(
        self,
        *,
        entrypoint_id: str,
        command_id: str,
        route_id: ModeloCalculationRouteId,
        canonical_cli_path: tuple[str, ...],
    ) -> bool:
        """Return whether the complete reconciled workflow identity is supported."""
        return any(
            workflow.entrypoint_id == entrypoint_id
            and workflow.command_id == command_id
            and workflow.route_id is route_id
            and workflow.canonical_cli_path == canonical_cli_path
            for workflow in self.workflows
        )

def build_supported_modelo_calculation_workflow_catalogue(
    reconciliation: OperatorSurfaceReconciliation,
) -> SupportedModeloCalculationWorkflowCatalogue:
    """Project qualifying workflow identities and paths from reconciled live leaves."""
    selected: list[SupportedModeloCalculationWorkflow] = []
    seen_ids: set[str] = set()
    seen_paths: set[tuple[str, ...]] = set()
    diagnostics: list[str] = []
    for reconciled_leaf in reconciliation.leaves:
        live_leaf = reconciled_leaf.live_leaf
        command_id = live_leaf.subject_leaf_key
        if command_id not in _CALCULATION_WORKFLOW_SUBJECTS:
            continue
        expected_path = _CALCULATION_WORKFLOW_PATHS[command_id]
        if live_leaf.canonical_cli_path != expected_path:
            diagnostics.append(
                f"supported calculation workflow path drift for {command_id}: "
                + " ".join(live_leaf.canonical_cli_path),
            )
            continue
        if command_id in seen_ids:
            diagnostics.append(f"duplicate supported calculation workflow identity: {command_id}")
        if live_leaf.canonical_cli_path in seen_paths:
            diagnostics.append(
                "duplicate supported calculation workflow path: " + " ".join(live_leaf.canonical_cli_path),
            )
        seen_ids.add(command_id)
        seen_paths.add(live_leaf.canonical_cli_path)
        selected.append(
            SupportedModeloCalculationWorkflow(
                command_id=command_id,
                route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
                canonical_cli_path=live_leaf.canonical_cli_path,
            ),
        )
    if diagnostics:
        raise OperatorSurfaceContractError(
            "supported_modelo_calculation_workflows",
            reason="; ".join(diagnostics),
        )
    if not selected:
        raise OperatorSurfaceContractError(
            "supported_modelo_calculation_workflows",
            reason="reconciled live surface contains no supported modelo calculation workflow",
        )
    return SupportedModeloCalculationWorkflowCatalogue(
        workflows=tuple(sorted(selected, key=lambda row: (row.entrypoint_id, row.command_id))),
    )


__all__ = [
    "ModeloCalculationRouteId",
    "SupportedModeloCalculationWorkflow",
    "SupportedModeloCalculationWorkflowCatalogue",
    "build_supported_modelo_calculation_workflow_catalogue",
]

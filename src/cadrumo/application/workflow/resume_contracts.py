"""Typed request, captured outcomes, and frontend projection for workflow resume."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..modelo.selectors import ModeloCalculationRevisionSelector
from ..operations.public_period import PublicPeriod
from .abort import WorkflowAbortReason
from .obligation_snapshot import WorkflowObligationSnapshot
from .resume import (
    WorkflowResumeRefusalReason,
    WorkflowResumeRunCandidate,
    WorkflowResumeTargetResolution,
    workflow_resume_refusal_reason,
)
from .run_models import WorkflowStage


def _require_unambiguous_resume_address(request: WorkflowResumeRequest) -> None:
    exact = sum(item is not None for item in (request.target, request.work_unit_id, request.calculation_revision_id))
    visible = any(item is not None for item in (request.modelo, request.period, request.revision_id))
    if exact > 1 or (exact and visible):
        raise ValueError("resume requires one unambiguous target")


def _require_complete_resume_address(request: WorkflowResumeRequest) -> None:
    exact = any(item is not None for item in (request.target, request.work_unit_id, request.calculation_revision_id))
    if not exact and (request.modelo is None or request.period is None):
        raise ValueError("resume requires a complete visible filing target")


def _require_expected_period_address(request: WorkflowResumeRequest) -> None:
    exact = any(item is not None for item in (request.target, request.work_unit_id, request.calculation_revision_id))
    if request.expected_period is not None and not exact:
        raise ValueError("expected period constrains only an exact resume target")


def _require_selector_address(request: WorkflowResumeRequest) -> None:
    if request.selector is not None and (
        request.calculation_revision_id is not None or (request.target is not None and len(request.target) == 16)
    ):
        raise ValueError("a direct run or revision does not accept a revision selector")


def _validate_resume_address(request: WorkflowResumeRequest) -> None:
    _require_unambiguous_resume_address(request)
    _require_complete_resume_address(request)
    _require_expected_period_address(request)
    _require_selector_address(request)


class WorkflowResumeRequest(BaseModel):
    """One exact address or a complete visible filing target, stored privately."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    target: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{16}|[0-9a-f]{64})$")] | None = None
    work_unit_id: WorkUnitId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None = None
    period: PublicPeriod | None = None
    expected_period: PublicPeriod | None = None
    revision_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    selector: ModeloCalculationRevisionSelector | None = None

    @model_validator(mode="after")
    def _address(self) -> Self:
        _validate_resume_address(self)
        return self

    def scope_period(self) -> PublicPeriod | None:
        """Return the explicit constraint without consulting mutable history."""
        return self.period if self.period is not None else self.expected_period


class WorkflowResumeAddress(BaseModel):
    """Closed projection of the canonical selector resolution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    source: Literal[
        "workflow_run_id",
        "work_unit_id",
        "calculation_revision_id",
        "visible_target",
        "visible_target_revision_selector",
    ]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None
    period: PublicPeriod | None
    filing_year: int | None
    work_unit_id: WorkUnitId | None
    short_work_unit_id: str | None
    calculation_revision_id: CalculationRevisionId | None
    short_calculation_revision_id: str | None

    @classmethod
    def from_resolution(cls, resolution: WorkflowResumeTargetResolution) -> Self:
        """Copy selected coordinates without the domain period serializer."""
        return cls.model_validate(
            resolution.model_dump(mode="python")
            | {
                "period": PublicPeriod.from_period(resolution.period) if resolution.period is not None else None,
            }
        )

    def to_resolution(self) -> WorkflowResumeTargetResolution:
        """Restore the canonical address for established CLI presentation."""
        return WorkflowResumeTargetResolution.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period() if self.period is not None else None,
            }
        )


class WorkflowResumeSuccess(BaseModel):
    """The same captured obligation the resumability policy approved."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["success"] = "success"
    address: WorkflowResumeAddress
    obligation: WorkflowObligationSnapshot
    aborted_reason: WorkflowAbortReason

    @model_validator(mode="after")
    def _coordinates(self) -> Self:
        if self.address.period is not None and (
            self.address.period != self.obligation.period or self.address.modelo != self.obligation.modelo
        ):
            raise ValueError("resume context differs from its selected target")
        if (
            workflow_resume_refusal_reason(
                final_stage=WorkflowStage.ABORTED, aborted_reason=self.aborted_reason, has_obligation=True
            )
            is not None
        ):
            raise ValueError("resume success contains a non-resumable abort reason")
        return self


class WorkflowResumeRefusal(BaseModel):
    """Bounded factual guidance for a canonical resumability refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["refused"] = "refused"
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    reason: WorkflowResumeRefusalReason
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None

    @model_validator(mode="after")
    def _canonical_reason(self) -> Self:
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError("resume refusal requires terminal facts")
        if self.final_stage is WorkflowStage.DONE and self.aborted_reason is not None:
            raise ValueError("completed run cannot carry an abort reason")
        expected = workflow_resume_refusal_reason(
            final_stage=self.final_stage,
            aborted_reason=self.aborted_reason,
            has_obligation=self.reason is not WorkflowResumeRefusalReason.NO_OBLIGATION,
        )
        if expected is not self.reason:
            raise ValueError("resume refusal contradicts its terminal facts")
        return self


class WorkflowResumeCandidateSnapshot(BaseModel):
    """One candidate in an explicitly authorized ambiguous filing period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None
    started_at: datetime
    short_work_unit_id: str | None
    work_unit_id: WorkUnitId | None

    @model_validator(mode="after")
    def _terminal(self) -> Self:
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError("resume candidate requires terminal facts")
        if (self.final_stage is WorkflowStage.ABORTED) != (self.aborted_reason is not None):
            raise ValueError("resume candidate has contradictory abort facts")
        return self

    @classmethod
    def from_candidate(cls, candidate: WorkflowResumeRunCandidate) -> Self:
        """Project typed canonical facts rather than exception context text."""
        return cls.model_validate(
            candidate.model_dump(mode="python")
            | {
                "period": PublicPeriod.from_period(candidate.period),
                "final_stage": WorkflowStage(candidate.final_stage),
                "aborted_reason": WorkflowAbortReason(candidate.aborted_reason) if candidate.aborted_reason else None,
            }
        )

    def to_candidate(self) -> WorkflowResumeRunCandidate:
        """Restore the existing localized guidance input."""
        return WorkflowResumeRunCandidate.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period(),
                "final_stage": self.final_stage.value,
                "aborted_reason": self.aborted_reason.value if self.aborted_reason else None,
            }
        )


class WorkflowResumeAmbiguity(BaseModel):
    """Multiple captured candidates; no automatic retry target is chosen."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["ambiguous"] = "ambiguous"
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    candidates: tuple[WorkflowResumeCandidateSnapshot, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _coordinates(self) -> Self:
        if any(item.modelo != self.modelo or item.period != self.period for item in self.candidates):
            raise ValueError("resume ambiguity crosses filing targets")
        if len({item.run_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("resume ambiguity repeats a run")
        return self


type WorkflowResumeOutcome = Annotated[
    WorkflowResumeSuccess | WorkflowResumeRefusal | WorkflowResumeAmbiguity, Field(discriminator="kind")
]


class WorkflowResumeResult(BaseModel):
    """Private encrypted resume-context operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    outcome: WorkflowResumeOutcome


class WorkflowResumeProjection(BaseModel):
    """Independent frontend schema for explicitly disclosed resume facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    outcome: WorkflowResumeOutcome

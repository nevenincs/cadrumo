"""Strict pydantic v2 records for the composite workflow engine.

Every boundary-crossing type in :mod:`aeat.application.workflow` is
defined here as a frozen, strict, ``extra="forbid"``
:class:`pydantic.BaseModel` or as an :class:`enum.StrEnum` for closed
enumerations. :attr:`WorkflowStep.details` is reserved for string-valued
diagnostics emitted by workflow stages.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.outbound.aeat.browser._site_health import SiteHealthStatus
from ...domain.deadlines import FilingObligation

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class WorkflowStage(StrEnum):
    """The read-only stages of the composite workflow, in strict order.

    The engine walks the stages top-to-bottom. Downstream code (the CLI,
    schedulers, the UI) depends on the linear ordering for the bailout
    matrix; the ordering is part of the public contract.

    Attributes:
        LOADING_PROFILE: Resolve the autónomo profile and target run.
        COMPUTING_DEADLINES: Determine the next pending obligation.
        CHECKING_INBOX: Probe the AEAT inbox for blocking requerimientos.
        BUILDING_DRAFT: Compose the filing draft from registry-backed inputs.
        VALIDATING_DRAFT: Apply registry-backed validation to the draft.
        RUNNING_PREFLIGHT: Execute the submission engine's preflight.
        DONE: Terminal success stage.
        ABORTED: Terminal failure stage; pairs with a
            :class:`WorkflowAbortReason`.
    """

    LOADING_PROFILE = "LOADING_PROFILE"
    COMPUTING_DEADLINES = "COMPUTING_DEADLINES"
    CHECKING_INBOX = "CHECKING_INBOX"
    BUILDING_DRAFT = "BUILDING_DRAFT"
    VALIDATING_DRAFT = "VALIDATING_DRAFT"
    RUNNING_PREFLIGHT = "RUNNING_PREFLIGHT"
    DONE = "DONE"
    ABORTED = "ABORTED"


class WorkflowAbortReason(StrEnum):
    """Closed set of reasons the workflow may abort.

    Every value is reachable from a specific :class:`WorkflowStage` via
    the bailout matrix and is exhaustively tested.

    Attributes:
        NO_PENDING_OBLIGATION: No filing is due in the requested window.
        INBOX_BLOCKING_REQUERIMIENTO: An open requerimiento blocks the
            obligation until resolved.
        DEADLINE_PASSED: The statutory deadline has expired.
        ALREADY_FILED: A filing for the obligation already exists.
        DRAFT_HAS_ERRORS: Draft validation reported blocking errors.
        PREFLIGHT_FAILED: The submission engine's preflight rejected the
            draft.
        CERT_INVALID: The certificate bundle is invalid or expired.
        USER_CANCELLED: The operator interrupted the run.
        SITE_UNAVAILABLE: AEAT site-health probe reports unavailable.
        UNHANDLED_EXCEPTION: A wrapped component raised an unexpected
            exception captured as
            :class:`aeat.application.workflow.WorkflowComponentError`.
    """

    NO_PENDING_OBLIGATION = "NO_PENDING_OBLIGATION"
    INBOX_BLOCKING_REQUERIMIENTO = "INBOX_BLOCKING_REQUERIMIENTO"
    DEADLINE_PASSED = "DEADLINE_PASSED"
    ALREADY_FILED = "ALREADY_FILED"
    DRAFT_HAS_ERRORS = "DRAFT_HAS_ERRORS"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    CERT_INVALID = "CERT_INVALID"
    USER_CANCELLED = "USER_CANCELLED"
    SITE_UNAVAILABLE = "SITE_UNAVAILABLE"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"


class SiteHealthAlert(BaseModel):
    """Workflow-side alert wrapping a browser site-health status.

    Attributes:
        stage: The :class:`WorkflowStage` that produced the alert.
        status: The :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
            captured by the probe.
        run_id: Identifier of the workflow run that emitted the alert.
    """

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    status: SiteHealthStatus
    run_id: str = Field(min_length=1, max_length=128)


class WorkflowStep(BaseModel):
    """A single step in a :class:`WorkflowResult`.

    Attributes:
        stage: The :class:`WorkflowStage` this step represents.
        started_at: UTC timestamp when the step began.
        ended_at: UTC timestamp when the step ended. ``None`` while the
            step is still running (never persisted as ``None``).
        success: Whether the step completed without triggering a
            workflow abort. ``None`` only during construction of a
            still-running step; always set on completed steps.
        summary: Multilingual human-readable summary of what happened in
            this step.
        details: Optional human-readable diagnostics dictionary. Per-stage
            diagnostics are string-valued so the result can carry useful
            context without adding one envelope type per workflow step.
    """

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    started_at: datetime
    ended_at: datetime | None = None
    success: bool | None = None
    summary: str
    details: dict[str, str] | None = None
    site_health_alert: SiteHealthAlert | None = None

    @model_validator(mode="after")
    def _check_timestamps(self) -> WorkflowStep:
        """Reject steps whose ``ended_at`` precedes ``started_at``."""
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError(f"ended_at ({self.ended_at}) precedes started_at ({self.started_at})")
        if self.ended_at is not None and self.success is None:
            raise ValueError("completed steps must set success explicitly")
        return self


class WorkflowResult(BaseModel):
    """The full result of one :meth:`WorkflowEngine.run_next` invocation.

    Attributes:
        run_id: Stable 16-char hex hash of
            ``(profile.tax_id, modelo, period, started_at)``. Identical
            seeds produce identical ids across processes.
        started_at: UTC timestamp when the engine began driving.
        ended_at: UTC timestamp when the engine returned.
        final_stage: The terminal stage reached. Either
            :attr:`WorkflowStage.DONE` or :attr:`WorkflowStage.ABORTED`.
        aborted_reason: The :class:`WorkflowAbortReason` recorded when
            ``final_stage == ABORTED``; ``None`` otherwise.
        obligation: The :class:`aeat.domain.deadlines.FilingObligation` the
            workflow targeted, if one was computed before the bailout.
        draft_id: The filing draft id, if a draft was built.
        submission_id: Reserved for historical persisted records. New
            workflow runs never create AEAT submission ids.
        steps: Tuple of :class:`WorkflowStep` in the order the engine
            executed them.
        summary: Multilingual user-facing summary of the whole run.
    """

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=16, max_length=16)
    started_at: datetime
    ended_at: datetime
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None = None
    obligation: FilingObligation | None = None
    draft_id: str | None = None
    submission_id: str | None = None
    steps: tuple[WorkflowStep, ...]
    summary: str

    @model_validator(mode="after")
    def _check_terminal_consistency(self) -> WorkflowResult:
        """Enforce the terminal-state invariants.

        - ``final_stage == ABORTED`` iff ``aborted_reason is not None``.
        - ``final_stage == DONE`` iff ``aborted_reason is None``.
        - ``ended_at >= started_at``.
        """
        if self.ended_at < self.started_at:
            raise ValueError("ended_at precedes started_at")
        if self.final_stage is WorkflowStage.ABORTED and self.aborted_reason is None:
            raise ValueError("ABORTED results must carry an aborted_reason")
        if self.final_stage is WorkflowStage.DONE and self.aborted_reason is not None:
            raise ValueError("DONE results must not carry an aborted_reason")
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError(f"final_stage must be DONE or ABORTED, got {self.final_stage}")
        return self


def compute_run_id(
    *,
    tax_id: str,
    modelo: str,
    period: str,
    started_at: datetime,
) -> str:
    """Return a stable 16-char hex hash for a workflow run.

    Args:
        tax_id: The profile tax ID.
        modelo: The target modelo, or ``"-"`` when the
            engine has not yet determined one.
        period: The target period (e.g. ``"2026Q1"``), or ``"-"``.
        started_at: The UTC start timestamp of the run.

    Returns:
        A 16-character lowercase hex prefix of the SHA-256 digest of
        the deterministic tuple encoding.
    """
    payload = "|".join([tax_id, modelo, period, started_at.isoformat()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

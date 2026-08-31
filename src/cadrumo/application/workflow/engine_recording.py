"""Failure recording helpers for the workflow engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import NoReturn

from ...core.errors.error_codes import build_error_envelope
from ...core.errors.hierarchy import SiteHealthError
from ...core.logging import get_logger
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.time.clock import now as _utcnow
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict
from .abort import WorkflowAbortReason
from .errors import UnhandledWorkflowError, WorkflowAbortSignalError
from .run_models import (
    SiteHealthAlert,
    WorkflowFailureDetails,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStep,
)

_logger = get_logger(__name__)


def record_unhandled(
    *,
    stage: WorkflowStage,
    started: datetime,
    exc: BaseException,
    steps: list[WorkflowStep],
) -> NoReturn:
    """Record a failed step and raise ``WorkflowAbortSignalError(UNHANDLED_EXCEPTION)``."""
    _logger.warning(
        "workflow stage raised an unhandled exception stage=%s",
        stage.value,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    synthetic = UnhandledWorkflowError(
        f"{stage.value} raised {type(exc).__name__}: {exc}",
        context={
            "stage": stage.value,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )
    synthetic.__cause__ = exc
    build_error_envelope(synthetic)
    steps.append(
        WorkflowStep(
            stage=stage,
            started_at=started,
            ended_at=_utcnow(),
            success=False,
            summary_locale_key="application.workflow.steps.workflow_failure",
            details=WorkflowFailureDetails(
                kind="workflow_failure",
                error_code="workflow.execution.unhandled_exception",
            ),
            precondition_verdict=_execution_failure_verdict("workflow.execution.unhandled_exception"),
        ),
    )
    raise WorkflowAbortSignalError(reason=WorkflowAbortReason.UNHANDLED_EXCEPTION) from synthetic


def record_site_unavailable(
    *,
    stage: WorkflowStage,
    started: datetime,
    exc: SiteHealthError,
    steps: list[WorkflowStep],
    current_run_id: Callable[[], str | None],
) -> NoReturn:
    """Record a site-health failure and abort with ``SITE_UNAVAILABLE``."""
    alert_run_id = current_run_id() or "-"
    steps.append(
        WorkflowStep(
            stage=stage,
            started_at=started,
            ended_at=_utcnow(),
            success=False,
            summary_locale_key="application.workflow.steps.site_unavailable",
            details=WorkflowFailureDetails(
                kind="workflow_failure",
                error_code="workflow.site.unavailable",
            ),
            precondition_verdict=_execution_failure_verdict("workflow.site.unavailable"),
            site_health_alert=SiteHealthAlert(
                stage=stage,
                status=WorkflowSiteHealthFacts.from_status(exc.status),
                run_id=alert_run_id,
            ),
        ),
    )
    raise WorkflowAbortSignalError(reason=WorkflowAbortReason.SITE_UNAVAILABLE) from exc


def _execution_failure_verdict(error_code: str) -> PreconditionVerdict:
    """Return the closed operator-decision verdict for an operational failure.

    Site-health and unhandled-exception aborts retain a persisted obligation and
    are accepted by the workflow resume authority.  They therefore cannot claim
    a terminal no-recovery outcome merely because no fully bound retry action is
    available at the recording point.
    """
    condition_id = "workflow.execution.completed"
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id="workflow.execution.error_code",
        facts={"completed": False, "error_code": error_code},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


__all__ = ["record_site_unavailable", "record_unhandled"]

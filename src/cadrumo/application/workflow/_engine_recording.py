"""Failure recording helpers for the workflow engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import NoReturn, cast

from ...core.errors import SiteHealthError, build_error_envelope
from ...core.logging import get_logger
from ...core.time import now as _utcnow
from ._engine_helpers import summary_text as _summary_text
from ._errors import UnhandledWorkflowError, WorkflowAbortSignalError
from ._models import SiteHealthAlert, SiteHealthStatus, WorkflowAbortReason, WorkflowStage, WorkflowStep

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
    unhandled_summary = _summary_text(f"Unhandled {type(exc).__name__} at stage={stage.value}: {exc}")
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
            summary=unhandled_summary,
            details={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        ),
    )
    raise WorkflowAbortSignalError(
        reason=WorkflowAbortReason.UNHANDLED_EXCEPTION,
        summary=unhandled_summary,
    ) from synthetic


def record_site_unavailable(
    *,
    stage: WorkflowStage,
    started: datetime,
    exc: SiteHealthError,
    steps: list[WorkflowStep],
    current_run_id: Callable[[], str | None],
) -> NoReturn:
    """Record a site-health failure and abort with ``SITE_UNAVAILABLE``."""
    # CAST-RATIONALE-WORKFLOW-SITE-HEALTH-STATUS:
    # ``SiteHealthError`` types its payload through the structural
    # ``SiteHealthStatusLike`` protocol so ``core.errors`` need not
    # import the browser adapter. Every site-health failure raised
    # by the AEAT browser adapter carries the concrete
    # ``SiteHealthStatus`` record, which the workflow ``SiteHealthAlert``
    # requires; narrow at this adapter boundary.
    status = cast("SiteHealthStatus", exc.status)
    alert_run_id = current_run_id() or "-"
    summary = _summary_text(f"AEAT site unavailable at stage={stage.value}: {status.state.value}")
    steps.append(
        WorkflowStep(
            stage=stage,
            started_at=started,
            ended_at=_utcnow(),
            success=False,
            summary=summary,
            site_health_alert=SiteHealthAlert(
                stage=stage,
                status=status,
                run_id=alert_run_id,
            ),
        ),
    )
    raise WorkflowAbortSignalError(
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        summary=summary,
    ) from exc


__all__ = ["record_site_unavailable", "record_unhandled"]

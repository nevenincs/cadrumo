"""Closed workflow-abort reason taxonomy."""

from __future__ import annotations

from enum import StrEnum


class WorkflowAbortReason(StrEnum):
    """Reason a workflow engine run can end in an aborted outcome."""

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


__all__ = ["WorkflowAbortReason"]

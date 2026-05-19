"""Strict pydantic v2 records for the filing submission engine.

Every type that crosses a public boundary is a strict+frozen
:class:`pydantic.BaseModel` or a closed :class:`enum.StrEnum`.
No dataclasses; no bare ``dict[str, Any]``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._errors import SubmissionValidationError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SubmissionStatus(StrEnum):
    """Lifecycle status of a :class:`ModeloPresentado`.

    Values are retained for historical records imported from AEAT,
    even though live AEAT submission is now permanently forbidden.

    Attributes:
        PENDING: Filing recorded but no attempt has run.
        IN_PROGRESS: An attempt is currently underway.
        SUBMITTED: Attempt completed; awaiting AEAT acknowledgement.
        ACKNOWLEDGED: AEAT issued a justificante CSV and PDF.
        REJECTED: AEAT explicitly rejected the filing.
        FAILED: Attempt could not complete (transport / browser).
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SubmissionAttempt(BaseModel):
    """A historical attempt record imported or retained locally.

    Attributes:
        attempt_id: Stable identifier for this attempt
            (``<submission_id>.<ordinal>``).
        started_at: UTC timestamp when the attempt began.
        ended_at: UTC timestamp when the attempt ended (success or
            failure).
        status: Terminal :class:`SubmissionStatus` for the attempt.
        error_code: Optional machine-readable error code.
        error_message: Optional multilingual error message.
        browser_trace_path: Optional path to a Playwright trace file
            written for this attempt.
    """

    model_config = _STRICT_FROZEN

    attempt_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    status: SubmissionStatus
    error_code: str | None = None
    error_message: str | None = None
    browser_trace_path: Path | None = None

    @model_validator(mode="after")
    def _check_time_ordering(self) -> SubmissionAttempt:
        """Reject attempts whose ``ended_at`` predates ``started_at``."""
        if self.ended_at and self.ended_at < self.started_at:
            raise SubmissionValidationError(f"ended_at ({self.ended_at}) is before started_at ({self.started_at})")
        return self


class ModeloPresentado(BaseModel):
    """The typed audit record for one historical filing.

    Attributes:
        submission_id: Stable SHA-256-derived hex digest of
            ``f"{draft_id}:{attempt_ordinal}"``. See
            :func:`make_submission_id`.
        draft_id: The upstream draft identifier.
        modelo: The AEAT modelo identifier.
        period: The period covered (e.g. ``"2026Q1"``).
        profile_tax_id: The autónomo NIF / NIE verbatim.
        status: The overall :class:`SubmissionStatus` for the filing.
        justificante_csv: The AEAT-issued CSV, when present.
        justificante_pdf_path: Local path to the justificante PDF,
            when present.
        submitted_at: UTC timestamp of the first attempt start.
        acknowledged_at: UTC timestamp the user acknowledged the
            filing, when set.
        attempts: Non-empty tuple of :class:`SubmissionAttempt`
            records in chronological order.
    """

    model_config = _STRICT_FROZEN

    submission_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    profile_tax_id: str = Field(min_length=1)
    status: SubmissionStatus
    justificante_csv: str | None = None
    justificante_pdf_path: Path | None = None
    submitted_at: datetime
    acknowledged_at: datetime | None = None
    attempts: tuple[SubmissionAttempt, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_ack_consistency(self) -> ModeloPresentado:
        """Enforce ``ACKNOWLEDGED`` ↔ justificante-present invariants."""
        if self.status is SubmissionStatus.ACKNOWLEDGED:
            if not self.justificante_csv or not self.justificante_pdf_path:
                raise SubmissionValidationError(
                    "status ACKNOWLEDGED requires both justificante_csv and justificante_pdf_path"
                )
            if not self.acknowledged_at:
                raise SubmissionValidationError("status ACKNOWLEDGED requires acknowledged_at")
        if self.acknowledged_at and self.acknowledged_at < self.submitted_at:
            raise SubmissionValidationError(
                f"acknowledged_at ({self.acknowledged_at}) is before submitted_at ({self.submitted_at})"
            )
        return self


def make_submission_id(draft_id: str, attempt_ordinal: int) -> str:
    """Return a stable 16-hex-char SHA-256 prefix for a submission.

    The output is deterministic: identical ``(draft_id, attempt_ordinal)``
    pairs always produce identical ids across runs and processes.

    Args:
        draft_id: The upstream draft identifier.
        attempt_ordinal: A strictly positive ordinal (``>= 1``)
            distinguishing multiple submission attempts against the
            same draft.

    Returns:
        A 16-character lowercase hex string.

    Raises:
        ValueError: If ``draft_id`` is empty or ``attempt_ordinal``
            is not a positive integer.
    """
    if not draft_id:
        raise SubmissionValidationError("draft_id must be non-empty")
    if attempt_ordinal < 1:
        raise SubmissionValidationError(f"attempt_ordinal must be >= 1, got {attempt_ordinal}")
    payload = f"{draft_id}:{attempt_ordinal}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]

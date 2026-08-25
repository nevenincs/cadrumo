"""Strict pydantic v2 records for the filing submission engine.

Every type that crosses a public boundary is a strict+frozen
:class:`pydantic.BaseModel` or a closed :class:`enum.StrEnum`.
No dataclasses; no bare ``dict[str, Any]``.

The records describe a local or imported filing audit trail. They do not
authorize a live AEAT write; live-write refusal stays with the core access gate
and application facades compose these records into draft/import flows.

See Also:
    :class:`cadrumo.domain.submission.SubmissionEngine`
        Runs preflight and reads these records from the repository.
    :func:`cadrumo.application.filing.import_filing_from_justificante`
        Builds a companion :class:`ModeloPresentado` when an offline
        justificante PDF is imported.
    :class:`cadrumo.domain.modelos.ModeloRecord`
        Work-unit filing record used by the modelo application facade.
    :mod:`cadrumo.application.live`
        Read-only live-capture surface that may attach AEAT evidence to
        existing local filing records.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period
from ...core.hashing import sha256_hex
from ...core.identity import AeatCsv, SubjectTaxId
from ...core.time import validate_utc_aware
from .errors import SubmissionValidationError

_SUBMISSION_ID_LENGTH = 16

SubmissionId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=_SUBMISSION_ID_LENGTH,
        max_length=_SUBMISSION_ID_LENGTH,
        pattern=r"^[0-9a-f]{16}$",
    ),
]
"""Content-derived identity of one filing submission.

The lowercase 16-character SHA-256 prefix :func:`make_submission_id` returns for
a ``(draft_id, attempt_ordinal)`` pair. Declaring the shape here keeps the
producer and the persisted record on one contract, so a record cannot carry an
identifier no derivation could have produced.
"""

SubmissionAttemptId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[0-9a-f]{16}\.[1-9][0-9]*$"),
]
"""Coordinate of one attempt within its submission: ``<submission_id>.<ordinal>``.

The ordinal is strictly positive and unpadded. The pattern fixes the *shape*;
:class:`ModeloPresentado` binds each attempt to its own parent submission and
ordinal position.
"""


class SubmissionStatus(StrEnum):
    """Lifecycle status of a :class:`ModeloPresentado`.

    Values are retained for historical records imported from AEAT,
    even though live AEAT submission is now permanently forbidden.
    Member names and values mirror the AEAT Sede labels.

    Attributes:
        PENDIENTE_DE_PRESENTAR: Filing recorded but no attempt has run.
        EN_TRAMITACION: An attempt is currently underway.
        PRESENTADA: Attempt completed; awaiting AEAT acknowledgement.
        ACEPTADA: AEAT issued a justificante CSV and PDF.
        RECHAZADA: AEAT explicitly rejected the filing.
        FALLIDA: Attempt could not complete (transport / browser).
    """

    PENDIENTE_DE_PRESENTAR = "PENDIENTE_DE_PRESENTAR"
    EN_TRAMITACION = "EN_TRAMITACION"
    PRESENTADA = "PRESENTADA"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    FALLIDA = "FALLIDA"


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

    attempt_id: SubmissionAttemptId
    started_at: datetime
    ended_at: datetime
    status: SubmissionStatus
    error_code: str | None = None
    error_message: str | None = None
    browser_trace_path: Path | None = None

    @model_validator(mode="after")
    def _check_time_ordering(self) -> SubmissionAttempt:
        """Reject non-UTC timestamps and attempts whose end predates their start."""
        try:
            validate_utc_aware(self.started_at)
            validate_utc_aware(self.ended_at)
        except ValueError as exc:
            raise SubmissionValidationError(str(exc)) from exc
        if self.ended_at and self.ended_at < self.started_at:
            raise SubmissionValidationError(f"ended_at ({self.ended_at}) is before started_at ({self.started_at})")
        return self


_AGGREGATE_STATUS_BY_TERMINAL_ATTEMPT: dict[SubmissionStatus, frozenset[SubmissionStatus]] = {
    # A presentation that completed may still be awaiting AEAT's answer, or may
    # already have received it -- the acknowledgement arrives after the attempt.
    SubmissionStatus.PRESENTADA: frozenset(
        {SubmissionStatus.PRESENTADA, SubmissionStatus.ACEPTADA, SubmissionStatus.RECHAZADA},
    ),
    # An attempt that itself recorded AEAT's verdict fixes the filing's verdict.
    SubmissionStatus.ACEPTADA: frozenset({SubmissionStatus.ACEPTADA}),
    SubmissionStatus.RECHAZADA: frozenset({SubmissionStatus.RECHAZADA}),
    # A failed attempt never presented anything, so the filing is either
    # recorded as failed or still awaiting a presentation.
    SubmissionStatus.FALLIDA: frozenset(
        {SubmissionStatus.FALLIDA, SubmissionStatus.PENDIENTE_DE_PRESENTAR},
    ),
    SubmissionStatus.EN_TRAMITACION: frozenset({SubmissionStatus.EN_TRAMITACION}),
    SubmissionStatus.PENDIENTE_DE_PRESENTAR: frozenset({SubmissionStatus.PENDIENTE_DE_PRESENTAR}),
}
"""Aggregate statuses each terminal-attempt outcome can support.

The filing's status and its last attempt's status answer different questions --
"where does this filing stand" versus "how did the last try end" -- so they are
not required to be equal. They are required to be *compatible*: AEAT's verdict
may land after a completed presentation, but it cannot exist without one.
"""


class ModeloPresentado(BaseModel):
    """The typed audit record for one historical filing.

    Attributes:
        submission_id: Stable SHA-256-derived hex digest of
            ``f"{draft_id}:{attempt_ordinal}"``. See
            :func:`make_submission_id`.
        draft_id: The upstream draft identifier.
        modelo: The AEAT modelo identifier.
        period: The :class:`~cadrumo.core.Period` covered, serialised as
            ``{"filing_year": int, "code": str}`` across the persistence
            boundary.
        profile_tax_id: The validated taxpayer identity value carried
            by the upstream draft or imported receipt.
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

    submission_id: SubmissionId
    draft_id: str = Field(min_length=1)
    modelo: Modelo
    period: Period
    profile_tax_id: SubjectTaxId = Field(min_length=1)
    status: SubmissionStatus
    justificante_csv: AeatCsv | None = None
    justificante_pdf_path: Path | None = None
    submitted_at: datetime
    acknowledged_at: datetime | None = None
    attempts: tuple[SubmissionAttempt, ...] = Field(min_length=1)

    @field_validator("modelo", mode="before")
    @classmethod
    def _coerce_modelo(cls, value: object) -> Modelo:
        """Resolve the filing's modelo through the canonical closed identity.

        This record is a durable filing identity, and the listing engine
        filters history by raw equality on this field. A length-only string
        let an unknown code, or a whitespace-padded spelling of a known one,
        become a historical filing that no later lookup by canonical code
        would ever match.
        """
        if isinstance(value, Modelo):
            return value
        if isinstance(value, str):
            try:
                return Modelo(value)
            except ValueError as exc:
                raise SubmissionValidationError(
                    f"modelo {value!r} is not a canonical AEAT modelo identifier",
                ) from exc
        raise SubmissionValidationError(f"modelo must be a Modelo or str, got {type(value).__name__}")

    @model_validator(mode="after")
    def _check_ack_consistency(self) -> ModeloPresentado:
        """Enforce ``ACEPTADA`` ↔ justificante-present invariants."""
        try:
            validate_utc_aware(self.submitted_at)
            if self.acknowledged_at is not None:
                validate_utc_aware(self.acknowledged_at)
        except ValueError as exc:
            raise SubmissionValidationError(str(exc)) from exc
        if self.status is SubmissionStatus.ACEPTADA:
            if not self.justificante_csv or not self.justificante_pdf_path:
                raise SubmissionValidationError(
                    "status ACEPTADA requires both justificante_csv and justificante_pdf_path",
                )
            if not self.acknowledged_at:
                raise SubmissionValidationError("status ACEPTADA requires acknowledged_at")
        if self.acknowledged_at and self.acknowledged_at < self.submitted_at:
            raise SubmissionValidationError(
                f"acknowledged_at ({self.acknowledged_at}) is before submitted_at ({self.submitted_at})",
            )
        return self

    @model_validator(mode="after")
    def _check_attempt_coordinates(self) -> ModeloPresentado:
        """Bind every attempt to this submission at its own ordinal position.

        ``attempt_id`` is documented as ``<submission_id>.<ordinal>``, so the
        tuple index and the identifier are two spellings of one fact. Checking
        them against each other makes parent binding, ordinal positivity,
        uniqueness, and tuple ordering a single enforced coordinate rather than
        four conventions the producer happens to honour.
        """
        for index, attempt in enumerate(self.attempts, start=1):
            expected = f"{self.submission_id}.{index}"
            if attempt.attempt_id != expected:
                raise SubmissionValidationError(
                    f"attempt {index} carries attempt_id {attempt.attempt_id!r}; "
                    f"this submission's attempt {index} is {expected!r}",
                )
        return self

    @model_validator(mode="after")
    def _check_attempt_chronology_and_status(self) -> ModeloPresentado:
        """Enforce the documented aggregate contract over the attempt history.

        Three separate claims the record makes about itself were unchecked: the
        attempts are in chronological order, ``submitted_at`` is the first
        attempt's start, and the aggregate status is coherent with how the last
        attempt ended. Without them the record could report an ACEPTADA filing
        whose only attempt FAILED -- an audit trail that contradicts its own
        evidence.
        """
        previous_start = self.attempts[0].started_at
        for attempt in self.attempts[1:]:
            if attempt.started_at < previous_start:
                raise SubmissionValidationError(
                    f"attempt {attempt.attempt_id!r} starts at {attempt.started_at} "
                    f"before the preceding attempt at {previous_start}",
                )
            previous_start = attempt.started_at
        if self.submitted_at != self.attempts[0].started_at:
            raise SubmissionValidationError(
                f"submitted_at ({self.submitted_at}) must be the first attempt's start ({self.attempts[0].started_at})",
            )
        terminal = self.attempts[-1].status
        permitted = _AGGREGATE_STATUS_BY_TERMINAL_ATTEMPT[terminal]
        if self.status not in permitted:
            accepted = ", ".join(sorted(status.value for status in permitted))
            raise SubmissionValidationError(
                f"status {self.status.value} is not coherent with a terminal "
                f"{terminal.value} attempt; accepted: {accepted}",
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
        SubmissionValidationError: If ``draft_id`` is empty or
            ``attempt_ordinal`` is not a positive integer.
    """
    if not draft_id:
        raise SubmissionValidationError("draft_id must be non-empty")
    if attempt_ordinal < 1:
        raise SubmissionValidationError(f"attempt_ordinal must be >= 1, got {attempt_ordinal}")
    payload = f"{draft_id}:{attempt_ordinal}".encode()
    return sha256_hex(payload)[:16]

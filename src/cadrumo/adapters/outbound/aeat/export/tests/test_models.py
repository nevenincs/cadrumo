"""Unit tests for the strict pydantic v2 submission domain models.

Covers :class:`SubmissionAttempt`, :class:`ModeloPresentado`, and
:func:`make_submission_id`. Each test pins one validator or invariant
(extra-fields rejection, frozen mutation, ordering constraints, etc.)
so that schema drift surfaces deterministically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.period import Period
from ......domain.submission.models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# The attempt coordinate is `<submission_id>.<ordinal>`, so the fixture derives
# both from one content-addressed id rather than naming them independently.
_SUBMISSION_ID = make_submission_id("draft-1", 1)
_ATTEMPT_ID = f"{_SUBMISSION_ID}.1"


def _attempt(
    *,
    status: SubmissionStatus = SubmissionStatus.PRESENTADA,
) -> SubmissionAttempt:
    """Build a deterministic :class:`SubmissionAttempt` for fixture reuse."""
    return SubmissionAttempt(
        attempt_id=_ATTEMPT_ID,
        started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=UTC),
        status=status,
    )


class TestSubmissionAttempt:
    """Invariants for :class:`SubmissionAttempt`."""

    def test_extra_fields_rejected(self) -> None:
        """Assert ``extra="forbid"`` rejects unknown keys."""
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            SubmissionAttempt.model_validate(
                {
                    "attempt_id": _ATTEMPT_ID,
                    "started_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "ended_at": datetime(2026, 4, 12, 10, 0, 1, tzinfo=UTC),
                    "status": "SUBMITTED",
                    "extra": "nope",
                },
            )

    def test_frozen(self) -> None:
        """Assert the model is frozen (mutating an attribute raises)."""
        attempt = _attempt()
        with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
            attempt.attempt_id = f"{_SUBMISSION_ID}.2"

    def test_end_before_start_rejected(self) -> None:
        """Assert ``ended_at < started_at`` is rejected by validation."""
        with pytest.raises(ValidationError, match=r"ended_at|started_at"):
            SubmissionAttempt(
                attempt_id=_ATTEMPT_ID,
                started_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=UTC),
                ended_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                status=SubmissionStatus.PRESENTADA,
            )

    def test_status_must_be_known(self) -> None:
        """Assert an unknown status string is rejected."""
        with pytest.raises(ValidationError, match=r"status|Input should be"):
            SubmissionAttempt.model_validate(
                {
                    "attempt_id": _ATTEMPT_ID,
                    "started_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "ended_at": datetime(2026, 4, 12, 10, 0, 1, tzinfo=UTC),
                    "status": "WHATEVER",
                },
            )


class TestModeloPresentado:
    """Invariants for :class:`ModeloPresentado`."""

    def _filing(self, **overrides: object) -> ModeloPresentado:
        """Build a baseline :class:`ModeloPresentado`, applying ``overrides``."""
        base: dict[str, object] = dict(
            submission_id=_SUBMISSION_ID,
            draft_id="draft-1",
            modelo="130",
            period=Period.from_year_and_code(2026, "1T"),
            profile_tax_id="X1234567L",
            status=SubmissionStatus.PRESENTADA,
            # submitted_at is the first attempt's start, not a free field.
            submitted_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
            attempts=(_attempt(),),
        )
        base.update(overrides)
        return ModeloPresentado.model_validate(base)

    def test_happy_path(self) -> None:
        """Assert the canonical baseline filing validates and exposes its attempts."""
        filing = self._filing()
        assert filing.status is SubmissionStatus.PRESENTADA
        assert filing.attempts[0].attempt_id == _ATTEMPT_ID

    def test_extra_fields_rejected(self) -> None:
        """Assert ``extra="forbid"`` rejects unknown keys on :class:`ModeloPresentado`."""
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            ModeloPresentado.model_validate(
                {
                    "submission_id": _SUBMISSION_ID,
                    "draft_id": "draft-1",
                    "modelo": "130",
                    "period": Period.from_year_and_code(2026, "1T"),
                    "profile_tax_id": "X1234567L",
                    "status": "SUBMITTED",
                    "submitted_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "attempts": [_attempt().model_dump()],
                    "extra": "nope",
                },
            )

    def test_attempts_must_be_nonempty(self) -> None:
        """Assert ``attempts`` cannot be empty."""
        with pytest.raises(ValidationError, match=r"attempts|at least 1"):
            self._filing(attempts=())

    def test_acknowledged_requires_justificante(self) -> None:
        """Assert ``ACKNOWLEDGED`` status requires a ``justificante_csv`` + PDF path."""
        with pytest.raises(ValidationError, match=r"justificante|ACKNOWLEDGED"):
            self._filing(
                status=SubmissionStatus.ACEPTADA,
                acknowledged_at=datetime(2026, 4, 12, 10, 5, 0, tzinfo=UTC),
            )

    def test_acknowledged_requires_acknowledged_at(self) -> None:
        """Assert ``ACKNOWLEDGED`` status requires ``acknowledged_at``."""
        with pytest.raises(ValidationError, match=r"acknowledged_at|ACKNOWLEDGED"):
            self._filing(
                status=SubmissionStatus.ACEPTADA,
                justificante_csv="FIXTURECSV1234X7",
                justificante_pdf_path=Path("var/j.pdf"),
            )

    def test_ack_before_submit_rejected(self) -> None:
        """Assert ``acknowledged_at < submitted_at`` is rejected."""
        with pytest.raises(ValidationError, match=r"acknowledged_at|submitted_at"):
            self._filing(
                acknowledged_at=datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC),
            )

    def test_round_trip(self) -> None:
        """Assert a fully ``ACKNOWLEDGED`` filing round-trips through JSON serialisation."""
        filing = self._filing(
            status=SubmissionStatus.ACEPTADA,
            justificante_csv="FIXTURECSVACK001",
            justificante_pdf_path=Path("var/submissions/j1.pdf"),
            acknowledged_at=datetime(2026, 4, 12, 10, 5, 0, tzinfo=UTC),
        )
        restored = ModeloPresentado.model_validate_json(filing.model_dump_json())
        assert restored == filing


class TestMakeSubmissionId:
    """Invariants for :func:`make_submission_id`."""

    def test_ordinal_changes_hash(self) -> None:
        """Assert a different ``ordinal`` produces a different id."""
        assert make_submission_id("draft-1", 1) != make_submission_id("draft-1", 2)

    def test_draft_changes_hash(self) -> None:
        """Assert a different ``draft_id`` produces a different id."""
        assert make_submission_id("draft-1", 1) != make_submission_id("draft-2", 1)

    def test_empty_draft_id_rejected(self) -> None:
        """Assert an empty ``draft_id`` raises :exc:`ValueError`."""
        with pytest.raises(ValueError, match=r"draft_id"):
            make_submission_id("", 1)

    def test_non_positive_ordinal_rejected(self) -> None:
        """Assert a non-positive ``ordinal`` raises :exc:`ValueError`."""
        with pytest.raises(ValueError, match=r"attempt_ordinal"):
            make_submission_id("draft-1", 0)

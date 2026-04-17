"""Unit tests for the strict pydantic v2 models in :mod:`aeat.submission._models`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from . import (
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)

pytestmark = pytest.mark.unit


def _attempt(
    *,
    status: SubmissionStatus = SubmissionStatus.SUBMITTED,
) -> SubmissionAttempt:
    return SubmissionAttempt(
        attempt_id="a1",
        started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=UTC),
        status=status,
    )


class TestSubmissionAttempt:
    """Invariants for :class:`SubmissionAttempt`."""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SubmissionAttempt.model_validate(
                {
                    "attempt_id": "a1",
                    "started_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "ended_at": datetime(2026, 4, 12, 10, 0, 1, tzinfo=UTC),
                    "status": "SUBMITTED",
                    "extra": "nope",
                }
            )

    def test_frozen(self) -> None:
        attempt = _attempt()
        with pytest.raises(ValidationError):
            attempt.attempt_id = "a2"  # type: ignore[misc]

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SubmissionAttempt(
                attempt_id="a1",
                started_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=UTC),
                ended_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                status=SubmissionStatus.SUBMITTED,
            )

    def test_status_must_be_known(self) -> None:
        with pytest.raises(ValidationError):
            SubmissionAttempt.model_validate(
                {
                    "attempt_id": "a1",
                    "started_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "ended_at": datetime(2026, 4, 12, 10, 0, 1, tzinfo=UTC),
                    "status": "WHATEVER",
                }
            )


class TestSubmittedFiling:
    """Invariants for :class:`SubmittedFiling`."""

    def _filing(self, **overrides: object) -> SubmittedFiling:
        base: dict[str, object] = dict(
            submission_id=make_submission_id("draft-1", 1),
            draft_id="draft-1",
            modelo="130",
            period="2026Q1",
            profile_tax_id="X1234567L",
            status=SubmissionStatus.SUBMITTED,
            submitted_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=UTC),
            attempts=(_attempt(),),
        )
        base.update(overrides)
        return SubmittedFiling.model_validate(base)

    def test_happy_path(self) -> None:
        filing = self._filing()
        assert filing.status is SubmissionStatus.SUBMITTED
        assert filing.attempts[0].attempt_id == "a1"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SubmittedFiling.model_validate(
                {
                    "submission_id": "x",
                    "draft_id": "draft-1",
                    "modelo": "130",
                    "period": "2026Q1",
                    "profile_tax_id": "X1",
                    "status": "SUBMITTED",
                    "submitted_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
                    "attempts": [_attempt().model_dump()],
                    "extra": "nope",
                }
            )

    def test_attempts_must_be_nonempty(self) -> None:
        with pytest.raises(ValidationError):
            self._filing(attempts=())

    def test_acknowledged_requires_justificante(self) -> None:
        with pytest.raises(ValidationError):
            self._filing(
                status=SubmissionStatus.ACKNOWLEDGED,
                acknowledged_at=datetime(2026, 4, 12, 10, 5, 0, tzinfo=UTC),
            )

    def test_acknowledged_requires_acknowledged_at(self) -> None:
        with pytest.raises(ValidationError):
            self._filing(
                status=SubmissionStatus.ACKNOWLEDGED,
                justificante_csv="CSV123",
                justificante_pdf_path=Path("var/j.pdf"),
            )

    def test_ack_before_submit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._filing(
                acknowledged_at=datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC),
            )

    def test_round_trip(self) -> None:
        filing = self._filing(
            status=SubmissionStatus.ACKNOWLEDGED,
            justificante_csv="CSV-ACK-1",
            justificante_pdf_path=Path("var/submissions/j1.pdf"),
            acknowledged_at=datetime(2026, 4, 12, 10, 5, 0, tzinfo=UTC),
        )
        restored = SubmittedFiling.model_validate_json(filing.model_dump_json())
        assert restored == filing


class TestMakeSubmissionId:
    """Invariants for :func:`make_submission_id`."""

    def test_stable(self) -> None:
        assert make_submission_id("draft-1", 1) == make_submission_id("draft-1", 1)

    def test_ordinal_changes_hash(self) -> None:
        assert make_submission_id("draft-1", 1) != make_submission_id("draft-1", 2)

    def test_draft_changes_hash(self) -> None:
        assert make_submission_id("draft-1", 1) != make_submission_id("draft-2", 1)

    def test_empty_draft_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_submission_id("", 1)

    def test_non_positive_ordinal_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_submission_id("draft-1", 0)

"""Tests for the idle-timeout evaluator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ...errors import StorageValidationError
from .._idle_timeout import (
    DEFAULT_IDLE_LOCK_MINUTES,
    IdleEvaluation,
    evaluate_idle,
)
from ..bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_BUCKET_ID = "66666666-6666-4666-8666-666666666666"


def _open_session(idle_minutes: int = 15) -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=bytes(range(32)),
        dek=bytes(range(32, 64)),
        idle_minutes=idle_minutes,
        opened_at=_NOW,
    )


def test_default_idle_lock_minutes_is_fifteen() -> None:
    """Default idle-lock is 15 minutes."""

    assert DEFAULT_IDLE_LOCK_MINUTES == 15


def test_evaluate_idle_returns_not_expired_inside_window() -> None:
    session = _open_session(idle_minutes=15)

    evaluation = evaluate_idle(
        session=session,
        now=_NOW + timedelta(minutes=10),
        configured_minutes=15,
    )

    assert evaluation.expired is False
    assert evaluation.remaining_seconds == 5 * 60


def test_evaluate_idle_returns_expired_past_window() -> None:
    session = _open_session(idle_minutes=15)

    evaluation = evaluate_idle(
        session=session,
        now=_NOW + timedelta(minutes=16),
        configured_minutes=15,
    )

    assert evaluation.expired is True
    assert evaluation.remaining_seconds == 0


def test_evaluate_idle_at_exact_deadline_is_expired() -> None:
    session = _open_session(idle_minutes=15)

    evaluation = evaluate_idle(
        session=session,
        now=_NOW + timedelta(minutes=15),
        configured_minutes=15,
    )

    assert evaluation.expired is True


def test_evaluate_idle_treats_sealed_session_as_expired() -> None:
    session = _open_session(idle_minutes=15)
    session.close()

    evaluation = evaluate_idle(session=session, now=_NOW, configured_minutes=15)

    assert evaluation.expired is True
    assert evaluation.remaining_seconds == 0


def test_touch_rolls_deadline_forward() -> None:
    """After `touch`, a previously-expired session reads as fresh."""

    session = _open_session(idle_minutes=15)
    past = _NOW + timedelta(minutes=20)
    assert evaluate_idle(session=session, now=past, configured_minutes=15).expired is True

    session.touch(past)

    assert evaluate_idle(session=session, now=past + timedelta(minutes=10), configured_minutes=15).expired is False
    assert evaluate_idle(session=session, now=past + timedelta(minutes=16), configured_minutes=15).expired is True


def test_evaluate_idle_rejects_non_positive_configured_minutes() -> None:
    session = _open_session(idle_minutes=15)

    with pytest.raises(StorageValidationError, match="strict positive") as zero_exc:
        evaluate_idle(session=session, now=_NOW, configured_minutes=0)
    assert zero_exc.value.translated_message == "errors.integrity.integrity_storage_validation"

    with pytest.raises(StorageValidationError, match="strict positive") as negative_exc:
        evaluate_idle(session=session, now=_NOW, configured_minutes=-5)
    assert negative_exc.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_evaluate_idle_is_pure_does_not_mutate_session() -> None:
    """The evaluator never calls `touch`; the caller owns mutation."""

    session = _open_session(idle_minutes=15)
    original_deadline = session.idle_deadline

    evaluate_idle(session=session, now=_NOW + timedelta(minutes=5), configured_minutes=15)
    evaluate_idle(session=session, now=_NOW + timedelta(minutes=20), configured_minutes=15)

    assert session.idle_deadline == original_deadline


def test_idle_evaluation_record_is_strict_pydantic() -> None:
    evaluation = IdleEvaluation(expired=False, remaining_seconds=42)

    assert evaluation.expired is False
    assert evaluation.remaining_seconds == 42
    # Strict: unknown keys rejected
    with pytest.raises(ValueError):
        IdleEvaluation.model_validate({"expired": False, "remaining_seconds": 42, "extra": "nope"})
    # Strict: negative remaining_seconds rejected
    invalid_remaining: int = -1
    with pytest.raises(ValueError):
        IdleEvaluation(expired=True, remaining_seconds=invalid_remaining)

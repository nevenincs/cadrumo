"""The throttle sidecar's instant obeys the canonical UTC contract.

The backoff decision is a single comparison against ``last_failure_at``, so
that field's awareness is load-bearing. As a bare ``datetime`` it admitted two
shapes no writer in this codebase produces, each with its own failure:

- A *naive* stamp loaded cleanly and then made the evaluation raise a raw
  ``TypeError`` comparing offset-naive and offset-aware datetimes -- out of a
  security gate whose whole contract is that an unusable sidecar reads as
  cleared.
- A stamp carrying a non-UTC *offset* loaded cleanly and shifted the deadline
  by that offset. A ``+01:00`` value described an instant an hour earlier than
  its digits suggest, so the gate reported the operator clear to retry while
  the same wall-clock instant written in UTC was still throttled.

Typing the field as :data:`~core.time.UtcInstant` routes both through the
module's documented unreadable-means-cleared path. Clearing rather than
refusing is deliberate: this sidecar is a revocable cache, a hard refusal
could strand the legitimate operator, and anyone able to write the file could
equally delete it -- so clearing grants no capability that removal did not.

Real files under a real keystore directory throughout; the sidecars are
written as raw JSON precisely because the production writer cannot emit these
shapes, which is the point.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..login_throttle import (
    LOGIN_THROTTLE_SCHEMA_VERSION,
    LoginThrottleState,
    ThrottleEvaluation,
    evaluate_login_throttle,
    login_throttle_path,
    record_login_failure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_FAILURES = 3

#: The instant every variant below names, in the three spellings under test.
_CANONICAL = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_NAIVE = _CANONICAL.replace(tzinfo=None)
_OFFSET = _CANONICAL.astimezone(timezone(timedelta(hours=1)))
#: One second after the stamp: inside the 8-second window three failures buy.
_NOW = _CANONICAL + timedelta(seconds=1)

_NON_UTC_STAMPS = (
    pytest.param(_NAIVE.isoformat(), id="naive"),
    pytest.param(_OFFSET.isoformat(), id="plus-one-hour"),
    pytest.param(_CANONICAL.astimezone(timezone(timedelta(hours=-5))).isoformat(), id="minus-five-hours"),
)


def _write_sidecar(root: Path, stamp: str) -> Path:
    """Write a throttle sidecar carrying ``stamp`` verbatim."""
    path = login_throttle_path(storage_root=root, bucket_id=_BUCKET_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": LOGIN_THROTTLE_SCHEMA_VERSION,
                "consecutive_failures": _FAILURES,
                "last_failure_at": stamp,
            },
        ),
        encoding="utf-8",
    )
    return path


def _evaluate(root: Path, now: datetime) -> ThrottleEvaluation:
    return evaluate_login_throttle(storage_root=root, bucket_id=_BUCKET_ID, now=now)


def test_a_canonical_utc_sidecar_throttles(tmp_path: Path) -> None:
    """Positive control: the shape the production writer emits still throttles.

    Every refusal below is only meaningful against this. Without it, a fix
    that broke the sidecar reader outright would make the whole module green.
    """
    _write_sidecar(tmp_path, _CANONICAL.isoformat())

    evaluation = _evaluate(tmp_path, _NOW)

    assert evaluation.throttled is True
    assert evaluation.consecutive_failures == _FAILURES
    assert evaluation.remaining_seconds > 0


@pytest.mark.parametrize("stamp", _NON_UTC_STAMPS)
def test_a_non_utc_sidecar_is_refused_at_the_model_boundary(stamp: str) -> None:
    """The state model itself refuses the awareness it cannot compare."""
    with pytest.raises(ValidationError):
        LoginThrottleState.model_validate(
            {
                "schema_version": LOGIN_THROTTLE_SCHEMA_VERSION,
                "consecutive_failures": _FAILURES,
                "last_failure_at": stamp,
            },
        )


@pytest.mark.parametrize("stamp", _NON_UTC_STAMPS)
def test_a_non_utc_sidecar_evaluates_as_cleared_rather_than_raising(tmp_path: Path, stamp: str) -> None:
    """The gate returns a cleared verdict; it neither crashes nor half-trusts.

    The naive case previously escaped as a raw ``TypeError``, and the offset
    cases previously returned an answer computed from a shifted deadline.
    Asserting the full cleared triple -- not merely "did not raise" -- is what
    distinguishes clearing from silently trusting a mis-shifted stamp.
    """
    _write_sidecar(tmp_path, stamp)

    evaluation = _evaluate(tmp_path, _NOW)

    assert evaluation.throttled is False
    assert evaluation.remaining_seconds == 0
    assert evaluation.consecutive_failures == 0


def test_an_offset_stamp_would_otherwise_disagree_with_its_own_utc_instant(tmp_path: Path) -> None:
    """The offset spelling names the same instant the canonical one does.

    This is the discriminating assertion for the *silent* half of the defect.
    A reader that merely accepted the offset stamp would answer differently
    for two spellings of one instant; the two sidecars here differ in nothing
    but spelling, so any divergence in the verdict is the bug.
    """
    assert _OFFSET == _CANONICAL
    assert _OFFSET.isoformat() != _CANONICAL.isoformat()

    _write_sidecar(tmp_path, _CANONICAL.isoformat())
    canonical_verdict = _evaluate(tmp_path, _NOW)
    _write_sidecar(tmp_path, _OFFSET.isoformat())
    offset_verdict = _evaluate(tmp_path, _NOW)

    assert canonical_verdict.throttled is True
    assert offset_verdict.throttled is False


def test_recording_a_failure_rewrites_a_canonical_sidecar(tmp_path: Path) -> None:
    """The cleared state is transient: the next failure restores a real record.

    Pins the module's stated recovery contract -- an unusable sidecar clears,
    and the following ``record_login_failure`` writes a canonical file -- so
    the clearing above cannot be mistaken for a throttle that stays disabled.
    """
    _write_sidecar(tmp_path, _NAIVE.isoformat())
    assert _evaluate(tmp_path, _NOW).throttled is False

    state = record_login_failure(storage_root=tmp_path, bucket_id=_BUCKET_ID, now=_NOW)

    assert state.consecutive_failures == 1
    assert state.last_failure_at == _NOW
    assert _evaluate(tmp_path, _NOW).throttled is True


def test_recording_a_failure_refuses_a_non_utc_instant(tmp_path: Path) -> None:
    """A naive ``now`` is refused at the write side rather than persisted.

    Closing the read side alone would leave the writer free to produce the
    very file the reader must then discard, turning a caller's clock bug into
    a silently disabled throttle.
    """
    with pytest.raises(ValidationError):
        record_login_failure(storage_root=tmp_path, bucket_id=_BUCKET_ID, now=_NAIVE)

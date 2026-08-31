"""Real-file tests for the per-bucket failed-login throttle sidecar.

The ``"keystore"`` literal in the sidecar-location assertion is deliberate.
``login_throttle_path`` resolves through ``keystore_sidecar_path``, which reads
``storage_location(StorageCategory.BUCKET_KEYSTORE)``, so expressing the
expected side through the same accessor would move both sides together and the
assertion would hold no matter where the sidecar landed. What it defends is
that throttle state is written *inside the keystore* rather than beside it --
a placement claim about the filesystem, not a lookup. Keep the literal.


The throttle is driven through real files under a real keystore directory
(no mocks, no patched clock): every test supplies an explicit ``now`` and
inspects the on-disk sidecar the production writer produced.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest

from ..login_throttle import (
    LOGIN_THROTTLE_FILENAME,
    LOGIN_THROTTLE_SCHEMA_VERSION,
    THROTTLE_BACKOFF_CAP_SECONDS,
    LoginThrottleState,
    ThrottleEvaluation,
    evaluate_login_throttle,
    login_throttle_path,
    record_login_failure,
    reset_login_throttle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"keystore"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_BUCKET_ID = "77777777-7777-4777-8777-777777777777"


def _path(root: Path) -> Path:
    return login_throttle_path(storage_root=root, bucket_id=_BUCKET_ID)


def _evaluate(root: Path, now: datetime) -> ThrottleEvaluation:
    return evaluate_login_throttle(storage_root=root, bucket_id=_BUCKET_ID, now=now)


def _record(root: Path, now: datetime) -> LoginThrottleState:
    return record_login_failure(storage_root=root, bucket_id=_BUCKET_ID, now=now)


def test_no_sidecar_is_not_throttled(tmp_path: Path) -> None:
    evaluation = _evaluate(tmp_path, _NOW)

    assert evaluation.throttled is False
    assert evaluation.remaining_seconds == 0
    assert evaluation.consecutive_failures == 0
    assert not _path(tmp_path).exists()


def test_first_failure_writes_a_real_sidecar_in_the_keystore(tmp_path: Path) -> None:
    state = _record(tmp_path, _NOW)

    path = _path(tmp_path)
    assert path.is_file()
    assert path.name == LOGIN_THROTTLE_FILENAME
    assert path.parent == tmp_path / "keystore" / _BUCKET_ID
    assert state.consecutive_failures == 1
    assert state.last_failure_at == _NOW


def test_first_failure_imposes_two_second_backoff(tmp_path: Path) -> None:
    _record(tmp_path, _NOW)

    immediate = _evaluate(tmp_path, _NOW)
    assert immediate.throttled is True
    assert immediate.remaining_seconds == 2  # 2 ** 1
    assert immediate.consecutive_failures == 1

    # Waiting the window out clears the throttle without a reset.
    cleared = _evaluate(tmp_path, _NOW + timedelta(seconds=2))
    assert cleared.throttled is False
    assert cleared.remaining_seconds == 0


@pytest.mark.parametrize(
    ("failures", "expected_wait"),
    [
        (1, 2),
        (2, 4),
        (3, 8),
        (4, 16),
        (5, 32),
        (6, THROTTLE_BACKOFF_CAP_SECONDS),  # 2 ** 6 == 64, capped at 60
        (7, THROTTLE_BACKOFF_CAP_SECONDS),
        (10, THROTTLE_BACKOFF_CAP_SECONDS),
    ],
)
def test_exponential_backoff_capped_at_sixty(tmp_path: Path, failures: int, expected_wait: int) -> None:
    last: datetime = _NOW
    for offset in range(failures):
        last = _NOW + timedelta(hours=offset)
        _record(tmp_path, last)

    evaluation = _evaluate(tmp_path, last)
    assert evaluation.consecutive_failures == failures
    assert evaluation.throttled is True
    assert evaluation.remaining_seconds == expected_wait

    # One second past the window is clear to retry.
    assert _evaluate(tmp_path, last + timedelta(seconds=expected_wait)).throttled is False


def test_remaining_seconds_counts_down_and_rounds_up(tmp_path: Path) -> None:
    _record(tmp_path, _NOW)  # window == 2 s
    _record(tmp_path, _NOW)  # window == 4 s (second consecutive failure)

    # 1.5 s elapsed of a 4 s window => 2.5 s remaining, rounded up to 3.
    partial = _evaluate(tmp_path, _NOW + timedelta(seconds=1.5))
    assert partial.throttled is True
    assert partial.remaining_seconds == 3


def test_reset_on_success_clears_the_counter_and_removes_the_file(tmp_path: Path) -> None:
    _record(tmp_path, _NOW)
    _record(tmp_path, _NOW)
    assert _evaluate(tmp_path, _NOW).throttled is True

    reset_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID)

    assert not _path(tmp_path).exists()
    cleared = _evaluate(tmp_path, _NOW)
    assert cleared.throttled is False
    assert cleared.consecutive_failures == 0


def test_reset_is_idempotent_when_no_sidecar_exists(tmp_path: Path) -> None:
    # No failure recorded yet; reset must be a clean no-op.
    reset_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID)
    reset_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID)

    assert not _path(tmp_path).exists()


def test_failure_count_restarts_from_one_after_reset(tmp_path: Path) -> None:
    for _ in range(4):
        _record(tmp_path, _NOW)
    assert _evaluate(tmp_path, _NOW).remaining_seconds == 16  # 2 ** 4

    reset_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID)

    # The next failure starts a fresh backoff schedule at 2 s, proving the
    # reset zeroed the count rather than merely clearing the timestamp.
    state = _record(tmp_path, _NOW)
    assert state.consecutive_failures == 1
    assert _evaluate(tmp_path, _NOW).remaining_seconds == 2


def test_sidecar_holds_only_plaintext_counts_and_timestamps(tmp_path: Path) -> None:
    _record(tmp_path, _NOW)

    payload = json.loads(_path(tmp_path).read_text(encoding="utf-8"))
    assert set(payload) == {"schema_version", "consecutive_failures", "last_failure_at"}
    assert payload["schema_version"] == LOGIN_THROTTLE_SCHEMA_VERSION
    assert payload["consecutive_failures"] == 1
    assert datetime.fromisoformat(payload["last_failure_at"]) == _NOW


def test_recorded_state_round_trips_from_disk(tmp_path: Path) -> None:
    _record(tmp_path, _NOW)
    _record(tmp_path, _NOW + timedelta(seconds=5))

    loaded = LoginThrottleState.model_validate_json(_path(tmp_path).read_text(encoding="utf-8"))
    assert loaded == LoginThrottleState(
        schema_version=LOGIN_THROTTLE_SCHEMA_VERSION,
        consecutive_failures=2,
        last_failure_at=_NOW + timedelta(seconds=5),
    )


def test_corrupt_sidecar_is_treated_as_cleared_no_lockout(tmp_path: Path) -> None:
    path = _path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not valid json", encoding="utf-8")

    # A corrupt sidecar must never permanently lock the operator out.
    evaluation = _evaluate(tmp_path, _NOW)
    assert evaluation.throttled is False
    assert evaluation.consecutive_failures == 0

    # The next failure rewrites a canonical file starting from one.
    state = _record(tmp_path, _NOW)
    assert state.consecutive_failures == 1
    assert LoginThrottleState.model_validate_json(path.read_text(encoding="utf-8")).consecutive_failures == 1


def test_schema_version_mismatch_is_treated_as_cleared(tmp_path: Path) -> None:
    path = _path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": LOGIN_THROTTLE_SCHEMA_VERSION + 1,
                "consecutive_failures": 9,
                "last_failure_at": _NOW.isoformat(),
            },
        ),
        encoding="utf-8",
    )

    evaluation = _evaluate(tmp_path, _NOW)
    assert evaluation.throttled is False
    assert evaluation.consecutive_failures == 0


def test_throttle_evaluation_record_is_strict_pydantic() -> None:
    evaluation = ThrottleEvaluation(throttled=True, remaining_seconds=8, consecutive_failures=3)

    assert evaluation.throttled is True
    assert evaluation.remaining_seconds == 8
    with pytest.raises(ValueError):
        ThrottleEvaluation.model_validate(
            {"throttled": True, "remaining_seconds": 8, "consecutive_failures": 3, "extra": "nope"},
        )
    invalid_remaining: int = -1
    with pytest.raises(ValueError):
        ThrottleEvaluation(throttled=True, remaining_seconds=invalid_remaining, consecutive_failures=1)

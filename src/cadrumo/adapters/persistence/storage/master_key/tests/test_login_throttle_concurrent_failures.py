"""Concurrent failed logins do not collapse the consecutive-failure counter.

The throttle is the brute-force control: after ``n`` consecutive failures the
caller must wait ``min(2 ** n, 60)`` seconds BEFORE any Argon2id derivation
runs, so the KDF cannot become a passphrase-testing oracle. That guarantee is
carried entirely by ``n``.

``record_login_failure`` reads the sidecar, adds one, and writes it back. With
no mutual exclusion, attempts that overlap all read the same ``n`` and all
write ``n + 1``, so a burst of ``k`` wrong passwords advances the counter once
instead of ``k`` times. The operator sees a two-second backoff where the
control owes them minutes, and the exponential curve the control is named for
never starts climbing.

This is reachable without any privileged position: the surface is a local CLI,
so an attacker with local access simply runs the login verb ``k`` times at
once. Unlike the sidecar's documented tolerances -- a missing, unreadable or
version-mismatched file is deliberately treated as "no active throttle" so a
legitimate operator is never stranded -- a lost increment weakens the control
against the attacker rather than protecting the operator, and is not a
tolerance anything declared.

Driven through the real production writer against a real keystore directory on
disk. Nothing is mocked, patched or stubbed; the only test-side apparatus is a
barrier that releases the threads together, which narrows the window the defect
needs rather than creating it.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .._login_throttle import (
    evaluate_login_throttle,
    record_login_failure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_BUCKET_ID = "78787878-7878-4787-8787-787878787878"

#: Concurrent wrong-password attempts. Chosen well above the two-attempt
#: minimum that would demonstrate the defect, because the counter it protects
#: is exponential: at eight the correct backoff is the 60s cap and a collapsed
#: counter yields two seconds, so the assertion separates the two states by the
#: whole useful range of the control rather than by one step.
_ATTEMPTS = 8


def _record_together(root: Path, attempts: int) -> None:
    """Run ``attempts`` failure recordings released from one barrier."""
    barrier = threading.Barrier(attempts)

    def _one() -> None:
        barrier.wait()
        record_login_failure(storage_root=root, bucket_id=_BUCKET_ID, now=_NOW)

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        for future in [pool.submit(_one) for _ in range(attempts)]:
            future.result()


def test_sequential_failures_accumulate(tmp_path: Path) -> None:
    """Baseline: the counter is not lossy on its own."""
    for _ in range(_ATTEMPTS):
        record_login_failure(storage_root=tmp_path, bucket_id=_BUCKET_ID, now=_NOW)

    evaluation = evaluate_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID, now=_NOW)
    assert evaluation.consecutive_failures == _ATTEMPTS


def test_concurrent_failures_each_advance_the_counter(tmp_path: Path) -> None:
    """DISCRIMINATING: every overlapping wrong password must still be counted.

    A burst is exactly the shape an attacker produces and exactly the shape a
    read-modify-write loses. Anything below ``_ATTEMPTS`` means attempts were
    discarded, and the backoff the next attempt faces was computed from a
    count that under-reports what the bucket actually saw.
    """
    _record_together(tmp_path, _ATTEMPTS)

    evaluation = evaluate_login_throttle(storage_root=tmp_path, bucket_id=_BUCKET_ID, now=_NOW)
    assert evaluation.consecutive_failures == _ATTEMPTS, (
        f"{_ATTEMPTS} concurrent failed logins advanced the throttle to "
        f"{evaluation.consecutive_failures}; the lost attempts leave the next attempt facing "
        f"a {evaluation.remaining_seconds}s backoff instead of the cap this many failures owe"
    )

"""Real-behaviour concurrency regression for the usage-ratio load-modify-save.

The usage-ratio profile is a single :class:`SecureObjectRepository` row per
bucket. ``ratios set`` / ``ratios unset`` (and the censo home-office seed) each
read that row, mutate one entry, and write the whole row back. Before the
per-bucket lock landed this read-modify-write span was unguarded, so two
concurrent writers each loaded the same snapshot, applied their own change, and
the second save silently dropped the first writer's category — a classic lost
update. The encrypted-SQLite ``busy_timeout`` / WAL only serialises individual
write transactions; it does not make the cross-transaction span atomic.

These tests spawn genuinely concurrent writers against the REAL secure
repository (no mocks) and assert that every distinct-category override survives,
and that the guarding lock is a real mutual-exclusion primitive rather than a
silent no-op. Run against the pre-fix (lock-free) code path the survival test
fails (only one of N categories survives, plus transaction-conflict errors);
with the per-bucket :func:`cadrumo.domain.usage_ratios.usage_ratio_bucket_lock`
held across the load-modify-save the writers serialise and all survive.
"""

from __future__ import annotations

import contextvars
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.usage_ratios import load_usage_ratios
from ....core.config import override_settings
from ....core.locks_errors import LockAcquisitionError
from ....domain.categories.spending_category import SpendingCategory
from ....domain.usage_ratios._model import ELIGIBLE_USAGE_RATIO_CATEGORIES
from ....domain.usage_ratios._service import usage_ratio_bucket_lock
from ....tests.secure_sql import isolated_runtime_profile
from ..ratios import set_usage_ratio

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "19191919-1919-4919-8919-191919191919"
_RATIO = Decimal("0.37")
_JOIN_TIMEOUT_S = 60.0


def _eligible_subset(count: int) -> tuple[SpendingCategory, ...]:
    """Return ``count`` eligible categories in a stable, deterministic order."""
    ordered = sorted(ELIGIBLE_USAGE_RATIO_CATEGORIES, key=lambda c: c.value)
    # The no-skip rule: assert the production catalogue is large enough rather
    # than silently shrinking the contention. If the eligible set ever drops
    # below this floor, this test must be rewritten, not quietly weakened.
    assert len(ordered) >= count, (
        f"ELIGIBLE_USAGE_RATIO_CATEGORIES has {len(ordered)} entries; this "
        f"concurrency regression needs at least {count} distinct categories."
    )
    return tuple(ordered[:count])


def test_concurrent_distinct_category_sets_do_not_lose_updates(tmp_path: Path) -> None:
    """N threads each set a DIFFERENT category on one bucket; every override survives."""
    categories = _eligible_subset(8)
    errors: list[str] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        bucket_id = profile.bucket_id
        # Release every writer simultaneously to maximise the read-modify-write
        # overlap that the lock must serialise.
        gate = threading.Barrier(len(categories))

        def writer(category: SpendingCategory) -> None:
            try:
                gate.wait()
                set_usage_ratio(bucket_id=bucket_id, category=category, ratio=_RATIO)
            except Exception as exc:  # surface any worker failure to the assertion
                errors.append(f"{category.value}: {type(exc).__name__}: {exc}")

        threads: list[threading.Thread] = []
        for category in categories:
            # Each worker runs in its own copied context so the settings
            # override and the active bucket-session contextvar (neither of
            # which a bare thread inherits) propagate into the worker.
            ctx = contextvars.copy_context()
            threads.append(threading.Thread(target=ctx.run, args=(writer, category)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=_JOIN_TIMEOUT_S)

        assert not [t for t in threads if t.is_alive()], "a writer deadlocked under contention"
        assert errors == [], f"concurrent writers raised: {errors}"

        final = load_usage_ratios(bucket_id=bucket_id)
        survived = set(final.ratios)
        expected = set(categories)
        lost = sorted(c.value for c in (expected - survived))
        assert survived == expected, f"lost-update detected; dropped categories: {lost}"
        for category in categories:
            assert final.ratios[category] == _RATIO


def test_usage_ratio_bucket_lock_is_a_real_mutex(tmp_path: Path) -> None:
    """A second acquisition of the per-bucket lock is refused while the first is held.

    Guards against the lock silently degrading to a no-op: if the context
    manager stopped acquiring a real OS lock, the nested acquire would succeed
    and this test would fail.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        bucket_id = profile.bucket_id
        # Tiny wait-budget so the contended re-acquire fails fast instead of
        # blocking for the default timeout (the setting must be strictly > 0).
        with override_settings(cadrumo_file_lock_timeout_s=0.05, cadrumo_file_lock_retry_backoff_s=0.01):  # noqa: SIM117 - pytest.raises must scope only the contended re-acquire
            with usage_ratio_bucket_lock(bucket_id):
                with pytest.raises(LockAcquisitionError):
                    with usage_ratio_bucket_lock(bucket_id):
                        pass

"""``exclusive_file_lock`` refuses an invalid retry backoff instead of crashing.

The typed :class:`~core.config.Settings` field that supplies the default binds
``gt=0``, but a caller-supplied ``retry_backoff`` bypassed settings entirely
and reached :func:`time.sleep`, which raises a bare
``ValueError: sleep length must be non-negative``. That crash surfaced only
under contention — an uncontended acquire never slept — so the primitive's
documented :class:`~core.errors.LockAcquisitionError` contract silently did
not hold for the one path that exercises the parameter.

Each refusal is paired with the valid value it accepts, so a guard that
started refusing everything is distinguishable from one refusing the right
thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..locks import exclusive_file_lock
from ..locks_errors import LockAcquisitionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("backoff", [-1, -0.001, 0, 0.0])
def test_non_positive_backoff_is_refused(tmp_path: Path, backoff: float) -> None:
    """The primitive carries the same bound as the settings field behind it."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    with (
        pytest.raises(LockAcquisitionError, match="retry_backoff"),
        exclusive_file_lock(target, timeout=0.1, retry_backoff=backoff),
    ):
        pytest.fail("an invalid retry backoff must not acquire the lock")


def test_negative_backoff_under_contention_raises_the_documented_error(tmp_path: Path) -> None:
    """The contended path is where the raw ``ValueError`` used to escape.

    Holding the lock forces the retry loop that reaches ``time.sleep``, so
    this is the case the settings-versus-primitive split actually broke.
    """
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    with (
        exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01),
        pytest.raises(LockAcquisitionError, match="retry_backoff"),
        exclusive_file_lock(target, timeout=0.1, retry_backoff=-1),
    ):
        pytest.fail("a contended acquire with an invalid backoff must refuse")


def test_valid_backoff_still_acquires(tmp_path: Path) -> None:
    """The guard must not refuse a legitimate acquisition."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    with exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01) as lock_path:
        assert lock_path.exists()


def test_valid_backoff_still_times_out_with_the_lock_error(tmp_path: Path) -> None:
    """A genuine contention timeout keeps its own message, not the backoff one."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    with (
        exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01),
        pytest.raises(LockAcquisitionError, match="within"),
        exclusive_file_lock(target, timeout=0.05, retry_backoff=0.01),
    ):
        pytest.fail("the second acquire cannot succeed while the first holds")


def test_default_backoff_remains_usable(tmp_path: Path) -> None:
    """Omitting the parameter resolves the settings default, which is positive."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    with exclusive_file_lock(target, timeout=1.0) as lock_path:
        assert lock_path.exists()

"""A secondary cleanup failure is retained on its primary error without replacing it."""

from __future__ import annotations

import pytest

from ..async_cleanup import (
    AsyncResourceCleanupError,
    async_cleanup_failures,
    attach_async_cleanup_error,
    direct_cleanup_owners,
    merged_cleanup_owner,
    retain_merged_cleanup,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Owner:
    async def close(self) -> None:
        raise RuntimeError("synthetic close failure")


def _cleanup(owner: _Owner, label: str) -> AsyncResourceCleanupError:
    return AsyncResourceCleanupError(
        (owner,), (RuntimeError(label),), retry_task_name=f"{label}-retry", close_attempts=1
    )


def test_first_failure_is_attached_with_its_note() -> None:
    primary = ValueError("primary")
    owner = _Owner()
    cleanup = _cleanup(owner, "first")

    retained = attach_async_cleanup_error(primary, cleanup, note="cleanup also failed")

    assert retained is cleanup
    assert primary.__dict__["async_cleanup_error"] is cleanup
    assert primary.__notes__ == ["cleanup also failed"]
    assert async_cleanup_failures(primary) == (cleanup,)


def test_later_failure_merges_after_the_earlier_retry_owner() -> None:
    primary = ValueError("primary")
    earlier_owner, later_owner = _Owner(), _Owner()
    earlier = _cleanup(earlier_owner, "earlier")
    later = _cleanup(later_owner, "later")

    attach_async_cleanup_error(primary, earlier)
    retained = attach_async_cleanup_error(primary, later)

    assert primary.__dict__["async_cleanup_error"] is retained
    assert retained.resources == (earlier_owner, later_owner)
    assert [str(failure) for failure in retained._failures] == ["earlier", "later"]
    assert not hasattr(primary, "__notes__")


def test_reattaching_the_retained_failure_does_not_duplicate_it() -> None:
    primary = ValueError("primary")
    cleanup = _cleanup(_Owner(), "only")

    attach_async_cleanup_error(primary, cleanup)
    retained = attach_async_cleanup_error(primary, cleanup)

    assert retained is cleanup
    assert len(retained._failures) == 1


def test_direct_owners_are_distinct_and_ordered_without_following_causes() -> None:
    cleanup = _cleanup(_Owner(), "shared")
    other = _cleanup(_Owner(), "other")
    primary = ValueError("primary")
    primary.__dict__["async_cleanup_error"] = cleanup
    primary.__dict__["cleanup_error"] = cleanup
    primary.__cause__ = RuntimeError("cause")
    primary.__cause__.__dict__["async_cleanup_error"] = other

    assert direct_cleanup_owners(primary) == (cleanup,)
    assert direct_cleanup_owners(cleanup) == (cleanup,)
    assert direct_cleanup_owners(ValueError("bare")) == ()


def test_merged_owner_combines_every_error_once_and_skips_absent_ones() -> None:
    first_owner, second_owner = _Owner(), _Owner()
    first = _cleanup(first_owner, "first")
    second = _cleanup(second_owner, "second")
    earlier = ValueError("earlier")
    earlier.__dict__["async_cleanup_error"] = first
    later = ValueError("later")
    later.__dict__["cleanup_error"] = second
    later.__dict__["async_cleanup_error"] = first

    merged = merged_cleanup_owner(None, earlier, later)

    assert merged is not None
    assert merged.resources == (first_owner, second_owner)
    assert [str(failure) for failure in merged._failures] == ["first", "second"]
    assert merged_cleanup_owner(None, ValueError("bare")) is None


def test_retained_merge_updates_both_attachment_fields_only_where_present() -> None:
    first = _cleanup(_Owner(), "first")
    second = _cleanup(_Owner(), "second")
    earlier = ValueError("earlier")
    earlier.__dict__["async_cleanup_error"] = first
    primary = ValueError("primary")
    primary.__dict__["cleanup_error"] = second

    retained = retain_merged_cleanup(primary, earlier)

    assert retained is not None
    assert primary.__dict__["async_cleanup_error"] is retained
    assert primary.__dict__["cleanup_error"] is retained
    assert retained.resources == first.resources + second.resources

    absent = ValueError("absent")
    absent_retained = retain_merged_cleanup(absent, earlier)
    assert absent.__dict__["async_cleanup_error"] is absent_retained is first
    assert "cleanup_error" not in absent.__dict__


def test_a_primary_that_is_the_only_owner_is_left_unchanged() -> None:
    owner = _cleanup(_Owner(), "only")

    assert retain_merged_cleanup(owner) is owner
    assert "async_cleanup_error" not in owner.__dict__
    assert retain_merged_cleanup(ValueError("bare")) is None

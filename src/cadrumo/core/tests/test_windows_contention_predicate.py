"""Only Windows contention is classified as contention.

The predicate decides whether a refusal is a peer's open handle -- worth
waiting out -- or a genuine denial that must propagate. Both consumers wait on
a ``True`` answer, so a predicate that answered ``True`` too readily would turn
a permanent refusal into a stall and then a late, confusing failure.

The codes are asserted by value rather than by re-deriving them from the module
under test: the numbers are Windows' contract, not this project's, and a test
that read them from the same frozenset it checks would pass whatever they were
changed to.
"""

from __future__ import annotations

import pytest

from ..windows_contention import WINDOWS_CONTENDED_ACCESS_ERRORS, is_windows_contention

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("winerror", [5, 32])
def test_a_peers_open_handle_is_contention(winerror: int) -> None:
    """ERROR_ACCESS_DENIED and ERROR_SHARING_VIOLATION are what a handle causes."""
    assert is_windows_contention(PermissionError(13, "refused", None, winerror)) is True


def test_a_posix_refusal_is_never_contention() -> None:
    """DISCRIMINATING: the direction that must not stall.

    POSIX carries no ``winerror`` and has no sharing-violation class, so an
    ``EACCES`` there is a genuine denial. Classifying it as contention would
    make every consumer wait out its whole budget before failing.
    """
    assert is_windows_contention(PermissionError(13, "permission denied")) is False


def test_an_unrelated_windows_error_is_not_contention() -> None:
    """A Windows error outside the pair stays genuine.

    Guards the frozenset against being widened into "any Windows refusal",
    which would absorb a read-only attribute or a denying ACL.
    """
    assert is_windows_contention(PermissionError(13, "refused", None, 1)) is False
    assert is_windows_contention(OSError(2, "missing")) is False


def test_the_codes_are_exactly_the_two_a_handle_produces() -> None:
    """ANTI-TAUTOLOGY: pin the membership, not just the predicate.

    Every assertion above would still pass if the set gained a third code, so
    the set itself is pinned to the pair Windows raises for a blocked handle.
    """
    assert frozenset({5, 32}) == WINDOWS_CONTENDED_ACCESS_ERRORS

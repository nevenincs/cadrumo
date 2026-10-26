"""Test-only authority capability for operation graphs that never read it."""

from __future__ import annotations

from ....domain.calculations.registry.authority import PinnedAuthorityOperation


def unread_authority_operation() -> PinnedAuthorityOperation:
    """Return an inert typed pin for tests whose executors never consult authority."""
    return PinnedAuthorityOperation.__new__(PinnedAuthorityOperation)


__all__ = ["unread_authority_operation"]

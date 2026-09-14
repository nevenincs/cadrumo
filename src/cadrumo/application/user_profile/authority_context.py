"""Profile-schema context adapters for authority-pinned application flows."""

from __future__ import annotations

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.authority_artifact import (
    ProfileCreateContext,
    ProfileDecodeContext,
)


def profile_create_context(operation: PinnedAuthorityOperation) -> ProfileCreateContext:
    """Return a creation context from a caller-held authority operation."""
    if not isinstance(operation, PinnedAuthorityOperation):
        raise TypeError("profile create context requires a PinnedAuthorityOperation")
    return operation.profile_create_context()


def profile_decode_context(operation: PinnedAuthorityOperation) -> ProfileDecodeContext:
    """Return a decode context from a caller-held authority operation."""
    if not isinstance(operation, PinnedAuthorityOperation):
        raise TypeError("profile decode context requires a PinnedAuthorityOperation")
    return operation.profile_decode_context()


__all__ = ["profile_create_context", "profile_decode_context"]

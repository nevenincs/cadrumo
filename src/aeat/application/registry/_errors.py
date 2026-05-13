"""Application-level registry workflow errors."""

from __future__ import annotations

from ...core.errors import AeatError


class RegistryApplicationError(AeatError):
    """Raised when registry application orchestration refuses or fails."""


class RegistryApplicationInputError(RegistryApplicationError):
    """Raised when registry application input cannot be executed."""


__all__ = ["RegistryApplicationError", "RegistryApplicationInputError"]

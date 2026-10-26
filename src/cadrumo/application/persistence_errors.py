"""Application-facing persistence failure contracts."""

from __future__ import annotations

from ..core.errors.hierarchy import CadrumoError


class PersistenceDegradationError(CadrumoError):
    """A persistence capability could not provide a requested operation."""

    def __init__(self, operation: str) -> None:
        """Carry the stable application operation, without adapter details."""
        self.operation = operation
        super().__init__(f"persistence operation failed: {operation}")


__all__ = ["PersistenceDegradationError"]

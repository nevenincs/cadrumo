"""Application-facing persistence failure contracts."""

from __future__ import annotations


class PersistenceDegradationError(RuntimeError):
    """A persistence capability could not provide a requested operation."""

    def __init__(self, operation: str) -> None:
        """Carry the stable application operation, without adapter details."""
        self.operation = operation
        super().__init__(f"persistence operation failed: {operation}")


__all__ = ["PersistenceDegradationError"]

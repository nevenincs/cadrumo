"""Result of bounded shutdown of one canonical operation owner."""

from __future__ import annotations

from dataclasses import dataclass

from .models import OperationId


@dataclass(frozen=True, slots=True)
class OperationDrainResult:
    """Local work still running and durable invocations requiring recovery.

    A returned deadline is never proof that an executor or descendant stopped.
    The caller must contain the owner process while ``needs_containment`` is
    true, then reconcile ``recovery_required`` through the canonical journal.
    """

    unresolved: tuple[OperationId, ...]
    recovery_required: tuple[OperationId, ...]

    @property
    def needs_containment(self) -> bool:
        """Whether a local task may still execute after this call returns."""
        return bool(self.unresolved)


__all__ = ["OperationDrainResult"]

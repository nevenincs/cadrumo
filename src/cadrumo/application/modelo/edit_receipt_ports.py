"""Application-owned capability for co-committing Modelo edit receipts.

The edit executor creates the receipt DTO and asks this narrow capability for
the secure-object write that accompanies the calculation revision.  The
encrypted repository and its storage failures remain in the outer adapter;
only this application DTO, the core write value, and the translated failure
cross the boundary.
"""

from __future__ import annotations

from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.secure_object_write import SecureObjectWrite
from .edit_contract import ModeloEditMutationResultReceiptV1


class ModeloEditReceiptPersistenceError(CadrumoError):
    """Translated failure from the edit-receipt persistence capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the stable application operation, never storage details."""
        self.operation = operation
        super().__init__(f"modelo edit receipt persistence operation failed: {operation}")


class ModeloEditReceiptRepositoryPort(Protocol):
    """Required co-commit preparation capability for one Modelo edit."""

    def to_secure_object_write(self, receipt: ModeloEditMutationResultReceiptV1) -> SecureObjectWrite:
        """Prepare the receipt write without committing it."""
        ...


class ModeloEditReceiptRepositoryFactory(Protocol):
    """Construct the receipt capability for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ModeloEditReceiptRepositoryPort:
        """Return the capability bound to ``bucket_id``."""
        ...


__all__ = [
    "ModeloEditReceiptPersistenceError",
    "ModeloEditReceiptRepositoryFactory",
    "ModeloEditReceiptRepositoryPort",
]

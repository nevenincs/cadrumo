"""Storage provider abstraction — public surface.

Exports the `StorageProvider` Protocol, the four pydantic records that
cross the provider boundary, the `ProviderKind` enum, and the typed
`StorageError` hierarchy. Concrete backends (`_local.py`,
`_google_drive.py`, `_testing.py`) and the `_factory.py` are not
re-exported; consumers depend on the Protocol surface and the records.
"""

from __future__ import annotations

from ._errors import (
    StorageConflictError,
    StorageError,
    StorageIntegrityError,
    StorageNetworkError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageQuotaError,
    StorageUnavailableError,
    StorageValidationError,
)
from ._protocol import StorageProvider
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

__all__ = [
    "ProviderKind",
    "ProviderObjectMetadata",
    "ProviderProbeReport",
    "StorageConflictError",
    "StorageError",
    "StorageIntegrityError",
    "StorageNetworkError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "StorageProvider",
    "StorageQuotaError",
    "StorageUnavailableError",
    "StorageValidationError",
]

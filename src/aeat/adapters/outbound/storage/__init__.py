"""Storage provider abstraction — public surface.

Exports the `StorageProvider` Protocol, the four pydantic records that
cross the provider boundary, the `ProviderKind` enum, and the typed
`OutboundStorageError` hierarchy. Concrete backends (`_local.py`,
`_google_drive.py`, `_testing.py`) and the `_factory.py` are not
re-exported; consumers depend on the Protocol surface and the records.
"""

from __future__ import annotations

from ._errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
)
from ._factory import get_storage_provider
from ._protocol import StorageProvider
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

__all__ = [
    "OutboundStorageConflictError",
    "OutboundStorageError",
    "OutboundStorageIntegrityError",
    "OutboundStorageNetworkError",
    "OutboundStorageNotFoundError",
    "OutboundStoragePermissionError",
    "OutboundStorageQuotaError",
    "OutboundStorageUnavailableError",
    "OutboundStorageValidationError",
    "ProviderKind",
    "ProviderObjectMetadata",
    "ProviderProbeReport",
    "StorageProvider",
    "get_storage_provider",
]

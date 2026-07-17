"""Narrow exceptions for the bucket-event-history domain.

:class:`BucketEventValidationError` protects :class:`BucketEvent` and
:class:`BucketEventHistoryCatalogue` invariants, while the maintenance errors
cover operator-facing bucket browse, export, import, rename, and delete flows.
"""

from __future__ import annotations

from ...core.errors import CadrumoError


class BucketsError(CadrumoError):
    """Base error for the bucket-event-history domain."""


class BucketEventValidationError(BucketsError, ValueError):
    """Raised when a bucket event fails validation."""


class BucketMaintenanceError(BucketsError):
    """Base error for operator-driven bucket-maintenance operations."""


class BucketBrowseError(BucketMaintenanceError):
    """Raised when a bucket browse / search request cannot be served."""


class BucketExportError(BucketMaintenanceError):
    """Raised when a bucket archive export fails."""


class BucketImportError(BucketMaintenanceError):
    """Raised when a bucket archive import fails (bad payload or collision)."""


class BucketRenameError(BucketMaintenanceError):
    """Raised when a bucket rename violates uniqueness or addressing rules."""


class BucketDeleteRefusedError(BucketMaintenanceError):
    """Raised when a bucket delete is refused by a destructive-action gate."""


class BucketArchiveRefusedError(BucketMaintenanceError):
    """Raised when a bucket archive (soft, reversible dormancy) is refused."""


class BucketRestoreRefusedError(BucketMaintenanceError):
    """Raised when restoring an archived bucket is refused (e.g. not archived)."""

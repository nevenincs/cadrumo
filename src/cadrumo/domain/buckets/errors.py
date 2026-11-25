"""Canonical narrow exceptions for the bucket-event-history domain.

:class:`BucketEventValidationError` protects :class:`BucketEvent` and
:class:`BucketEventHistoryCatalogue` invariants, while the maintenance errors
cover operator-facing bucket browse, export, import, rename, and delete flows.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin

# The application owns the concrete ``PreconditionVerdict`` record.  Core's
# mixin deliberately carries that value opaquely so this domain taxonomy does
# not need a type-only dependency on the application boundary.
_BucketDeletePreconditionErrorMixin = TerminalPreconditionErrorMixin[object]


class BucketsError(CadrumoError):
    """Base error for the bucket-event-history domain."""


class BucketEventValidationError(BucketsError):
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


class BucketDeleteRefusedError(_BucketDeletePreconditionErrorMixin, BucketMaintenanceError):
    """Raised when a destructive-action gate refuses a bucket deletion.

    The bucket-maintenance application boundary may attach a typed terminal
    precondition verdict when it observes a safety condition with no safe
    recovery command. The core-owned mixin carries that opaque application
    record without making this domain taxonomy depend on application models.
    """


class BucketArchiveRefusedError(BucketMaintenanceError):
    """The refusal reserved for a bucket archive (soft, reversible dormancy).

    Nothing raises it.
    """


class BucketRestoreRefusedError(BucketMaintenanceError):
    """The refusal reserved for restoring an archived bucket (e.g. not archived).

    Nothing raises it.
    """

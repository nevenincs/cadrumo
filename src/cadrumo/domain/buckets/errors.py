"""Canonical narrow exceptions for the bucket-event-history domain.

:class:`BucketEventValidationError` protects :class:`BucketEvent` and
:class:`BucketEventHistoryCatalogue` invariants, while the maintenance errors
cover operator-facing bucket browse, export, import, rename, and delete flows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin

if TYPE_CHECKING:
    from ...application.operator_actions._models import PreconditionVerdict

    _BucketDeletePreconditionErrorMixin = TerminalPreconditionErrorMixin[PreconditionVerdict]
else:
    _BucketDeletePreconditionErrorMixin = TerminalPreconditionErrorMixin


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


class BucketDeleteRefusedError(_BucketDeletePreconditionErrorMixin, BucketMaintenanceError):
    """Raised when a destructive-action gate refuses a bucket deletion.

    The bucket-maintenance application boundary may attach a typed terminal
    precondition verdict when it observes a safety condition with no safe
    recovery command. The core-owned mixin carries that opaque application
    record without making this domain taxonomy depend on application models.
    """


class BucketArchiveRefusedError(BucketMaintenanceError):
    """The refusal reserved for a bucket archive (soft, reversible dormancy).

    Nothing raises it: the archive service method was deleted when the custody
    capsule became the sole profile authority, and this is the typed refusal
    its verb took rather than a guard on a live path.

    Kept deliberately. The verb's restore-or-retire decision is open, and the
    orphaned typed contracts around it -- this refusal among them -- are the
    cheapest specification available to whoever makes it. Deleting them would
    discard part of the answer before the question is settled.
    """


class BucketRestoreRefusedError(BucketMaintenanceError):
    """The refusal reserved for restoring an archived bucket (e.g. not archived).

    Nothing raises it, for the same reason and by the same change as
    :class:`BucketArchiveRefusedError`: the restore service method was deleted
    with the archive one, and both refusals were kept as contract rather than
    retired with their verbs.
    """

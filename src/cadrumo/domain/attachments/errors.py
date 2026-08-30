"""Domain exceptions for :mod:`domain.attachments`.

Every error raised inside the attachment subpackage inherits from
:exc:`AttachmentError`, which itself derives from
:exc:`core.errors.CadrumoError`. Callers can therefore catch the family
root for coarse handling or branch on the specific subclasses.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class AttachmentError(CadrumoError):
    """Base error for every attachment-service failure.

    All other exceptions in :mod:`domain.attachments` derive from this
    class so callers can install a single catch.
    """


class AttachmentValidationError(AttachmentError, ValueError):
    """Raised when an attachment payload fails domain validation.

    Used both by pydantic-driven validation on :class:`domain.attachments.Attachment`
    and by :class:`adapters.persistence.storage.AttachmentStore` when an untrusted
    digest token does not match the expected 64-character lowercase hex shape.
    """


class AttachmentPersistenceError(AttachmentError):
    """Raised when the attachment store cannot read or write bytes or manifests.

    Wraps the underlying :exc:`OSError` so callers do not have to reason about
    raw filesystem failures.
    """


class AttachmentNotFoundError(AttachmentError):
    """Raised when a manifest or blob lookup targets a missing attachment.

    Distinct from :exc:`AttachmentPersistenceError` so callers can treat a
    missing record differently from a filesystem failure.
    """

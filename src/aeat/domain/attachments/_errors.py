"""Domain exceptions for ``aeat.domain.attachments``."""

from __future__ import annotations

from ...core.errors import AeatError


class AttachmentError(AeatError):
    """Base error for every attachment-service failure."""


class AttachmentValidationError(AttachmentError):
    """Raised when an attachment payload fails domain validation."""


class AttachmentPersistenceError(AttachmentError):
    """Raised when the attachment store cannot read or write bytes or manifests."""


class AttachmentNotFoundError(AttachmentError):
    """Raised when a manifest or blob lookup targets a missing attachment."""

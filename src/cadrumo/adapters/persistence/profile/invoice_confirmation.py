"""Persistence adapter for the invoice-confirmation capability.

The application confirmation flow consumes the public attachment-store
protocol.  This module binds that protocol to the encrypted attachment store
for one bucket and translates storage failures into the application-owned
confirmation error before they cross the boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar, override

from ....application.ledger.invoice_confirmation_ports import (
    InvoiceConfirmationPersistenceError,
    InvoiceConfirmationPorts,
)
from ....core.identity.bucket import canonical_bucket_id
from ....domain.attachments.errors import (
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ....domain.attachments.models import Attachment
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ..storage.attachment import AttachmentStore
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket

T = TypeVar("T")


def _translate_attachment_failure(operation: str, action: Callable[[], T]) -> T:
    """Expose only domain misses/validation and the app persistence contract."""
    try:
        return action()
    except (AttachmentNotFoundError, AttachmentValidationError, InvoiceConfirmationPersistenceError):
        raise
    except (AttachmentPersistenceError, StorageError, OSError, TypeError, ValueError, KeyError) as exc:
        raise InvoiceConfirmationPersistenceError(operation) from exc


class InvoiceConfirmationAttachmentStoreAdapter(AttachmentStoreProtocol):
    """Translate the encrypted attachment store to the confirmation port."""

    def __init__(self, *, store: AttachmentStore) -> None:
        self._store = store

    @override
    def put_bytes(self, data: bytes) -> str:
        """Store bytes while translating persistence failures."""
        return _translate_attachment_failure("attachment_put_bytes", lambda: self._store.put_bytes(data))

    @override
    def put_file(self, source: Path) -> tuple[str, int]:
        """Store a file while translating persistence failures."""
        return _translate_attachment_failure("attachment_put_file", lambda: self._store.put_file(source))

    @override
    def read_bytes(self, sha256: str) -> bytes:
        """Read bytes while translating persistence failures."""
        return _translate_attachment_failure("attachment_read_bytes", lambda: self._store.read_bytes(sha256))

    @override
    def write_manifest(self, attachment: Attachment) -> None:
        """Write a manifest while translating persistence failures."""
        _translate_attachment_failure("attachment_write_manifest", lambda: self._store.write_manifest(attachment))

    @override
    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load a manifest while preserving an ordinary domain miss."""
        return _translate_attachment_failure(
            "attachment_load_manifest", lambda: self._store.load_manifest(attachment_id)
        )

    @override
    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate manifests while translating failures raised during iteration."""
        try:
            yield from self._store.iter_manifests()
        except (AttachmentNotFoundError, AttachmentValidationError, InvoiceConfirmationPersistenceError):
            raise
        except (AttachmentPersistenceError, StorageError, OSError, TypeError, ValueError, KeyError) as exc:
            raise InvoiceConfirmationPersistenceError("attachment_iter_manifests") from exc

    @override
    def verify_blob(self, attachment_id: str) -> None:
        """Verify one blob while translating persistence failures."""
        _translate_attachment_failure("attachment_verify_blob", lambda: self._store.verify_blob(attachment_id))


def build_invoice_confirmation_ports(*, bucket_id: str) -> InvoiceConfirmationPorts:
    """Bind encrypted attachment custody to one profile bucket."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    return InvoiceConfirmationPorts(
        attachment_store=InvoiceConfirmationAttachmentStoreAdapter(
            store=AttachmentStore(
                bucket_id=normalized_bucket_id,
                objects=secure_object_repository_for_bucket(normalized_bucket_id),
            ),
        ),
    )


__all__ = [
    "InvoiceConfirmationAttachmentStoreAdapter",
    "build_invoice_confirmation_ports",
]

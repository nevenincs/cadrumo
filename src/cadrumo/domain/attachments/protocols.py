"""Protocol declaration for the attachment store boundary.

Domain-layer protocol that the adapter-layer concrete implementation
must satisfy. The concrete implementation is exported as
:class:`adapters.persistence.storage.AttachmentStore`; this module keeps
the domain free of adapter imports.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import Attachment


@runtime_checkable
class AttachmentStoreProtocol(Protocol):
    """Structural protocol for an attachment storage backend.

    The domain service layer (``_service.py``) accepts any object that
    satisfies this protocol. The concrete SQL-backed implementation is
    :class:`adapters.persistence.storage.AttachmentStore`.
    """

    def put_bytes(self, data: bytes) -> str:
        """Write ``data`` under its SHA-256 digest and return the digest."""
        ...

    def put_file(self, source: Path) -> tuple[str, int]:
        """Read ``source`` into the store and return ``(sha256, bytes_size)``."""
        ...

    def read_bytes(self, sha256: str) -> bytes:
        """Return the raw bytes for ``sha256``."""
        ...

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` as a manifest record."""
        ...

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the manifest for ``attachment_id``.

        Returns:
            The validated :class:`Attachment` manifest record.
        """
        ...

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every :class:`Attachment` manifest in sorted attachment-id order."""
        ...

    def verify_blob(self, attachment_id: str) -> None:
        """Re-hash the stored blob and verify it matches ``attachment_id``."""
        ...


__all__ = ["AttachmentStoreProtocol"]

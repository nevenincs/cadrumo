"""The file name a held purchase document arrived under, from its encrypted attachment manifest."""

from __future__ import annotations

from ....domain.attachments.enums import AttachmentSource
from ....domain.attachments.errors import AttachmentNotFoundError
from ..storage.attachment import AttachmentStore
from ..storage.sql.secure_objects import SecureObjectRepository


def attachment_source_file_name(objects: SecureObjectRepository, content_digest: str) -> str | None:
    """Answer the name alone, never the path around it; a document not held from a local file has none.

    Args:
        objects: :class:`SecureObjectRepository` holding the attachment manifest.
        content_digest: Digest identifying the attachment.
    """
    try:
        manifest = AttachmentStore(objects=objects).load_manifest(content_digest)
    except AttachmentNotFoundError:
        return None
    if manifest.source is not AttachmentSource.LOCAL_FILE:
        return None
    # The path was written on whichever system captured it, so both separators count.
    return manifest.source_reference.replace("\\", "/").rsplit("/", 1)[-1] or None


__all__ = ["attachment_source_file_name"]

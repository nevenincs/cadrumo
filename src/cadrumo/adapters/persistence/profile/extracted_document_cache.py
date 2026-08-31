"""Encrypted persistence adapter for transcription-cache documents."""

from __future__ import annotations

from typing import override

from ....application.ledger.extracted_document_cache import (
    ExtractedDocumentCacheDocument,
    extracted_document_cache_object_key,
)
from ....core.config import Settings
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE


class ExtractedDocumentCacheRepository(SecureBoundRepository[ExtractedDocumentCacheDocument]):
    """Store one bucket's transcription cache through encrypted secure objects."""

    namespace = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.namespace
    sensitivity = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.sensitivity
    schema_version = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.schema_version
    payload_type = ExtractedDocumentCacheDocument

    def __init__(self, *, bucket_id: str, settings: Settings) -> None:
        """Bind the repository to ``bucket_id`` through the storage runtime."""
        super().__init__(objects=secure_object_repository_for_bucket(bucket_id, settings))

    @override
    def extract_identifier(self, payload: ExtractedDocumentCacheDocument) -> str:
        """Return the cache document's bucket-scoped natural key."""
        return extracted_document_cache_object_key(payload)


__all__ = ["ExtractedDocumentCacheRepository"]

"""Encrypted persistence adapter for pending ledger extraction drafts."""

from __future__ import annotations

from typing import override

from ....application.ledger.extraction_draft_store import (
    ExtractionDraftDocument,
    extraction_draft_object_key,
)
from ....core.config import Settings
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import LEDGER_EXTRACTION_DRAFT_NAMESPACE


class ExtractionDraftRepository(SecureBoundRepository[ExtractionDraftDocument]):
    """Store one bucket's pending drafts through encrypted secure objects."""

    namespace = LEDGER_EXTRACTION_DRAFT_NAMESPACE.namespace
    sensitivity = LEDGER_EXTRACTION_DRAFT_NAMESPACE.sensitivity
    schema_version = LEDGER_EXTRACTION_DRAFT_NAMESPACE.schema_version
    payload_type = ExtractionDraftDocument

    def __init__(self, *, bucket_id: str, settings: Settings) -> None:
        """Bind the repository to ``bucket_id`` through the storage runtime."""
        super().__init__(objects=secure_object_repository_for_bucket(bucket_id, settings))

    @override
    def extract_identifier(self, payload: ExtractionDraftDocument) -> str:
        """Return the application-owned natural key for ``payload``."""
        return extraction_draft_object_key(payload)


__all__ = ["ExtractionDraftRepository"]

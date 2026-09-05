"""The canonical secure repository for notification documents in custody.

One definition, because two entrypoints need it. The CLI composes it to fetch
and store documents behind a notificación; the TUI reads it to count what is
already in custody, which is how AEAT Sync tells "nothing has been pulled"
apart from "nothing is there". Building it a second time in the TUI would put
the namespace, object key and two error factories in two places, and a
divergence between them would be a read pointed at a store nothing writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.live.errors import LiveApplicationInputError
from ....application.live.notification_documents import (
    NotificationDocumentNotFoundError,
    NotificationDocumentRecord,
    notification_document_object_key,
)
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import LIVE_NOTIFICATION_DOCUMENT_NAMESPACE
from .snapshots import SecureSnapshotRepository

if TYPE_CHECKING:
    from ....core.config import Settings


def notification_document_repository(
    bucket_id: str,
    settings: Settings,
) -> SecureSnapshotRepository[NotificationDocumentRecord]:
    """Return the secure repository holding one bucket's notification documents."""
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=NotificationDocumentRecord,
        namespace_definition=LIVE_NOTIFICATION_DOCUMENT_NAMESPACE,
        object_key=notification_document_object_key,
        not_found_factory=lambda certificado_id: NotificationDocumentNotFoundError(
            translated_message="application.live.notifications.errors.document_not_found",
            context={"certificado_id": certificado_id},
        ),
        ambiguous_prefix_factory=lambda certificado_id, full_ids: NotificationDocumentNotFoundError(
            translated_message="application.live.notifications.errors.document_prefix_ambiguous",
            context={"certificado_id": certificado_id, "match_count": len(full_ids)},
        ),
        domain_label="notification-document",
        input_error_cls=LiveApplicationInputError,
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


__all__ = ["notification_document_repository"]

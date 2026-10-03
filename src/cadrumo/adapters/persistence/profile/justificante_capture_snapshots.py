"""The canonical secure repository for persisted justificante capture snapshots.

The live justificante commands write captures through it and the overview
calendar reads them back as filing evidence. One definition keeps the
namespace, object key and both lookup-refusal factories identical for the
writer and the reader.
"""

from __future__ import annotations

from ....application.live.errors import LiveApplicationInputError
from ....application.live.justificante import (
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotNotFoundError,
    justificante_capture_snapshot_object_key,
)
from ..storage.secure_object_namespaces import LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from .snapshots import SecureSnapshotRepository


def justificante_capture_snapshot_repository(
    bucket_id: str,
    *,
    objects: SecureObjectRepository,
) -> SecureSnapshotRepository[JustificanteCaptureSnapshot]:
    """Return the secure repository holding one bucket's justificante captures."""
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=JustificanteCaptureSnapshot,
        namespace_definition=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
        object_key=justificante_capture_snapshot_object_key,
        not_found_factory=lambda snapshot_id: JustificanteCaptureSnapshotNotFoundError(
            translated_message="application.live.justificante.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: JustificanteCaptureSnapshotNotFoundError(
            translated_message="application.live.justificante.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="justificante capture",
        input_error_cls=LiveApplicationInputError,
        objects=objects,
    )


__all__ = ["justificante_capture_snapshot_repository"]

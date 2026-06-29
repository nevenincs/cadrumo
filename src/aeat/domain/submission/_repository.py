"""Governed-persistence repository for submission audit records.

Submission audit records keep the local or imported
:class:`aeat.domain.submission.ModeloPresentado` lifecycle: draft id, modelo,
period, taxpayer identity, AEAT receipt metadata when observed, and attempt
summaries. They are stored as encrypted byte objects in the primary SQL backend
at :class:`SensitivityClass` AUDIT; no plaintext submission JSON or envelope
file lands on disk.

See Also:
    :class:`aeat.domain.submission.ModeloPresentado`
        Payload model encrypted by this repository.
    :class:`aeat.adapters.persistence.storage.sql.SecureObjectRepository`
        SQL object store underlying the bound repository.
    :mod:`aeat.application.filing._import`
        Offline justificante import path that can create companion submission
        audit records.
    :mod:`aeat.application.live`
        Read-only live-evidence capture surface; it does not create live
        submission attempts.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar, cast, override

from pydantic import ValidationError

from ...adapters.persistence.storage import SecureBoundRepository, SensitivityClass
from ...core.logging import get_logger
from ._models import ModeloPresentado

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass

_log = get_logger(__name__)


class SubmissionRepository(SecureBoundRepository[ModeloPresentado]):
    """Repository over encrypted SQL-backed :class:`ModeloPresentado` audit records."""

    namespace: ClassVar[str] = "aeat.domain.submission.records"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1

    @override
    @classmethod
    def payload_model(cls) -> type[ModeloPresentado]:
        return ModeloPresentado

    @override
    def extract_identifier(self, payload: ModeloPresentado) -> str:
        return payload.submission_id

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository, in lexicographic order."""
        return tuple(sorted(self.iter_ids()))

    def iter_submissions(self) -> Iterator[ModeloPresentado]:
        """Yield every persisted submission, in lexicographic id order.

        Audit-record enumeration is resilient: rows that fail
        classification or schema-version gates are logged and skipped
        rather than aborting the iteration. Diagnostic surfaces depend
        on listing all healthy submissions even when a single row is
        unreadable.

        Returns:
            Iterator over :class:`ModeloPresentado` records.
        """
        from ...adapters.persistence.storage.sql import SecureObjectRecord

        envelope_cls = self._envelope_cls()
        records: list[tuple[str, ModeloPresentado]] = []
        for item in self.secure_object_repository.iter_records_with_failures(
            self.namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            if not isinstance(item, SecureObjectRecord):
                _log.warning(
                    "iter_submissions: skipping unreadable submission row_id=%s reason=%s",
                    getattr(item, "row_id", "unknown"),
                    getattr(item, "reason", "unknown"),
                )
                continue
            try:
                envelope = envelope_cls.model_validate_json(item.payload)
            except ValidationError:
                _log.warning(
                    "iter_submissions: skipping invalid submission payload object_key=%s",
                    item.object_key.hex(),
                    exc_info=True,
                )
                continue
            # CAST-RATIONALE-SUBMISSION-ENVELOPE-CAST: envelope verified via metadata
            payload = cast(ModeloPresentado, envelope.payload)
            records.append((payload.submission_id, payload))
        for _, payload in sorted(records, key=lambda record: record[0]):
            yield payload


__all__ = [
    "SubmissionRepository",
]

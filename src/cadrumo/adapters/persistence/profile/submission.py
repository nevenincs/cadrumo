"""Governed-persistence repository for submission audit records.

Submission audit records keep the local or imported
:class:`domain.submission.ModeloPresentado` lifecycle: draft id, modelo,
period, taxpayer identity, AEAT receipt metadata when observed, and attempt
summaries. They are stored as encrypted byte objects in the primary SQL backend
at ``AUDIT`` :class:`~adapters.persistence.storage.SensitivityClass`; no
plaintext submission JSON or envelope file lands on disk.

This concrete repository is the persistence adapter behind the read-side
:class:`domain.submission.SubmissionRepositoryProtocol`. It lives in the
persistence adapter (not in :mod:`domain.submission`) because its base
:class:`~adapters.persistence.storage.SecureBoundRepository` is
SQL/crypto-coupled; the domain package depends only on the structural port.

See Also:
    :class:`domain.submission.ModeloPresentado`
        Payload model encrypted by this repository.
    :class:`domain.submission.SubmissionRepositoryProtocol`
        Domain-facing read port this repository satisfies structurally.
    :class:`adapters.persistence.storage.SecureObjectRepository`
        SQL object store underlying the bound repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, cast, override

from pydantic import ValidationError

from ....core.logging import get_logger
from ....domain.submission import ModeloPresentado
from ..storage import SUBMISSION_RECORDS_NAMESPACE, SecureBoundRepository, SensitivityClass

_log = get_logger(__name__)


class SubmissionRepository(SecureBoundRepository[ModeloPresentado]):
    """Encrypted AUDIT repository for :class:`ModeloPresentado` records.

    The :class:`~adapters.persistence.storage.SecureBoundRepository` base
    stores each :class:`ModeloPresentado` in a
    :class:`~adapters.persistence.storage.Envelope` row under the AUDIT
    submission-records namespace. The natural key is the submission id, so the
    list and iteration APIs expose historical filing attempts rather than any
    live submission capability.

    See Also:
        :class:`domain.submission.SubmissionRepositoryProtocol`
            Domain read port this class satisfies.
        :class:`~adapters.persistence.storage.SecureObjectRepository`
            SQL object store composed by the bound repository base.
    """

    namespace: ClassVar[str] = SUBMISSION_RECORDS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = SUBMISSION_RECORDS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = SUBMISSION_RECORDS_NAMESPACE.schema_version

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
        from ..storage.sql import SecureObjectRecord

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

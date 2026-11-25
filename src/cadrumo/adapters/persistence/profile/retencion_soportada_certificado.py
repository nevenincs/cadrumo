"""Revision-reading and removal over the encrypted suffered-withholding per-payer records.

Extends the record repository with the two capabilities the operator-facing
certificate operations need beyond the calculation's read: each record beside
the revision it was read at, and a removal that only succeeds against that
revision.
"""

from __future__ import annotations

from typing import override

from ....application.aggregation.retencion_soportada_repository import (
    RetencionSoportadaPersistenceError,
    RetencionSoportadaRevisionConflictError,
    retencion_soportada_record_key,
)
from ....application.retencion_soportada_certificado.ports import RetencionSoportadaCertificadoRepository
from ....domain.renta.retencion_soportada import RetencionSoportadaIdentity, RetencionSoportadaRecord
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.errors import (
    STORED_RECORD_FAILURES,
    SecureObjectRevisionConflictError,
    SecureObjectRowIdentityError,
)
from .retencion_soportada_records import RetencionSoportadaRecordRepositoryAdapter

__all__ = ["RetencionSoportadaCertificadoRepositoryAdapter"]


class RetencionSoportadaCertificadoRepositoryAdapter(
    RetencionSoportadaRecordRepositoryAdapter,
    RetencionSoportadaCertificadoRepository,
):
    """Bind the certificate operations' port to encrypted secure-object storage."""

    @override
    def list_revisioned(self, ejercicio: int) -> tuple[tuple[RetencionSoportadaRecord, str], ...]:
        """Return every payer record of ``ejercicio`` with its revision, ordered by object key."""

        def scan() -> tuple[tuple[RetencionSoportadaRecord, str], ...]:
            rows: list[tuple[str, RetencionSoportadaRecord, str]] = []
            for stored, envelope in self._iter_validated_rows():
                payload = envelope.payload
                identifier = self.extract_identifier(payload)
                if secure_object_key_digest(identifier) != stored.object_key:
                    raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
                if payload.ejercicio == ejercicio:
                    rows.append((identifier, payload, stored.revision_id))
            return tuple((payload, revision_id) for _identifier, payload, revision_id in sorted(rows))

        try:
            return scan()
        except STORED_RECORD_FAILURES as exc:
            raise RetencionSoportadaPersistenceError("retencion_soportada_list_revisioned") from exc

    @override
    def delete_revisioned(self, identity: RetencionSoportadaIdentity, *, expected_revision_id: str) -> None:
        """Remove the row at ``identity`` only if it is still at ``expected_revision_id``."""
        deletion = self.to_secure_object_deletion(retencion_soportada_record_key(identity)).model_copy(
            update={"expected_revision_id": expected_revision_id},
        )
        try:
            self.secure_object_repository.apply_batch((), (deletion,))
        except SecureObjectRevisionConflictError as exc:
            raise RetencionSoportadaRevisionConflictError from exc
        except STORED_RECORD_FAILURES as exc:
            raise RetencionSoportadaPersistenceError("retencion_soportada_delete") from exc

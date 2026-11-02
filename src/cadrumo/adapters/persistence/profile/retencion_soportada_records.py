"""Encrypted persistence adapter for the suffered-withholding per-payer records.

The payer's tax identifier lives only inside the encrypted payload. A record is
stored under ``{ejercicio}:{income_class}:{payer_ref}``, and ``payer_ref`` is an
HMAC-SHA256 of the canonical tax-identity token under a sub-key of the active
profile's data key, derived for this family alone under
:data:`RETENCION_SOPORTADA_PAYER_REF_CONTEXT`. The natural key is digested again
into the ``object_key`` column, as for every namespace.

An unkeyed hash of a tax identifier would not do: the identifier space is small
enough to enumerate, and a natural key can surface in a row-identity error. A
digest under a key only this profile holds cannot be inverted by whoever reads
the key, and two profiles never derive the same reference for one payer.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.domain.renta.retencion_soportada.RetencionSoportadaRecord`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final, override

from ....application.aggregation.retencion_soportada_repository import (
    RetencionSoportadaPersistenceError,
    RetencionSoportadaRecordRepository,
    RetencionSoportadaRevisionConflictError,
    retencion_soportada_record_key,
)
from ....core.classification.policies import SensitivityClass
from ....core.external_constants import UTF_8_ENCODING
from ....core.identity.tax_id import tax_id_identity_token
from ....core.keyed_digest import keyed_digest_hex
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.renta.retencion_soportada import RetencionSoportadaIdentity, RetencionSoportadaRecord
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import STORED_RECORD_FAILURES, SecureObjectRevisionConflictError, SecureObjectRowIdentityError
from ..storage.master_key.active_session import get_active_hmac_subkey
from ..storage.secure_object_namespaces import RETENCION_SOPORTADA_RECORDS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

__all__ = [
    "RETENCION_SOPORTADA_PAYER_REF_CONTEXT",
    "RetencionSoportadaRecordRepositoryAdapter",
    "retencion_soportada_payer_reference",
]

RETENCION_SOPORTADA_PAYER_REF_CONTEXT: Final[bytes] = b"cadrumo.renta.retencion_soportada.payer_ref.v1"
"""The HKDF label separating the payer-reference sub-key from every other use of the profile key.

Versioned, because a change to what the reference digests would need a key
that cannot reproduce the references this one produced.
"""


def retencion_soportada_payer_reference(payer_tax_id: str) -> str:
    """Return the active profile's keyed digest of one payer's canonical tax-identity token.

    Raises:
        RetencionSoportadaPersistenceError: The identifier is blank, or no
            profile session is open to derive the key from.
    """
    token = tax_id_identity_token(payer_tax_id)
    if not token:
        raise RetencionSoportadaPersistenceError("retencion_soportada_payer_reference")
    try:
        key = get_active_hmac_subkey(RETENCION_SOPORTADA_PAYER_REF_CONTEXT)
    except STORED_RECORD_FAILURES as exc:
        raise RetencionSoportadaPersistenceError("retencion_soportada_payer_reference") from exc
    return keyed_digest_hex(key=key, message=token.encode(UTF_8_ENCODING))


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate storage failures into the application-owned error, keeping the conflict distinct."""
    try:
        return action()
    except (RetencionSoportadaPersistenceError, RetencionSoportadaRevisionConflictError):
        raise
    except SecureObjectRevisionConflictError as exc:
        raise RetencionSoportadaRevisionConflictError from exc
    except (*STORED_RECORD_FAILURES, TypeError, KeyError) as exc:
        raise RetencionSoportadaPersistenceError(operation) from exc


class RetencionSoportadaRecordRepositoryAdapter(
    SecureBoundRepository[RetencionSoportadaRecord],
    RetencionSoportadaRecordRepository,
):
    """Bind the suffered-withholding port to encrypted secure-object storage."""

    namespace: ClassVar[str] = RETENCION_SOPORTADA_RECORDS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = RETENCION_SOPORTADA_RECORDS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = RETENCION_SOPORTADA_RECORDS_NAMESPACE.schema_version
    # Final: a constant narrowing of the base's mutable ``ClassVar[type[BaseModel]]``.
    payload_type: Final[type[RetencionSoportadaRecord]] = RetencionSoportadaRecord

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    @override
    def extract_identifier(self, payload: RetencionSoportadaRecord) -> str:
        return retencion_soportada_record_key(payload.identity)

    @override
    def payer_reference(self, payer_tax_id: str) -> str:
        """Return this profile's keyed digest of ``payer_tax_id``."""
        return retencion_soportada_payer_reference(payer_tax_id)

    @override
    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        """Return every payer record of ``ejercicio``, ordered by object key."""
        return _translate_storage_failure(
            "retencion_soportada_load_records",
            lambda: tuple(
                sorted(
                    (record for record in self.iter_records() if record.ejercicio == ejercicio),
                    key=self.extract_identifier,
                ),
            ),
        )

    @override
    def load_revisioned(self, identity: RetencionSoportadaIdentity) -> tuple[RetencionSoportadaRecord | None, str]:
        """Return the stored record at ``identity`` and the revision it was read at."""
        return _translate_storage_failure(
            "retencion_soportada_load_revisioned",
            lambda: self._load_revisioned(retencion_soportada_record_key(identity)),
        )

    def _load_revisioned(self, identifier: str) -> tuple[RetencionSoportadaRecord | None, str]:
        stored = self.secure_object_repository.load(
            self.namespace,
            identifier,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        )
        if stored is None:
            return None, ABSENT_SECURE_OBJECT_REVISION_ID
        payload = self._validate_envelope(stored.payload, subject=f"{self.namespace} revisioned row").payload
        if self.extract_identifier(payload) != identifier:
            raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
        return payload, stored.revision_id

    @override
    def save_revisioned(self, record: RetencionSoportadaRecord, *, expected_revision_id: str) -> None:
        """Store ``record`` only if its row is still at ``expected_revision_id``."""
        _translate_storage_failure(
            "retencion_soportada_save",
            lambda: self.secure_object_repository.save_many(
                (self.to_secure_object_write(record, expected_revision_id=expected_revision_id),),
            ),
        )

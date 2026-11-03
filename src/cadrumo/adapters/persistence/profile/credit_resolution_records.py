"""Encrypted persistence adapter for the operator's acceptances of disputed Modelo figures.

A resolution restates the amounts a calculation disagreed on, so it lives only in
an encrypted payload of the profile's own bucket. The row is stored under
``credit-resolution:{modelo}:{filing_year}:{period}:{finding_key}``, and the key
is digested again into the ``object_key`` column, as for every namespace. The
row-identity AAD binds namespace, key digest and schema version, and the key is
re-derived from the payload on load, so a substituted row is refused.

A storage failure is translated into the application-owned error and never into
an empty result: a caller that cannot read the resolutions must not read that as
there being none to find, nor as there being none to honour.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.domain.modelos.credit_resolution.CreditResolutionRecord`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final, override

from ....application.modelo.credit_resolution_repository import (
    CreditResolutionPersistenceError,
    CreditResolutionRepository,
    CreditResolutionRevisionConflictError,
    credit_resolution_key,
)
from ....core.classification.policies import SensitivityClass
from ....core.filing_year import FilingYear
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.modelos.credit_resolution import CreditResolutionIdentity, CreditResolutionRecord
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import STORED_RECORD_FAILURES, SecureObjectRevisionConflictError, SecureObjectRowIdentityError
from ..storage.secure_object_namespaces import MODELO_CREDIT_RESOLUTION_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

__all__ = ["CreditResolutionRepositoryAdapter"]


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate storage failures into the application-owned error, keeping the conflict distinct."""
    try:
        return action()
    except (CreditResolutionPersistenceError, CreditResolutionRevisionConflictError):
        raise
    except SecureObjectRevisionConflictError as exc:
        raise CreditResolutionRevisionConflictError from exc
    except (*STORED_RECORD_FAILURES, TypeError, KeyError) as exc:
        raise CreditResolutionPersistenceError(operation) from exc


class CreditResolutionRepositoryAdapter(SecureBoundRepository[CreditResolutionRecord], CreditResolutionRepository):
    """Bind the credit resolution port to encrypted secure-object storage."""

    namespace: ClassVar[str] = MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = MODELO_CREDIT_RESOLUTION_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = MODELO_CREDIT_RESOLUTION_NAMESPACE.schema_version
    # Final: a constant narrowing of the base's mutable ``ClassVar[type[BaseModel]]``.
    payload_type: Final[type[CreditResolutionRecord]] = CreditResolutionRecord

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    @override
    def extract_identifier(self, payload: CreditResolutionRecord) -> str:
        return credit_resolution_key(payload.identity)

    @override
    def load_for_work(self, *, modelo: str, filing_year: FilingYear, period: str) -> tuple[CreditResolutionRecord, ...]:
        """Return every resolution of one declaration, active or revoked, ordered by object key."""
        return tuple(
            record
            for record, _revision_id in self.list_revisioned(modelo=modelo, filing_year=filing_year, period=period)
        )

    @override
    def list_revisioned(
        self, *, modelo: str, filing_year: FilingYear, period: str
    ) -> tuple[tuple[CreditResolutionRecord, str], ...]:
        """Return every resolution of one declaration with its revision, ordered by object key."""

        def scan() -> tuple[tuple[CreditResolutionRecord, str], ...]:
            rows: list[tuple[str, CreditResolutionRecord, str]] = []
            for stored, envelope in self._iter_validated_rows():
                payload = envelope.payload
                identifier = self.extract_identifier(payload)
                if secure_object_key_digest(identifier) != stored.object_key:
                    raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
                fact = payload.disagreement
                if fact.modelo == modelo and fact.filing_year == filing_year and fact.period == period:
                    rows.append((identifier, payload, stored.revision_id))
            return tuple(
                (payload, revision_id) for _identifier, payload, revision_id in sorted(rows, key=lambda row: row[0])
            )

        return _translate_storage_failure("credit_resolution_list", scan)

    @override
    def load_revisioned(self, identity: CreditResolutionIdentity) -> tuple[CreditResolutionRecord | None, str]:
        """Return the stored resolution at ``identity`` and the revision it was read at."""
        return _translate_storage_failure(
            "credit_resolution_load", lambda: self._load_revisioned(credit_resolution_key(identity))
        )

    def _load_revisioned(self, identifier: str) -> tuple[CreditResolutionRecord | None, str]:
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
    def save_revisioned(self, record: CreditResolutionRecord, *, expected_revision_id: str) -> str:
        """Store ``record`` only if its row is still at ``expected_revision_id``; return the new revision."""

        def save() -> str:
            self.secure_object_repository.save_many(
                (self.to_secure_object_write(record, expected_revision_id=expected_revision_id),),
            )
            _stored, revision_id = self._load_revisioned(self.extract_identifier(record))
            return revision_id

        return _translate_storage_failure("credit_resolution_save", save)

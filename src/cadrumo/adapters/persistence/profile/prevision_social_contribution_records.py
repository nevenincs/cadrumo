"""Encrypted persistence adapter for the pension contribution certificate records.

The issuer's and the plan's tax identifiers live only inside the encrypted
payload. A record is stored under
``{ejercicio}:{issuer_ref}:{plan_ref|-}:{clave}:{subclave|-}``, where each
reference is an HMAC-SHA256 of the canonical tax-identity token under its own
sub-key of the active profile's data key, derived for this family alone. The
natural key is digested again into the ``object_key`` column, as for every
namespace.

An unkeyed hash of a tax identifier would not do: the identifier space is small
enough to enumerate. A digest under a key only this profile holds cannot be
inverted by whoever reads the key, and two profiles never derive the same
reference for one issuer.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.domain.renta.prevision_social_contribution.PrevisionSocialContribution`;
:class:`SensitivityClass`, the sensitivity classification of stored objects.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final, override

from ....application.aggregation.prevision_social_contribution_repository import (
    PrevisionSocialContributionPersistenceError,
    PrevisionSocialContributionRecordRepository,
    PrevisionSocialContributionRevisionConflictError,
    prevision_social_contribution_record_key,
)
from ....core.classification.policies import SensitivityClass
from ....core.external_constants import UTF_8_ENCODING
from ....core.identity.tax_id import tax_id_identity_token
from ....core.keyed_digest import keyed_digest_hex
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.renta.prevision_social_contribution import (
    PrevisionSocialContribution,
    PrevisionSocialContributionIdentity,
)
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import STORED_RECORD_FAILURES, SecureObjectRevisionConflictError, SecureObjectRowIdentityError
from ..storage.master_key.active_session import get_active_hmac_subkey
from ..storage.secure_object_namespaces import PREVISION_SOCIAL_CONTRIBUTION_RECORDS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

__all__ = [
    "PREVISION_SOCIAL_ISSUER_REF_CONTEXT",
    "PREVISION_SOCIAL_PLAN_REF_CONTEXT",
    "PrevisionSocialContributionRecordRepositoryAdapter",
]

PREVISION_SOCIAL_ISSUER_REF_CONTEXT: Final[bytes] = b"cadrumo.renta.prevision_social_contribution.issuer_ref.v1"
"""The HKDF label separating the issuer-reference sub-key from every other use of the profile key."""

PREVISION_SOCIAL_PLAN_REF_CONTEXT: Final[bytes] = b"cadrumo.renta.prevision_social_contribution.plan_ref.v1"
"""The HKDF label separating the plan-reference sub-key from every other use of the profile key."""


def _keyed_reference(tax_id: str, *, context: bytes, operation: str) -> str:
    token = tax_id_identity_token(tax_id)
    if not token:
        raise PrevisionSocialContributionPersistenceError(operation)
    try:
        key = get_active_hmac_subkey(context)
    except STORED_RECORD_FAILURES as exc:
        raise PrevisionSocialContributionPersistenceError(operation) from exc
    return keyed_digest_hex(key=key, message=token.encode(UTF_8_ENCODING))


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate storage failures into the application-owned error, keeping the conflict distinct."""
    try:
        return action()
    except (PrevisionSocialContributionPersistenceError, PrevisionSocialContributionRevisionConflictError):
        raise
    except SecureObjectRevisionConflictError as exc:
        raise PrevisionSocialContributionRevisionConflictError from exc
    except (*STORED_RECORD_FAILURES, TypeError, KeyError) as exc:
        raise PrevisionSocialContributionPersistenceError(operation) from exc


class PrevisionSocialContributionRecordRepositoryAdapter(
    SecureBoundRepository[PrevisionSocialContribution],
    PrevisionSocialContributionRecordRepository,
):
    """Bind the contribution-record port to encrypted secure-object storage."""

    namespace: ClassVar[str] = PREVISION_SOCIAL_CONTRIBUTION_RECORDS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = PREVISION_SOCIAL_CONTRIBUTION_RECORDS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = PREVISION_SOCIAL_CONTRIBUTION_RECORDS_NAMESPACE.schema_version
    # Final: a constant narrowing of the base's mutable ``ClassVar[type[BaseModel]]``.
    payload_type: Final[type[PrevisionSocialContribution]] = PrevisionSocialContribution

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    @override
    def extract_identifier(self, payload: PrevisionSocialContribution) -> str:
        return prevision_social_contribution_record_key(payload.identity)

    @override
    def issuer_reference(self, issuer_tax_id: str) -> str:
        """Return this profile's keyed digest of ``issuer_tax_id``."""
        return _keyed_reference(
            issuer_tax_id, context=PREVISION_SOCIAL_ISSUER_REF_CONTEXT, operation="prevision_social_issuer_reference"
        )

    @override
    def plan_reference(self, plan_tax_id: str) -> str:
        """Return this profile's keyed digest of ``plan_tax_id``."""
        return _keyed_reference(
            plan_tax_id, context=PREVISION_SOCIAL_PLAN_REF_CONTEXT, operation="prevision_social_plan_reference"
        )

    @override
    def load_records(self, ejercicio: int) -> tuple[PrevisionSocialContribution, ...]:
        """Return every record of ``ejercicio``, ordered by object key."""
        return tuple(record for record, _revision in self.list_revisioned(ejercicio))

    @override
    def list_revisioned(self, ejercicio: int) -> tuple[tuple[PrevisionSocialContribution, str], ...]:
        """Return every record of ``ejercicio`` with its revision, ordered by object key."""

        def scan() -> tuple[tuple[PrevisionSocialContribution, str], ...]:
            rows: list[tuple[str, PrevisionSocialContribution, str]] = []
            for stored, envelope in self._iter_validated_rows():
                payload = envelope.payload
                identifier = self.extract_identifier(payload)
                if secure_object_key_digest(identifier) != stored.object_key:
                    raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
                if payload.ejercicio == ejercicio:
                    rows.append((identifier, payload, stored.revision_id))
            return tuple(
                (payload, revision_id) for _identifier, payload, revision_id in sorted(rows, key=lambda row: row[0])
            )

        return _translate_storage_failure("prevision_social_list_records", scan)

    @override
    def load_revisioned(
        self, identity: PrevisionSocialContributionIdentity
    ) -> tuple[PrevisionSocialContribution | None, str]:
        """Return the stored record at ``identity`` and the revision it was read at."""

        def load() -> tuple[PrevisionSocialContribution | None, str]:
            identifier = prevision_social_contribution_record_key(identity)
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

        return _translate_storage_failure("prevision_social_load_revisioned", load)

    @override
    def save_revisioned(self, record: PrevisionSocialContribution, *, expected_revision_id: str) -> None:
        """Store ``record`` only if its row is still at ``expected_revision_id``."""
        _translate_storage_failure(
            "prevision_social_save",
            lambda: self.secure_object_repository.save_many(
                (self.to_secure_object_write(record, expected_revision_id=expected_revision_id),),
            ),
        )

    @override
    def delete_revisioned(self, identity: PrevisionSocialContributionIdentity, *, expected_revision_id: str) -> None:
        """Remove the row at ``identity`` only if it is still at ``expected_revision_id``."""
        deletion = self.to_secure_object_deletion(prevision_social_contribution_record_key(identity)).model_copy(
            update={"expected_revision_id": expected_revision_id},
        )
        _translate_storage_failure(
            "prevision_social_delete", lambda: self.secure_object_repository.apply_batch((), (deletion,))
        )

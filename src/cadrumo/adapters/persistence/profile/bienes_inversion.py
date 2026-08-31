"""Encrypted SQL persistence for the capital-goods IVA regularización register.

The :class:`domain.bienes_inversion.BienesInversionIvaRegister` document is
stored as a ``FINANCIAL``
:class:`adapters.persistence.storage.SensitivityClass` secure object in the
primary database through
:class:`adapters.persistence.storage.SecureObjectRepository`. The singleton
namespace, default object key, schema version, and custody contracts come from
:data:`adapters.persistence.storage.PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE`.

The register is authoritative primary state (the operator declares each tracked
capital good), not a rebuildable cache; it therefore carries a strict
save/load/equality roundtrip plus an anti-tautology proof.

See Also:
    :mod:`domain.bienes_inversion`
        Typed register payload models persisted here.
    :mod:`adapters.persistence.profile.assets`
        Sibling profile-local secure-object adapter whose shape this mirrors.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionRecordError,
)
from ..storage._secure_object_namespaces import PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE
from ..storage.sql import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

BIENES_INVERSION_REGISTER_FILENAME = "bienes-inversion-iva-register.secure-object"


def load_bienes_inversion_register() -> BienesInversionIvaRegister:
    """Load the register, returning an empty register when absent.

    Returns:
        Persisted :class:`BienesInversionIvaRegister`, or an empty one when no
        envelope exists.
    """
    return BienesInversionIvaRegisterRepository().load()


def save_bienes_inversion_register(register: BienesInversionIvaRegister) -> Path:
    """Persist ``register`` as a governed FINANCIAL-class encrypted envelope.

    Args:
        register: Register document to encrypt and write.

    Returns:
        Logical secure-object marker for the persisted register.
    """
    repository = BienesInversionIvaRegisterRepository()
    repository.save(register)
    return repository.envelope_path


def declare_bien_inversion(record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
    """Atomically add ``record`` to the encrypted register.

    Args:
        record: Capital-good record to insert.

    Returns:
        The updated :class:`BienesInversionIvaRegister` including the new record.
    """
    return BienesInversionIvaRegisterRepository().add(record)


class BienesInversionIvaRegisterRepository:
    """Governed repository for the encrypted register singleton.

    The singleton row is owned by
    :data:`adapters.persistence.storage.PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE`
    and persisted through
    :class:`adapters.persistence.storage.SecureObjectRepository`.
    """

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Initialise the repository.

        Args:
            bucket_id: Explicit bucket to bind to, resolved through
                :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`.
                Lets a caller that already knows the target bucket (e.g. the
                calculate-path advisory collector, which receives ``bucket_id``
                from its context rather than the process-global active-profile
                pointer) load the register for that bucket explicitly. Ignored
                when ``objects`` is supplied.
            objects: Explicit :class:`SecureObjectRepository` override (tests).
                When neither ``objects`` nor ``bucket_id`` is supplied, defaults
                to the active-bucket secure object store.
        """
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
            model_type=BienesInversionIvaRegister,
            empty_document=BienesInversionIvaRegister,
        )

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return self._storage.logical_path(BIENES_INVERSION_REGISTER_FILENAME)

    def load(self) -> BienesInversionIvaRegister:
        """Load the register, returning an empty document when absent.

        Returns:
            Decrypted :class:`BienesInversionIvaRegister`.

        Raises:
            BienInversionRecordError: When the envelope exists but cannot be
                loaded or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "bienes inversion register load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise BienInversionRecordError(
                f"unable to load bienes inversion register: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="adapters.persistence.profile.bienes_inversion.errors.load_register_failed",
            ) from exc

    def save(self, register: BienesInversionIvaRegister) -> None:
        """Persist ``register`` as FINANCIAL-class ciphertext.

        Args:
            register: Register document to encrypt and write.
        """
        self._save_unlocked(register)
        _log.info(
            "saved %d bienes inversion records to secure object %s",
            len(register.records),
            self._storage.object_key,
        )

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        """Atomically add ``record`` and refuse duplicate identifiers.

        The register is a singleton row, so adding one record rewrites the whole
        document. Read, duplicate-check, rebuild, and write ran unguarded, so
        two callers adding DIFFERENT capital goods both read the same register
        and the later write silently discarded the earlier record -- a lost
        update the duplicate check could never notice, because the two records
        never met in one document.

        The mutation now runs through the shared revision-guarded unit of work:
        the write carries the revision the register was read at, and a
        concurrent write makes it re-read and re-apply rather than overwrite.
        The duplicate check lives inside the mutation so it is re-evaluated
        against the newly-current register on every attempt.

        Args:
            record: Capital-good record to insert.

        Returns:
            The :class:`BienesInversionIvaRegister` including the new record.

        Raises:
            BienInversionRecordError: When a record with the same identifier
                already exists.
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _insert(current: BienesInversionIvaRegister) -> BienesInversionIvaRegister:
            if any(existing.identifier == record.identifier for existing in current.records):
                raise BienInversionRecordError(
                    f"bien de inversion {record.identifier!r} already exists",
                    context={"record_id": record.identifier},
                    translated_message="adapters.persistence.profile.bienes_inversion.errors.record_already_exists",
                )
            return BienesInversionIvaRegister(records=(*current.records, record))

        return self._storage.mutate(_insert)

    def _save_unlocked(self, register: BienesInversionIvaRegister) -> None:
        self._storage.save(register)


__all__ = [
    "BienesInversionIvaRegisterRepository",
    "declare_bien_inversion",
    "load_bienes_inversion_register",
    "save_bienes_inversion_register",
]

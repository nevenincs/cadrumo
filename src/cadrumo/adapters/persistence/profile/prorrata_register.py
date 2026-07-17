"""Encrypted SQL persistence for the cross-period IVA prorrata register.

The :class:`domain.prorrata_register.ProrrataRegister` document is stored as a
``FINANCIAL`` :class:`adapters.persistence.storage.SensitivityClass` secure
object in the primary database through
:class:`adapters.persistence.storage.SecureObjectRepository`. The singleton
namespace, default object key, schema version, and custody contracts come from
:data:`adapters.persistence.storage.PROFILE_PRORRATA_REGISTER_NAMESPACE`.

The register is authoritative primary state (the taxpayer's per-ejercicio
provisional and settled prorrata percentages, seeded from the stamped prior
settlement observation), not a rebuildable cache; it therefore carries a strict
save/load/equality roundtrip plus an anti-tautology proof.

See Also:
    :mod:`domain.prorrata_register`
        Typed register payload models persisted here.
    :mod:`adapters.persistence.profile.bienes_inversion`
        Sibling profile-local secure-object adapter whose shape this mirrors.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors import CadrumoError
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
    SectorDefinition,
)
from ..storage import (
    PROFILE_PRORRATA_REGISTER_NAMESPACE,
    SecureObjectRepository,
    SecureObjectWrite,
    SensitivityClass,
    secure_object_logical_path,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
)

_log = get_logger(__name__)

PRORRATA_REGISTER_FILENAME = "prorrata-register.secure-object"
_REGISTER_SECURE_OBJECT_VERSION = PROFILE_PRORRATA_REGISTER_NAMESPACE.schema_version
_REGISTER_NAMESPACE = PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace
_REGISTER_OBJECT_KEY = PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key()


def _secure_object_marker(namespace: str, filename: str) -> Path:
    return secure_object_logical_path(namespace, filename)


def load_prorrata_register() -> ProrrataRegister:
    """Load the register, returning an empty register when absent.

    Returns:
        Persisted :class:`ProrrataRegister`, or an empty one when no envelope
        exists.
    """
    return ProrrataRegisterRepository().load()


def save_prorrata_register(register: ProrrataRegister) -> Path:
    """Persist ``register`` as a governed FINANCIAL-class encrypted envelope.

    Args:
        register: Register document to encrypt and write.

    Returns:
        Logical secure-object marker for the persisted register.
    """
    repository = ProrrataRegisterRepository()
    repository.save(register)
    return repository.envelope_path


def declare_prorrata_entry(entry: ProrrataRegisterEntry) -> ProrrataRegister:
    """Atomically add or replace ``entry`` in the encrypted register by its key.

    Args:
        entry: The per-ejercicio entry to insert or update.

    Returns:
        The updated :class:`ProrrataRegister` including the entry.
    """
    return ProrrataRegisterRepository().upsert_entry(entry)


class ProrrataRegisterRepository:
    """Governed repository for the encrypted register singleton.

    The singleton row is owned by
    :data:`adapters.persistence.storage.PROFILE_PRORRATA_REGISTER_NAMESPACE`
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
                Lets a caller that already knows the target bucket load the
                register for that bucket explicitly. Ignored when ``objects`` is
                supplied.
            objects: Explicit :class:`SecureObjectRepository` override (tests).
                When neither ``objects`` nor ``bucket_id`` is supplied, defaults
                to the active-bucket secure object store.
        """
        if objects is not None:
            self._objects = objects
        elif bucket_id is not None:
            self._objects = secure_object_repository_for_bucket(bucket_id)
        else:
            self._objects = secure_object_repository_for_active_bucket()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return _secure_object_marker(_REGISTER_NAMESPACE, PRORRATA_REGISTER_FILENAME)

    def load(self) -> ProrrataRegister:
        """Load the register, returning an empty document when absent.

        Returns:
            Decrypted :class:`ProrrataRegister`.

        Raises:
            ProrrataRegisterError: When the envelope exists but cannot be loaded
                or decrypted.
        """
        try:
            record = self._objects.load(
                _REGISTER_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_REGISTER_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return ProrrataRegister()
            return ProrrataRegister.model_validate_json(record.payload.decode(UTF_8_ENCODING))
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "prorrata register load failed",
                extra={
                    "namespace": _REGISTER_NAMESPACE,
                    "object_key": self._object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise ProrrataRegisterError(
                f"unable to load prorrata register: {self._object_key}",
                context={"namespace": _REGISTER_NAMESPACE, "object_key": self._object_key},
            ) from exc

    def save(self, register: ProrrataRegister) -> None:
        """Persist ``register`` as FINANCIAL-class ciphertext.

        Args:
            register: Register document to encrypt and write.
        """
        self._objects.save_many((self.to_secure_object_write(register),))
        _log.info(
            "saved %d prorrata register entries to secure object %s",
            len(register.entries),
            self._object_key,
        )

    def to_secure_object_write(self, register: ProrrataRegister) -> SecureObjectWrite:
        """Return the secure-object upsert for ``register`` without committing it.

        The filing persistence path co-emits the settled prorrata register with
        the filed revision and filing catalogue in one secure-object transaction,
        mirroring the participation-index write pattern.
        """
        written_at = now()
        return SecureObjectWrite(
            namespace=_REGISTER_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_REGISTER_SECURE_OBJECT_VERSION,
            written_at=written_at,
            payload=register.model_dump_json().encode(UTF_8_ENCODING),
        )

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace ``entry`` by its ``(ejercicio, sector_id)`` key.

        The register carries one entry per ``(ejercicio, sector_id)`` key across
        the ejercicio's lifecycle (provisional seed then definitive settlement),
        so declaring an entry for an existing key replaces it rather than raising.

        Args:
            entry: The entry to insert or update.

        Returns:
            The :class:`ProrrataRegister` including the entry.
        """
        current = self.load()
        retained = tuple(
            existing
            for existing in current.entries
            if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
        )
        updated = ProrrataRegister(
            entries=(*retained, entry),
            sector_definitions=current.sector_definitions,
        )
        self._save_unlocked(updated)
        return updated

    def upsert_sector_definition(self, definition: SectorDefinition) -> ProrrataRegister:
        """Atomically add or replace a differentiated-sector definition by its ``sector_id``.

        The register carries one :class:`SectorDefinition` per ``sector_id``
        (LIVA arts. 9.1.c / 101); declaring a sector whose id already exists
        replaces it rather than raising. Existing per-ejercicio entries are
        preserved, so the operator can declare the partition and the per-sector
        entries in either order.

        Args:
            definition: The differentiated-sector partition entry to insert or
                update.

        Returns:
            The updated :class:`ProrrataRegister` including the definition.
        """
        current = self.load()
        retained = tuple(
            existing for existing in current.sector_definitions if existing.sector_id != definition.sector_id
        )
        updated = ProrrataRegister(
            entries=current.entries,
            sector_definitions=(*retained, definition),
        )
        self._save_unlocked(updated)
        return updated

    def _save_unlocked(self, register: ProrrataRegister) -> None:
        self._objects.save_many((self.to_secure_object_write(register),))

    @property
    def _object_key(self) -> str:
        return _REGISTER_OBJECT_KEY


__all__ = [
    "ProrrataRegisterRepository",
    "declare_prorrata_entry",
    "load_prorrata_register",
    "save_prorrata_register",
]

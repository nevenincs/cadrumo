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

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
    SectorDefinition,
)
from ..storage._secure_object_namespaces import PROFILE_PRORRATA_REGISTER_NAMESPACE
from ..storage.sql import SecureObjectRepository, SecureObjectWrite
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

PRORRATA_REGISTER_FILENAME = "prorrata-register.secure-object"


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


def declare_prorrata_activity_row(row: ProrrataActivityRow) -> ProrrataRegister:
    """Atomically add or replace a canonical activity row by stable identity."""
    return ProrrataRegisterRepository().upsert_activity_row(row)


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
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=PROFILE_PRORRATA_REGISTER_NAMESPACE,
            model_type=ProrrataRegister,
            empty_document=ProrrataRegister,
        )

    @property
    def bucket_id(self) -> str | None:
        """Return the explicit profile bucket identity, when one was supplied.

        A repository constructed against an injected secure-object store cannot
        infer that store's bucket safely; it deliberately remains unbound until
        the caller supplies ``bucket_id``. Consumers that combine authorities
        from one filing bucket must reject that unbound shape rather than
        treating it as interchangeable with an explicitly owned register.
        """
        return self._bucket_id

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return self._storage.logical_path(PRORRATA_REGISTER_FILENAME)

    def load(self) -> ProrrataRegister:
        """Load the register, returning an empty document when absent.

        Returns:
            Decrypted :class:`ProrrataRegister`.

        Raises:
            ProrrataRegisterError: When the envelope exists but cannot be loaded
                or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "prorrata register load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise ProrrataRegisterError(
                f"unable to load prorrata register: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
            ) from exc

    def save(self, register: ProrrataRegister) -> None:
        """Persist ``register`` as FINANCIAL-class ciphertext.

        Args:
            register: Register document to encrypt and write.
        """
        self._storage.save(register)
        _log.info(
            "saved %d prorrata register entries to secure object %s",
            len(register.entries),
            self._storage.object_key,
        )

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        """Return the register and the revision id it was read at.

        The read a guarded co-commit needs: this register is composed into the
        calculate batch, so it cannot use a self-committing mutation, and an
        unguarded write puts the whole singleton row back over a sector entry
        another writer added in between.
        """
        return self._storage.load_revisioned()

    def to_secure_object_write(
        self,
        register: ProrrataRegister,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``register`` without committing it.

        The filing persistence path co-emits the settled prorrata register with
        the filed revision and filing catalogue in one secure-object transaction,
        mirroring the participation-index write pattern.
        """
        return self._storage.to_secure_object_write(register, expected_revision_id=expected_revision_id)

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace ``entry`` by its ``(ejercicio, sector_id)`` key.

        The register carries one entry per ``(ejercicio, sector_id)`` key across
        the ejercicio's lifecycle (provisional seed then definitive settlement),
        so declaring an entry for an existing key replaces it rather than raising.

        The register is a singleton row, so this "add or replace one entry" is
        really read-whole-register, rebuild, write-whole-register. Run
        unguarded, two callers declaring entries for DIFFERENT keys both read
        the same register and the later save silently dropped the earlier
        caller's entry -- a lost update, invisible to the key-replacement logic
        because the two entries never met in one document.

        The rebuild now runs through the shared revision-guarded unit of work,
        so a concurrent write makes it re-read and re-apply rather than
        overwrite.

        Args:
            entry: The entry to insert or update.

        Returns:
            The :class:`ProrrataRegister` including the entry.

        Raises:
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            retained = tuple(
                existing
                for existing in current.entries
                if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
            )
            return ProrrataRegister(
                entries=(*retained, entry),
                sector_definitions=current.sector_definitions,
                activity_rows=current.activity_rows,
            )

        return self._storage.mutate(_apply)

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

        Carries the same revision guard as :meth:`upsert_entry`, and for the
        same reason: the two methods write the SAME singleton row, so an
        unguarded sector declaration could discard a concurrently-declared
        entry just as easily as another sector definition.

        Returns:
            The updated :class:`ProrrataRegister` including the definition.

        Raises:
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            retained = tuple(
                existing for existing in current.sector_definitions if existing.sector_id != definition.sector_id
            )
            return ProrrataRegister(
                entries=current.entries,
                sector_definitions=(*retained, definition),
                activity_rows=current.activity_rows,
            )

        return self._storage.mutate(_apply)

    def upsert_activity_row(self, row: ProrrataActivityRow) -> ProrrataRegister:
        """Atomically add or replace one row by its ``(ejercicio, activity_id)`` key."""

        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            retained = tuple(
                existing
                for existing in current.activity_rows
                if (existing.ejercicio, existing.activity_id) != (row.ejercicio, row.activity_id)
            )
            return ProrrataRegister(
                entries=current.entries,
                sector_definitions=current.sector_definitions,
                activity_rows=(*retained, row),
            )

        return self._storage.mutate(_apply)


__all__ = [
    "ProrrataRegisterRepository",
    "declare_prorrata_activity_row",
    "declare_prorrata_entry",
    "load_prorrata_register",
    "save_prorrata_register",
]

"""Encrypted SQL persistence for the cross-period IVA prorrata register.

The :class:`domain.prorrata_register.register.ProrrataRegister` document is stored as a
``FINANCIAL`` :class:`~core.classification.policies.SensitivityClass` secure
object in the primary database through
:class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`. The singleton
namespace, default object key, schema version, and custody contracts come from
:data:`adapters.persistence.storage.secure_object_namespaces.PROFILE_PRORRATA_REGISTER_NAMESPACE`.

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

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from ....application.calculations.observations_repository import observation_key_for_token
from ....application.prorrata_register.ports import ProrrataPriorSettlementSourceSnapshot
from ....application.prorrata_register.sector_lifecycle import (
    ProrrataSectorLifecycleUnavailableError,
    seed_sector_carried_definitive_from_register,
    settle_sector_definitive,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
    SectorDefinition,
)
from ..storage.errors import StorageValidationError
from ..storage.secure_object_namespaces import CALCULATION_OBSERVATIONS_NAMESPACE, PROFILE_PRORRATA_REGISTER_NAMESPACE
from ..storage.sql.secure_object_records import SecureObjectRevisionAssertion
from ..storage.sql.secure_objects import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

PRORRATA_REGISTER_FILENAME = "prorrata-register.secure-object"


class ProrrataRegisterRepository:
    """Governed repository for the encrypted register singleton.

    The singleton row is owned by
    :data:`adapters.persistence.storage.secure_object_namespaces.PROFILE_PRORRATA_REGISTER_NAMESPACE`
    and persisted through
    :class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
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
                :func:`~adapters.persistence.storage.runtime_repository.secure_object_repository_for_bucket`.
                Lets a caller that already knows the target bucket load the
                register for that bucket explicitly. Ignored when ``objects`` is
                supplied.
            objects: Explicit :class:`SecureObjectRepository` override (tests).
                When neither ``objects`` nor ``bucket_id`` is supplied, defaults
                to the active-bucket secure object store.
        """
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        resolved_objects = resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id)
        self._objects = resolved_objects
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolved_objects,
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

    def commit_whole_carried_seed(
        self,
        register: ProrrataRegister,
        *,
        ejercicio: int,
        expected_revision_id: str,
        source_snapshot: ProrrataPriorSettlementSourceSnapshot,
    ) -> None:
        """Fence both possible unmembered prior 303 rows and the register in one transaction."""
        if source_snapshot.backend_identity is not self._objects.engine:
            raise StorageValidationError("prorrata seed source and target must share the same profile store")
        expected = {
            (CALCULATION_OBSERVATIONS_NAMESPACE.namespace, observation_key_for_token("303", ejercicio - 1, token))
            for token in ("4T", "12")
        }
        actual = {(revision.namespace, revision.object_key) for revision in source_snapshot.revisions}
        if len(source_snapshot.revisions) != 2 or actual != expected:
            raise StorageValidationError("prorrata seed requires both prior-year 303 source revisions")
        assertions = tuple(
            SecureObjectRevisionAssertion(
                namespace=revision.namespace,
                object_key=revision.object_key,
                expected_revision_id=revision.expected_revision_id,
            )
            for revision in source_snapshot.revisions
        )
        self._objects.apply_batch(
            (self.to_secure_object_write(register, expected_revision_id=expected_revision_id),),
            assertions=assertions,
        )

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

    def seed_sector_carried(
        self,
        ejercicio: int,
        sector_id: str,
        *,
        validate_entry: Callable[[ProrrataRegisterEntry], None],
    ) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Read the prior definitive again on every register CAS attempt."""

        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            entry = seed_sector_carried_definitive_from_register(current, ejercicio=ejercicio, sector_id=sector_id)
            if entry is None:
                raise ProrrataSectorLifecycleUnavailableError(
                    f"prior definitive prorrata is absent for sector {sector_id} in {ejercicio - 1}"
                )
            validate_entry(entry)
            return _replace_entry(current, entry)

        committed = self._storage.mutate(_apply)
        entry = committed.entry_for(ejercicio, sector_id=sector_id)
        if entry is None:
            raise ProrrataRegisterError("committed sector carry entry is missing")
        return committed, entry

    def settle_sector(
        self,
        ejercicio: int,
        sector_id: str,
        *,
        con_derecho_volume: Decimal,
        sin_derecho_volume: Decimal,
        producing_snapshot_ref: RegistrySnapshotRef,
        validate_entry: Callable[[ProrrataRegisterEntry], None],
    ) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Settle from the latest current-year sector entry on each CAS attempt."""

        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            previous = current.entry_for(ejercicio, sector_id=sector_id)
            if previous is None:
                raise ProrrataSectorLifecycleUnavailableError(
                    f"current provisional prorrata is absent for sector {sector_id} in {ejercicio}"
                )
            entry = settle_sector_definitive(
                previous,
                con_derecho_volume=con_derecho_volume,
                sin_derecho_volume=sin_derecho_volume,
                producing_snapshot_ref=producing_snapshot_ref,
            )
            validate_entry(entry)
            return _replace_entry(current, entry)

        committed = self._storage.mutate(_apply)
        entry = committed.entry_for(ejercicio, sector_id=sector_id)
        if entry is None:
            raise ProrrataRegisterError("committed sector settlement entry is missing")
        return committed, entry

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


__all__ = [
    "ProrrataRegisterRepository",
]


def _replace_entry(current: ProrrataRegister, entry: ProrrataRegisterEntry) -> ProrrataRegister:
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

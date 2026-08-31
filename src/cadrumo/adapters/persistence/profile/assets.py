"""Encrypted SQL persistence for actividad economica asset and amortizacion ledgers.

:class:`AssetRecord`, :class:`AssetsLedgerDocument`, and
:class:`AmortizacionLedger` payloads are stored as
``FINANCIAL`` :class:`adapters.persistence.storage.SensitivityClass`
secure objects in the primary database through
:class:`adapters.persistence.storage.SecureObjectRepository`. The
singleton namespace, default object key, schema version, and custody contracts
come from
:data:`adapters.persistence.storage.PROFILE_ASSETS_LEDGER_NAMESPACE` and
:data:`adapters.persistence.storage.PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE`.

See Also:
    :mod:`domain.contribuyente.assets`
        Typed asset and amortizacion payload models persisted here.
    :mod:`adapters.persistence.profile.inventory`
        Sibling profile-local secure-object adapter for stock valuation ledgers.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.contribuyente.assets.records import (
    AmortizacionLedger,
    AssetRecord,
    AssetRecordError,
    AssetsLedgerDocument,
)
from ..storage._secure_object_namespaces import (
    PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
    PROFILE_ASSETS_LEDGER_NAMESPACE,
)
from ..storage.sql import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

ASSETS_LEDGER_FILENAME = "assets-ledger.secure-object"
ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortization-ledger.secure-object"


def load_assets() -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger.

    Returns:
        Tuple of :class:`AssetRecord` entries, empty when the ledger is absent.
    """
    return AssetsLedgerRepository().load().assets


def save_assets(assets: tuple[AssetRecord, ...]) -> Path:
    """Persist ``assets`` as a governed FINANCIAL-class encrypted envelope.

    The storage contract comes from
    :data:`adapters.persistence.storage.PROFILE_ASSETS_LEDGER_NAMESPACE`.

    Args:
        assets: Asset records to persist.

    Returns:
        Logical secure-object marker for the persisted ledger.
    """
    repository = AssetsLedgerRepository()
    repository.save(AssetsLedgerDocument(assets=assets))
    return repository.envelope_path


def add_asset(asset: AssetRecord) -> AssetsLedgerDocument:
    """Atomically add ``asset`` to the encrypted asset ledger.

    Args:
        asset: Asset record to insert.

    Returns:
        The updated :class:`AssetsLedgerDocument` including the newly inserted asset.
    """
    return AssetsLedgerRepository().add(asset)


def load_amortizacion_ledger() -> AmortizacionLedger:
    """Load the amortizacion ledger, returning an empty ledger when absent.

    Returns:
        Persisted :class:`AmortizacionLedger` or an empty one when no envelope exists.
    """
    return AmortizacionLedgerRepository().load()


def save_amortizacion_ledger(ledger: AmortizacionLedger) -> Path:
    """Persist ``ledger`` as a governed FINANCIAL-class encrypted envelope.

    The storage contract comes from
    :data:`adapters.persistence.storage.PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE`.

    Args:
        ledger: Amortizacion ledger to persist.

    Returns:
        Logical secure-object marker for the persisted ledger.
    """
    repository = AmortizacionLedgerRepository()
    repository.save(ledger)
    return repository.envelope_path


class AssetsLedgerRepository:
    """Governed repository for the encrypted :class:`AssetsLedgerDocument` singleton.

    The singleton row is owned by
    :data:`adapters.persistence.storage.PROFILE_ASSETS_LEDGER_NAMESPACE`
    and persisted through
    :class:`adapters.persistence.storage.SecureObjectRepository`.
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Initialise the repository, defaulting to the active-bucket secure object store."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects),
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return self._storage.logical_path(ASSETS_LEDGER_FILENAME)

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""
        return self._storage.logical_path("assets-ledger.lock")

    def load(self) -> AssetsLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted :class:`AssetsLedgerDocument`.

        Raises:
            AssetRecordError: When the envelope exists but cannot be loaded or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "asset ledger load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise AssetRecordError(
                f"unable to load asset ledger: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="adapters.persistence.profile.assets.errors.load_asset_ledger_failed",
            ) from exc

    def save(self, document: AssetsLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        The classification, schema version, namespace, and object key are taken
        from
        :data:`adapters.persistence.storage.PROFILE_ASSETS_LEDGER_NAMESPACE`.

        Args:
            document: Ledger document to encrypt and write.
        """
        validated_document = AssetsLedgerDocument.model_validate(document.model_dump())
        self._save_unlocked(validated_document)
        _log.info(
            "saved %d asset records to secure object %s",
            len(validated_document.assets),
            self._storage.object_key,
        )

    def add(self, asset: AssetRecord) -> AssetsLedgerDocument:
        """Atomically add ``asset`` and refuse duplicate identifiers.

        The ledger is a singleton row, so adding one asset rewrites the whole
        document. Read, duplicate-check, rebuild, and write ran unguarded, so
        two callers adding DIFFERENT assets both read the same ledger and the
        later write silently discarded the earlier asset -- a lost update the
        duplicate check could never notice, because the two assets never met in
        one document.

        The mutation now runs through the shared revision-guarded unit of work:
        the write carries the revision the ledger was read at, and a concurrent
        write makes it re-read and re-apply rather than overwrite. The duplicate
        check lives inside the mutation so it is re-evaluated against the
        newly-current ledger on every attempt.

        Args:
            asset: Asset record to insert.

        Returns:
            The :class:`AssetsLedgerDocument` including the new asset.

        Raises:
            AssetRecordError: When an asset with the same identifier already exists.
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _insert(current: AssetsLedgerDocument) -> AssetsLedgerDocument:
            if any(existing.identifier == asset.identifier for existing in current.assets):
                raise AssetRecordError(
                    f"asset {asset.identifier!r} already exists",
                    context={"asset_id": asset.identifier},
                    translated_message="adapters.persistence.profile.assets.errors.asset_already_exists",
                )
            return AssetsLedgerDocument(assets=(*current.assets, asset))

        return self._storage.mutate(_insert)

    def _save_unlocked(self, document: AssetsLedgerDocument) -> None:
        self._storage.save(document)


class AmortizacionLedgerRepository:
    """Governed repository for the encrypted :class:`AmortizacionLedger` singleton.

    Mirrors :class:`AssetsLedgerRepository` for amortizacion entries; the
    payload type is :class:`AmortizacionLedger`. Its singleton row is owned by
    :data:`adapters.persistence.storage.PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE`
    and persisted through
    :class:`adapters.persistence.storage.SecureObjectRepository`.
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Initialise the repository, defaulting to the active-bucket secure object store."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects),
            definition=PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
            model_type=AmortizacionLedger,
            empty_document=AmortizacionLedger,
        )

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return self._storage.logical_path(ASSETS_AMORTIZATION_LEDGER_FILENAME)

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""
        return self._storage.logical_path("assets-amortization-ledger.lock")

    def load(self) -> AmortizacionLedger:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted :class:`AmortizacionLedger`.

        Raises:
            AssetRecordError: When the envelope exists but cannot be loaded or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "asset amortizacion ledger load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise AssetRecordError(
                f"unable to load amortizacion ledger: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="adapters.persistence.profile.assets.errors.load_amortizacion_ledger_failed",
            ) from exc

    def save(self, ledger: AmortizacionLedger) -> None:
        """Persist ``ledger`` as FINANCIAL-class ciphertext.

        The classification, schema version, namespace, and object key are taken
        from
        :data:`adapters.persistence.storage.PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE`.

        Args:
            ledger: Amortizacion ledger to encrypt and write.
        """
        self._save_unlocked(ledger)
        _log.info("saved amortizacion ledger to secure object %s", self._storage.object_key)

    def _load_unlocked(self) -> AmortizacionLedger:
        return self.load()

    def _save_unlocked(self, ledger: AmortizacionLedger) -> None:
        self._storage.save(ledger)


__all__ = [
    "AmortizacionLedgerRepository",
    "AssetsLedgerRepository",
    "add_asset",
    "load_amortizacion_ledger",
    "load_assets",
    "save_amortizacion_ledger",
    "save_assets",
]

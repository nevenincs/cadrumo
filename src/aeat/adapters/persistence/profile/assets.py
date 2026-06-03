"""Encrypted SQL persistence for actividad economica asset and amortizacion ledgers.

:class:`aeat.domain.contribuyente.assets.AssetRecord` and
:class:`aeat.domain.contribuyente.assets.AmortizacionLedger` payloads are stored
as :class:`SensitivityClass` FINANCIAL secure objects in the primary database
through :class:`SecureObjectRepository`.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors import AeatError
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.contribuyente.assets import (
    AmortizacionLedger,
    AssetRecord,
    AssetRecordError,
    AssetsLedgerDocument,
)
from ..storage import (
    PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
    PROFILE_ASSETS_LEDGER_NAMESPACE,
    SensitivityClass,
    secure_object_logical_path,
)
from ..storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.sql import SecureObjectRepository

_log = get_logger(__name__)

ASSETS_LEDGER_FILENAME = "assets-ledger.secure-object"
ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortization-ledger.secure-object"
_ASSETS_SECURE_OBJECT_VERSION = PROFILE_ASSETS_LEDGER_NAMESPACE.schema_version
_AMORTIZACION_SECURE_OBJECT_VERSION = PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE.schema_version
_ASSETS_NAMESPACE = PROFILE_ASSETS_LEDGER_NAMESPACE.namespace
_AMORTIZACION_NAMESPACE = PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE.namespace
_ASSETS_OBJECT_KEY = PROFILE_ASSETS_LEDGER_NAMESPACE.require_default_object_key()
_AMORTIZACION_OBJECT_KEY = PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE.require_default_object_key()


def _secure_object_marker(namespace: str, filename: str) -> Path:
    return secure_object_logical_path(namespace, filename)


def load_assets() -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger.

    Returns:
        Tuple of :class:`AssetRecord` entries, empty when the ledger is absent.
    """
    return AssetsLedgerRepository().load().assets


def save_assets(assets: tuple[AssetRecord, ...]) -> Path:
    """Persist ``assets`` as a governed FINANCIAL-class encrypted envelope.

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

    Args:
        ledger: Amortizacion ledger to persist.

    Returns:
        Logical secure-object marker for the persisted ledger.
    """
    repository = AmortizacionLedgerRepository()
    repository.save(ledger)
    return repository.envelope_path


class AssetsLedgerRepository:
    """Governed repository for the encrypted assets ledger."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Initialise the repository, defaulting to the active-bucket secure object store."""
        self._objects = objects if objects is not None else secure_object_repository_for_active_bucket()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return _secure_object_marker(_ASSETS_NAMESPACE, ASSETS_LEDGER_FILENAME)

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""
        return _secure_object_marker(_ASSETS_NAMESPACE, "assets-ledger.lock")

    def load(self) -> AssetsLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted :class:`AssetsLedgerDocument`.

        Raises:
            AssetRecordError: When the envelope exists but cannot be loaded or decrypted.
        """
        try:
            record = self._objects.load(
                _ASSETS_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_ASSETS_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return AssetsLedgerDocument()
            return AssetsLedgerDocument.model_validate_json(record.payload.decode(UTF_8_ENCODING))
        except (OSError, AeatError) as exc:
            _log.debug(
                "asset ledger load failed",
                extra={
                    "namespace": _ASSETS_NAMESPACE,
                    "object_key": self._object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise AssetRecordError(
                f"unable to load asset ledger: {self._object_key}",
                context={"namespace": _ASSETS_NAMESPACE, "object_key": self._object_key},
                translated_message="adapters.persistence.profile.assets.errors.load_asset_ledger_failed",
            ) from exc

    def save(self, document: AssetsLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        Args:
            document: Ledger document to encrypt and write.
        """
        self._save_unlocked(document)
        _log.info("saved %d asset records to secure object %s", len(document.assets), self._object_key)

    def add(self, asset: AssetRecord) -> AssetsLedgerDocument:
        """Atomically add ``asset`` and refuse duplicate identifiers.

        Args:
            asset: Asset record to insert.

        Returns:
            The :class:`AssetsLedgerDocument` including the new asset.

        Raises:
            AssetRecordError: When an asset with the same identifier already exists.
        """
        current = self._load_unlocked()
        if any(existing.identifier == asset.identifier for existing in current.assets):
            raise AssetRecordError(
                f"asset {asset.identifier!r} already exists",
                context={"asset_id": asset.identifier},
                suggestion=None,
                translated_message="adapters.persistence.profile.assets.errors.asset_already_exists",
            )
        updated = AssetsLedgerDocument(assets=(*current.assets, asset))
        self._save_unlocked(updated)
        return updated

    def _load_unlocked(self) -> AssetsLedgerDocument:
        return self.load()

    def _save_unlocked(self, document: AssetsLedgerDocument) -> None:
        self._objects.save(
            namespace=_ASSETS_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_ASSETS_SECURE_OBJECT_VERSION,
            written_at=now(),
            payload=document.model_dump_json().encode(UTF_8_ENCODING),
        )

    @property
    def _object_key(self) -> str:
        return _ASSETS_OBJECT_KEY


class AmortizacionLedgerRepository:
    """Governed repository for the encrypted amortizacion ledger.

    Mirrors :class:`AssetsLedgerRepository` for amortizacion entries; the
    payload type is :class:`aeat.domain.contribuyente.assets.AmortizacionLedger`.
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Initialise the repository, defaulting to the active-bucket secure object store."""
        self._objects = objects if objects is not None else secure_object_repository_for_active_bucket()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return _secure_object_marker(_AMORTIZACION_NAMESPACE, ASSETS_AMORTIZATION_LEDGER_FILENAME)

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""
        return _secure_object_marker(_AMORTIZACION_NAMESPACE, "assets-amortization-ledger.lock")

    def load(self) -> AmortizacionLedger:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted :class:`AmortizacionLedger`.

        Raises:
            AssetRecordError: When the envelope exists but cannot be loaded or decrypted.
        """
        try:
            record = self._objects.load(
                _AMORTIZACION_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_AMORTIZACION_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return AmortizacionLedger()
            return AmortizacionLedger.model_validate_json(record.payload.decode(UTF_8_ENCODING))
        except (OSError, AeatError) as exc:
            _log.debug(
                "asset amortizacion ledger load failed",
                extra={
                    "namespace": _AMORTIZACION_NAMESPACE,
                    "object_key": self._object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise AssetRecordError(
                f"unable to load amortizacion ledger: {self._object_key}",
                context={"namespace": _AMORTIZACION_NAMESPACE, "object_key": self._object_key},
                translated_message="adapters.persistence.profile.assets.errors.load_amortizacion_ledger_failed",
            ) from exc

    def save(self, ledger: AmortizacionLedger) -> None:
        """Persist ``ledger`` as FINANCIAL-class ciphertext.

        Args:
            ledger: Amortizacion ledger to encrypt and write.
        """
        self._save_unlocked(ledger)
        _log.info("saved amortizacion ledger to secure object %s", self._object_key)

    def _load_unlocked(self) -> AmortizacionLedger:
        return self.load()

    def _save_unlocked(self, ledger: AmortizacionLedger) -> None:
        self._objects.save(
            namespace=_AMORTIZACION_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_AMORTIZACION_SECURE_OBJECT_VERSION,
            written_at=now(),
            payload=ledger.model_dump_json().encode(UTF_8_ENCODING),
        )

    @property
    def _object_key(self) -> str:
        return _AMORTIZACION_OBJECT_KEY


__all__ = [
    "AmortizacionLedgerRepository",
    "AssetsLedgerRepository",
    "add_asset",
    "load_amortizacion_ledger",
    "load_assets",
    "save_amortizacion_ledger",
    "save_assets",
]

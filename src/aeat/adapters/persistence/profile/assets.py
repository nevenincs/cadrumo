"""Encrypted SQL persistence for actividad economica asset and amortizacion ledgers.

:class:`aeat.domain.profile.assets.AssetRecord` and
:class:`aeat.domain.profile.assets.AmortizacionLedger` payloads are stored
as FINANCIAL-class secure objects in the primary database.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors import AeatError
from ....core.logging import get_logger
from ....domain.profile.assets import (
    AmortizacionLedger,
    AssetRecord,
    AssetsLedgerDocument,
)
from ....domain.profile.errors import AssetRecordError
from ..storage import SensitivityClass
from ..storage.sql import SecureObjectRepository

_log = get_logger(__name__)

ASSETS_LEDGER_FILENAME = "assets-ledger.secure-object"
ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortization-ledger.secure-object"
_SECURE_OBJECT_VERSION = 1
_ASSETS_NAMESPACE = "aeat.persistence.profile.assets"
_AMORTIZACION_NAMESPACE = "aeat.persistence.profile.assets.amortization"
_LEDGER_OBJECT_KEY = "default"


def load_assets() -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger.

    Returns:
        Tuple of persisted asset records, empty when the ledger is absent.
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
        The updated ledger document including the newly inserted asset.

    Raises:
        :exc:`aeat.domain.profile.errors.AssetRecordError`: When ``asset.identifier``
            is already present in the ledger.
    """

    return AssetsLedgerRepository().add(asset)


def load_amortizacion_ledger() -> AmortizacionLedger:
    """Load the amortizacion ledger, returning an empty ledger when absent.

    Returns:
        Persisted amortizacion ledger or an empty one when no envelope exists.
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

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""

        return Path("db://secure_objects") / _ASSETS_NAMESPACE / ASSETS_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""

        return Path("db://secure_objects") / _ASSETS_NAMESPACE / "assets-ledger.lock"

    def load(self) -> AssetsLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted assets ledger document.

        Raises:
            :exc:`aeat.domain.profile.errors.AssetRecordError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        try:
            record = self._objects.load(
                _ASSETS_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return AssetsLedgerDocument()
            return AssetsLedgerDocument.model_validate_json(record.payload.decode("utf-8"))
        except (OSError, AeatError) as exc:
            raise AssetRecordError(f"unable to load asset ledger: {self._object_key}") from exc

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
            The ledger document including the new asset.

        Raises:
            :exc:`aeat.domain.profile.errors.AssetRecordError`: When an asset
                with the same :attr:`AssetRecord.identifier` already exists.
        """

        current = self._load_unlocked()
        if any(existing.identifier == asset.identifier for existing in current.assets):
            raise AssetRecordError(
                f"asset {asset.identifier!r} already exists",
                context={"asset_id": asset.identifier},
                suggestion=None,
            )
        updated = AssetsLedgerDocument(assets=(*current.assets, asset))
        self._save_unlocked(updated)
        return updated

    def _load_unlocked(self) -> AssetsLedgerDocument:
        return self.load()

    def _save_unlocked(self, document: AssetsLedgerDocument) -> None:
        from datetime import UTC, datetime

        self._objects.save(
            namespace=_ASSETS_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_SECURE_OBJECT_VERSION,
            written_at=datetime.now(UTC),
            payload=document.model_dump_json().encode("utf-8"),
        )

    @property
    def _object_key(self) -> str:
        return _LEDGER_OBJECT_KEY


class AmortizacionLedgerRepository:
    """Governed repository for the encrypted amortizacion ledger.

    Mirrors :class:`AssetsLedgerRepository` for amortizacion entries; the
    payload type is :class:`aeat.domain.profile.assets.AmortizacionLedger`.
    """

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""

        return Path("db://secure_objects") / _AMORTIZACION_NAMESPACE / ASSETS_AMORTIZATION_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""

        return Path("db://secure_objects") / _AMORTIZACION_NAMESPACE / "assets-amortization-ledger.lock"

    def load(self) -> AmortizacionLedger:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted amortizacion ledger.

        Raises:
            :exc:`aeat.domain.profile.errors.AssetRecordError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        try:
            record = self._objects.load(
                _AMORTIZACION_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return AmortizacionLedger()
            return AmortizacionLedger.model_validate_json(record.payload.decode("utf-8"))
        except (OSError, AeatError) as exc:
            raise AssetRecordError(f"unable to load amortizacion ledger: {self._object_key}") from exc

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
        from datetime import UTC, datetime

        self._objects.save(
            namespace=_AMORTIZACION_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_SECURE_OBJECT_VERSION,
            written_at=datetime.now(UTC),
            payload=ledger.model_dump_json().encode("utf-8"),
        )

    @property
    def _object_key(self) -> str:
        return _LEDGER_OBJECT_KEY


__all__ = [
    "AmortizacionLedgerRepository",
    "AssetsLedgerRepository",
    "add_asset",
    "load_amortizacion_ledger",
    "load_assets",
    "save_amortizacion_ledger",
    "save_assets",
]

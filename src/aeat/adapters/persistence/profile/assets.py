"""Encrypted persistence for actividad economica asset and amortization ledgers.

Wraps :mod:`aeat.adapters.persistence.storage`'s envelope, master-key, and
file-locking primitives to persist :class:`aeat.domain.profile.assets.AssetRecord`
and :class:`aeat.domain.profile.assets.AmortizationLedger` payloads as
FINANCIAL-class ciphertext. Module-level convenience functions wrap the two
repository classes for common one-shot operations.

Attributes:
    ASSETS_LEDGER_FILENAME: Filename used inside the storage directory for the
        encrypted assets envelope.
    ASSETS_AMORTIZATION_LEDGER_FILENAME: Filename used inside the storage
        directory for the encrypted amortization envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ....core.config import load_settings
from ....core.errors import AeatError
from ....core.logging import get_logger
from ....domain.profile.assets import (
    AmortizationLedger,
    AmortizationRecordResult,
    AssetRecord,
    AssetsLedgerDocument,
    _flatten_entries,
    _nested_entries,
    compute_amortization_for_year,
)
from ....domain.profile.errors import AssetRecordError
from ..storage import Envelope, SensitivityClass, exclusive_file_lock, load_encrypted_envelope, save_encrypted_envelope
from ..storage.crypto._encrypted_columns import _resolve_master_key_provider

_log = get_logger(__name__)

ASSETS_LEDGER_FILENAME = "assets-ledger.envelope.json"
ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortization-ledger.envelope.json"
_ENVELOPE_VERSION = 1
_HKDF_CONTEXT_ASSETS = b"aeat.domain.profile.assets.ledger.v1"
_HKDF_CONTEXT_AMORTIZATION = b"aeat.domain.profile.assets.amortization-ledger.v1"


def default_storage_dir() -> Path:
    """Return the configured governed ledger storage directory.

    Returns:
        Filesystem path resolved from
        :attr:`aeat.core.config.Settings.aeat_ledgers_dir`.
    """

    return Path(load_settings().aeat_ledgers_dir)


def load_assets(*, storage_dir: Path | None = None) -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger.

    Args:
        storage_dir: Override for the ledger storage directory; defaults to
            :func:`default_storage_dir`.

    Returns:
        Tuple of persisted asset records, empty when the ledger is absent.
    """

    return AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir()).load().assets


def save_assets(assets: tuple[AssetRecord, ...], *, storage_dir: Path | None = None) -> Path:
    """Persist ``assets`` as a governed FINANCIAL-class encrypted envelope.

    Args:
        assets: Asset records to persist.
        storage_dir: Override for the ledger storage directory.

    Returns:
        Path to the encrypted envelope file that was written.
    """

    repository = AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(AssetsLedgerDocument(assets=assets))
    return repository.envelope_path


def add_asset(asset: AssetRecord, *, storage_dir: Path | None = None) -> AssetsLedgerDocument:
    """Atomically add ``asset`` to the encrypted asset ledger.

    Args:
        asset: Asset record to insert.
        storage_dir: Override for the ledger storage directory.

    Returns:
        The updated ledger document including the newly inserted asset.

    Raises:
        :exc:`aeat.domain.profile.errors.AssetRecordError`: When ``asset.identifier``
            is already present in the ledger.
    """

    return AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir()).add(asset)


def load_amortization_ledger(*, storage_dir: Path | None = None) -> AmortizationLedger:
    """Load the amortization ledger, returning an empty ledger when absent.

    Args:
        storage_dir: Override for the ledger storage directory.

    Returns:
        Persisted amortization ledger or an empty one when no envelope exists.
    """

    return AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).load()


def save_amortization_ledger(ledger: AmortizationLedger, *, storage_dir: Path | None = None) -> Path:
    """Persist ``ledger`` as a governed FINANCIAL-class encrypted envelope.

    Args:
        ledger: Amortization ledger to persist.
        storage_dir: Override for the ledger storage directory.

    Returns:
        Path to the encrypted envelope file that was written.
    """

    repository = AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(ledger)
    return repository.envelope_path


def record_amortization(asset: AssetRecord, year: int, *, storage_dir: Path | None = None) -> AmortizationLedger:
    """Compute and record amortization for one asset and tax year.

    Idempotent: if an entry for ``(asset.identifier, year)`` already exists,
    the existing amount is returned unchanged.

    Args:
        asset: Asset whose amortization is being recorded.
        year: Tax year (e.g. ``2025``).
        storage_dir: Override for the ledger storage directory.

    Returns:
        The amortization ledger as it stands after the operation.
    """

    return AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).record(asset, year).ledger


class AssetsLedgerRepository:
    """Governed repository for the encrypted assets ledger.

    Each method takes an exclusive file lock on :attr:`lock_target` for the
    duration of the read-modify-write cycle so concurrent processes cannot
    corrupt the ledger envelope.
    """

    def __init__(self, *, store_dir: Path) -> None:
        """Initialize the repository.

        Args:
            store_dir: Directory in which the encrypted envelope and lock
                sidecar live.
        """
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Path to the canonical encrypted envelope file."""

        return self._store_dir / ASSETS_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Path to the canonical exclusive-lock sidecar file."""

        return self._store_dir / "assets-ledger.lock"

    def load(self) -> AssetsLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted assets ledger document.

        Raises:
            :exc:`aeat.domain.profile.errors.AssetRecordError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        if not self.envelope_path.exists():
            return AssetsLedgerDocument()
        try:
            envelope = load_encrypted_envelope(
                self.envelope_path,
                Envelope[AssetsLedgerDocument],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_ASSETS,
                max_supported_version=_ENVELOPE_VERSION,
            )
            return envelope.payload
        except (OSError, AeatError) as exc:
            raise AssetRecordError(f"unable to load asset ledger: {self.envelope_path}") from exc

    def save(self, document: AssetsLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        Args:
            document: Ledger document to encrypt and write.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            envelope = Envelope[AssetsLedgerDocument](
                schema_version=_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=document,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_ASSETS,
            )
        _log.info("saved %d asset records to %s", len(document.assets), self.envelope_path)

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

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            current = self._load_unlocked()
            if any(existing.identifier == asset.identifier for existing in current.assets):
                raise AssetRecordError(
                    f"asset {asset.identifier!r} already exists",
                    context={"asset_id": asset.identifier},
                    suggestion=f"aeat data ledgers assets show {asset.identifier}",
                )
            updated = AssetsLedgerDocument(assets=(*current.assets, asset))
            self._save_unlocked(updated)
            return updated

    def _load_unlocked(self) -> AssetsLedgerDocument:
        if not self.envelope_path.exists():
            return AssetsLedgerDocument()
        envelope = load_encrypted_envelope(
            self.envelope_path,
            Envelope[AssetsLedgerDocument],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_ASSETS,
            max_supported_version=_ENVELOPE_VERSION,
        )
        return envelope.payload

    def _save_unlocked(self, document: AssetsLedgerDocument) -> None:
        envelope = Envelope[AssetsLedgerDocument](
            schema_version=_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=document,
        )
        save_encrypted_envelope(
            envelope,
            self.envelope_path,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_ASSETS,
        )


class AmortizationLedgerRepository:
    """Governed repository for the encrypted amortization ledger.

    Mirrors :class:`AssetsLedgerRepository` for amortization entries; the
    payload type is :class:`aeat.domain.profile.assets.AmortizationLedger`.
    """

    def __init__(self, *, store_dir: Path) -> None:
        """Initialize the repository.

        Args:
            store_dir: Directory in which the encrypted envelope and lock
                sidecar live.
        """
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Path to the canonical encrypted envelope file."""

        return self._store_dir / ASSETS_AMORTIZATION_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Path to the canonical exclusive-lock sidecar file."""

        return self._store_dir / "assets-amortization-ledger.lock"

    def load(self) -> AmortizationLedger:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted amortization ledger.

        Raises:
            :exc:`aeat.domain.profile.errors.AssetRecordError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        if not self.envelope_path.exists():
            return AmortizationLedger()
        try:
            envelope = load_encrypted_envelope(
                self.envelope_path,
                Envelope[AmortizationLedger],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_AMORTIZATION,
                max_supported_version=_ENVELOPE_VERSION,
            )
            return envelope.payload
        except (OSError, AeatError) as exc:
            raise AssetRecordError(f"unable to load amortization ledger: {self.envelope_path}") from exc

    def save(self, ledger: AmortizationLedger) -> None:
        """Persist ``ledger`` as FINANCIAL-class ciphertext.

        Args:
            ledger: Amortization ledger to encrypt and write.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            envelope = Envelope[AmortizationLedger](
                schema_version=_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=ledger,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_AMORTIZATION,
            )
        _log.info("saved amortization ledger to %s", self.envelope_path)

    def record(self, asset: AssetRecord, year: int) -> AmortizationRecordResult:
        """Atomically compute and record amortization for one asset and year.

        Returns the prior amount unchanged when an entry for
        ``(asset.identifier, year)`` already exists, with
        :attr:`aeat.domain.profile.assets.AmortizationRecordResult.stored`
        set to ``False``.

        Args:
            asset: Asset whose amortization is being recorded.
            year: Tax year.

        Returns:
            Result carrying the resulting ledger, the recorded amount, and a
            ``stored`` flag.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            current = self._load_unlocked()
            by_asset = _nested_entries(current)
            by_year = by_asset.setdefault(asset.identifier, {})
            if year in by_year:
                return AmortizationRecordResult(ledger=current, amount=by_year[year], stored=False)
            amount = compute_amortization_for_year(asset, year, current)
            by_year[year] = amount
            updated = AmortizationLedger(entries=_flatten_entries(by_asset))
            self._save_unlocked(updated)
            return AmortizationRecordResult(ledger=updated, amount=amount, stored=True)

    def _load_unlocked(self) -> AmortizationLedger:
        if not self.envelope_path.exists():
            return AmortizationLedger()
        envelope = load_encrypted_envelope(
            self.envelope_path,
            Envelope[AmortizationLedger],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_AMORTIZATION,
            max_supported_version=_ENVELOPE_VERSION,
        )
        return envelope.payload

    def _save_unlocked(self, ledger: AmortizationLedger) -> None:
        envelope = Envelope[AmortizationLedger](
            schema_version=_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=ledger,
        )
        save_encrypted_envelope(
            envelope,
            self.envelope_path,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_AMORTIZATION,
        )


__all__ = [
    "AmortizationLedgerRepository",
    "AssetsLedgerRepository",
    "add_asset",
    "default_storage_dir",
    "load_amortization_ledger",
    "load_assets",
    "record_amortization",
    "save_amortization_ledger",
    "save_assets",
]

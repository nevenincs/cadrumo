"""Encrypted persistence for actividad economica asset ledgers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ....core.config import load_settings
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
    """Return the configured governed ledger storage directory."""

    return Path(load_settings().aeat_ledgers_dir)


def load_assets(*, storage_dir: Path | None = None) -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger."""

    return AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir()).load().assets


def save_assets(assets: tuple[AssetRecord, ...], *, storage_dir: Path | None = None) -> Path:
    """Persist asset records as a governed encrypted envelope."""

    repository = AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(AssetsLedgerDocument(assets=assets))
    return repository.envelope_path


def add_asset(asset: AssetRecord, *, storage_dir: Path | None = None) -> AssetsLedgerDocument:
    """Atomically add ``asset`` to the encrypted asset ledger."""

    return AssetsLedgerRepository(store_dir=storage_dir or default_storage_dir()).add(asset)


def load_amortization_ledger(*, storage_dir: Path | None = None) -> AmortizationLedger:
    """Load the amortization ledger, returning an empty ledger when absent."""

    return AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).load()


def save_amortization_ledger(ledger: AmortizationLedger, *, storage_dir: Path | None = None) -> Path:
    """Persist the amortization ledger as a governed encrypted envelope."""

    repository = AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(ledger)
    return repository.envelope_path


def record_amortization(asset: AssetRecord, year: int, *, storage_dir: Path | None = None) -> AmortizationLedger:
    """Compute and record amortization for one asset/year."""

    return AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).record(asset, year).ledger


class AssetsLedgerRepository:
    """Governed repository for the encrypted assets ledger."""

    def __init__(self, *, store_dir: Path) -> None:
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Return the canonical encrypted envelope path."""

        return self._store_dir / ASSETS_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock sidecar path."""

        return self._store_dir / "assets-ledger.lock"

    def load(self) -> AssetsLedgerDocument:
        """Load the ledger, returning an empty document when absent."""

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
        except Exception as exc:
            raise AssetRecordError(f"unable to load asset ledger: {self.envelope_path}") from exc

    def save(self, document: AssetsLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext."""

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
        """Atomically add ``asset`` and refuse duplicate identifiers."""

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
    """Governed repository for the encrypted amortization ledger."""

    def __init__(self, *, store_dir: Path) -> None:
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Return the canonical encrypted envelope path."""

        return self._store_dir / ASSETS_AMORTIZATION_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock sidecar path."""

        return self._store_dir / "assets-amortization-ledger.lock"

    def load(self) -> AmortizationLedger:
        """Load the ledger, returning an empty document when absent."""

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
        except Exception as exc:
            raise AssetRecordError(f"unable to load amortization ledger: {self.envelope_path}") from exc

    def save(self, ledger: AmortizationLedger) -> None:
        """Persist ``ledger`` as FINANCIAL-class ciphertext."""

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
        """Atomically compute and record amortization for ``asset`` and ``year``."""

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

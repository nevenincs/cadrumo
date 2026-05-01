"""Asset ledger for actividad economica amortization tracking."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core.logging import get_logger
from ...formulas import LIS_ART_12_LINEAL_TABLE, AssetClass
from ..errors import AssetRecordError, BasisCapExceededError

_log = get_logger(__name__)

ASSETS_LEDGER_FILENAME = "assets-ledger.envelope.json"
ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortization-ledger.envelope.json"
SCHEMA_VERSION = "1"
_ENVELOPE_VERSION = 1
_HKDF_CONTEXT_ASSETS = b"aeat.domain.profile.assets.ledger.v1"
_HKDF_CONTEXT_AMORTIZATION = b"aeat.domain.profile.assets.amortization-ledger.v1"
_CENT = Decimal("0.01")
_ONE = Decimal("1")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


class LibertadAmortizacionElection(BaseModel):
    """Opt-in election for LIS art. 12 accelerated amortization cases."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    enabled: bool = False
    legal_basis: str | None = None
    amount_limit: Decimal | None = Field(default=None, gt=Decimal("0"))


class AssetRecord(BaseModel):
    """A depreciable asset affected to an economic activity."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    asset_class: AssetClass
    acquisition_date: date
    cost_basis: Decimal = Field(gt=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, gt=Decimal("0"))
    vat_rate: Decimal = Field(default=Decimal("21.00"), ge=Decimal("0"), le=Decimal("100"))
    vat_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_vat_ratio: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"), le=Decimal("1"))
    gross_total: Decimal | None = Field(default=None, gt=Decimal("0"))
    useful_life_years: int | None = Field(default=None, gt=0)
    libertad_amortizacion: LibertadAmortizacionElection = Field(default_factory=LibertadAmortizacionElection)
    actividad_id: str | None = None
    allocation_ratio: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"), le=Decimal("1"))
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AssetRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_vat_decomposition(self) -> AssetRecord:
        base = self.taxable_base or self.cost_basis
        computed_vat = _quantize(base * self.vat_rate / _HUNDRED)
        if self.vat_amount is not None and self.vat_amount != computed_vat:
            raise ValueError("vat_amount must equal taxable_base * vat_rate")
        computed_gross = _quantize(base + computed_vat)
        if self.gross_total is not None and self.gross_total != computed_gross:
            raise ValueError("gross_total must equal taxable_base + vat_amount")
        if self.taxable_base is not None:
            non_deductible_vat = computed_vat * (_ONE - self.deductible_vat_ratio)
            expected_basis = _quantize(self.taxable_base + non_deductible_vat)
            if self.cost_basis != expected_basis:
                raise ValueError("cost_basis must equal taxable_base plus non-deductible VAT")
        return self

    @property
    def resolved_taxable_base(self) -> Decimal:
        """Return the invoice taxable base used to derive the asset basis."""

        return self.taxable_base or self.cost_basis

    @property
    def resolved_vat_amount(self) -> Decimal:
        """Return the invoice VAT amount."""

        return self.vat_amount or _quantize(self.resolved_taxable_base * self.vat_rate / _HUNDRED)

    @property
    def resolved_gross_total(self) -> Decimal:
        """Return the gross invoice total."""

        return self.gross_total or _quantize(self.resolved_taxable_base + self.resolved_vat_amount)


class AmortizationEntry(BaseModel):
    """One immutable amortization amount for an asset/year."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    amount: Decimal = Field(ge=Decimal("0"))


class AmortizationLedger(BaseModel):
    """Per-asset yearly amortization already recorded."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    entries: tuple[AmortizationEntry, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AmortizationLedger schema_version {value!r}")
        return value


class AmortizationRecordResult(BaseModel):
    """Result of an atomic amortization record operation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger: AmortizationLedger
    amount: Decimal
    stored: bool


class AssetsLedgerDocument(BaseModel):
    """JSON document containing the asset ledger."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    assets: tuple[AssetRecord, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AssetsLedgerDocument schema_version {value!r}")
        return value


def default_storage_dir() -> Path:
    """Return the configured governed ledger storage directory."""

    from ....core.config import load_settings

    return Path(load_settings().aeat_ledgers_dir)


def load_assets(*, storage_dir: Path | None = None) -> tuple[AssetRecord, ...]:
    """Load persisted asset records from the encrypted ledger.

    Args:
        storage_dir: Optional directory override for tests or import flows.

    Returns:
        Tuple of asset records. Missing files return an empty tuple.
    """

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


def compute_amortization_for_year(asset: AssetRecord, year: int, ledger: AmortizationLedger) -> Decimal:
    """Compute allowable amortization for one asset and year.

    Args:
        asset: Asset to compute.
        year: Calendar year being filed.
        ledger: Existing recorded amortization.

    Returns:
        Allowable amortization for the year, capped at remaining basis.

    Raises:
        BasisCapExceededError: If an existing ledger already exceeds basis.
    """

    if year < asset.acquisition_date.year:
        return _ZERO
    cumulative = _cumulative_for_asset(ledger, asset.identifier, up_to_year=year - 1)
    if cumulative > asset.cost_basis:
        raise BasisCapExceededError(
            f"asset {asset.identifier!r} already exceeds its cost basis",
            context={
                "asset_id": asset.identifier,
                "cost_basis": str(asset.cost_basis),
                "cumulative": str(cumulative),
            },
        )
    remaining = asset.cost_basis - cumulative
    if remaining <= _ZERO:
        return _ZERO
    if asset.libertad_amortizacion.enabled:
        limit = asset.libertad_amortizacion.amount_limit or remaining
        return _quantize(min(limit, remaining))
    annual = asset.cost_basis * _annual_rate(asset)
    prorated = annual * Decimal(_days_used(asset, year)) / Decimal("365")
    return _quantize(min(prorated, remaining))


def record_amortization(
    asset: AssetRecord,
    year: int,
    *,
    storage_dir: Path | None = None,
    ledger: AmortizationLedger | None = None,
) -> AmortizationLedger:
    """Compute and record amortization for one asset/year."""

    if ledger is not None:
        by_asset = _nested_entries(ledger)
        by_year = by_asset.setdefault(asset.identifier, {})
        if year in by_year:
            save_amortization_ledger(ledger, storage_dir=storage_dir)
            return ledger
        amount = compute_amortization_for_year(asset, year, ledger)
        by_year[year] = amount
        updated = AmortizationLedger(entries=_flatten_entries(by_asset))
        save_amortization_ledger(updated, storage_dir=storage_dir)
        return updated
    return AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).record(asset, year).ledger


def compute_anexo_d_amortization_aggregate(
    year: int,
    *,
    assets: tuple[AssetRecord, ...] | None = None,
    ledger: AmortizationLedger | None = None,
    actividad_id: str | None = None,
    storage_dir: Path | None = None,
) -> Decimal:
    """Compute Anexo D normal casilla `0173` from assets."""

    resolved_assets = assets if assets is not None else load_assets(storage_dir=storage_dir)
    resolved_ledger = ledger if ledger is not None else load_amortization_ledger(storage_dir=storage_dir)
    total = _ZERO
    for asset in resolved_assets:
        if actividad_id is not None and asset.actividad_id not in {None, actividad_id}:
            continue
        amount = compute_amortization_for_year(asset, year, resolved_ledger)
        total += amount * asset.allocation_ratio
    return _quantize(total)


def _assets_path(storage_dir: Path | None) -> Path:
    return (storage_dir or default_storage_dir()) / ASSETS_LEDGER_FILENAME


def _amortization_path(storage_dir: Path | None) -> Path:
    return (storage_dir or default_storage_dir()) / ASSETS_AMORTIZATION_LEDGER_FILENAME


def _annual_rate(asset: AssetRecord) -> Decimal:
    table_row = _table_row_for(asset.asset_class)
    if asset.useful_life_years is not None:
        rate = _ONE / Decimal(asset.useful_life_years)
        max_rate = table_row.coef_max_pct / _HUNDRED
        if rate > max_rate:
            raise AssetRecordError(
                "useful_life_years would exceed the LIS art. 12.1.a maximum coefficient",
                context={
                    "asset_id": asset.identifier,
                    "asset_class": asset.asset_class.value,
                    "useful_life_years": str(asset.useful_life_years),
                    "max_rate": str(max_rate),
                },
            )
        if asset.useful_life_years > table_row.period_max_years:
            raise AssetRecordError(
                "useful_life_years would exceed the LIS art. 12.1.a maximum period",
                context={
                    "asset_id": asset.identifier,
                    "asset_class": asset.asset_class.value,
                    "useful_life_years": str(asset.useful_life_years),
                    "period_max_years": str(table_row.period_max_years),
                },
            )
        return rate
    return table_row.coef_max_pct / _HUNDRED


def _table_row_for(asset_class: AssetClass):
    for category in LIS_ART_12_LINEAL_TABLE:
        if category.asset_class is asset_class:
            return category
    raise AssetRecordError(f"missing LIS art. 12.1.a coefficient for {asset_class.value}")


def _days_used(asset: AssetRecord, year: int) -> int:
    start = max(asset.acquisition_date, date(year, 1, 1))
    end = date(year, 12, 31)
    if start > end:
        return 0
    return (end - start).days + 1


def _cumulative_for_asset(ledger: AmortizationLedger, asset_id: str, *, up_to_year: int | None = None) -> Decimal:
    return sum(
        (
            entry.amount
            for entry in ledger.entries
            if entry.asset_id == asset_id and (up_to_year is None or entry.year <= up_to_year)
        ),
        _ZERO,
    )


def _nested_entries(ledger: AmortizationLedger) -> dict[str, dict[int, Decimal]]:
    nested: dict[str, dict[int, Decimal]] = {}
    for entry in ledger.entries:
        nested.setdefault(entry.asset_id, {})[entry.year] = entry.amount
    return nested


def _flatten_entries(entries: dict[str, dict[int, Decimal]]) -> tuple[AmortizationEntry, ...]:
    return tuple(
        AmortizationEntry(asset_id=asset_id, year=year, amount=amount)
        for asset_id, by_year in sorted(entries.items())
        for year, amount in sorted(by_year.items())
    )


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


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
            from ....adapters.persistence.storage import Envelope, SensitivityClass, load_encrypted_envelope
            from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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

        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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

        from ....adapters.persistence.storage import exclusive_file_lock

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
        from ....adapters.persistence.storage import Envelope, SensitivityClass, load_encrypted_envelope
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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
        from ....adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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
            from ....adapters.persistence.storage import Envelope, SensitivityClass, load_encrypted_envelope
            from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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

        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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

        from ....adapters.persistence.storage import exclusive_file_lock

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
        from ....adapters.persistence.storage import Envelope, SensitivityClass, load_encrypted_envelope
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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
        from ....adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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
    "AmortizationEntry",
    "AmortizationLedger",
    "AmortizationLedgerRepository",
    "AssetRecord",
    "LibertadAmortizacionElection",
    "add_asset",
    "compute_amortization_for_year",
    "compute_anexo_d_amortization_aggregate",
    "default_storage_dir",
    "load_amortization_ledger",
    "load_assets",
    "record_amortization",
    "save_assets",
]

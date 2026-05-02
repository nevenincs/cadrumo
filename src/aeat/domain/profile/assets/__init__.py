"""Asset ledger for actividad economica amortization tracking.

Provides the strict, frozen pydantic v2 records that back the
LIRPF / LIS art. 12 lineal amortization computation:
:class:`AssetRecord` (a depreciable asset affected to an economic
activity), :class:`AmortizationLedger` (the recorded per-asset / per-
year accruals), and :class:`LibertadAmortizacionElection` (the LIS
art. 12 accelerated-amortization opt-in). The annual computation is
exposed via :func:`compute_amortization_for_year` and aggregated for
Anexo D casilla ``0173`` by
:func:`compute_anexo_d_amortization_aggregate`.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...formulas import LIS_ART_12_LINEAL_TABLE, AssetClass
from ..errors import AssetRecordError, BasisCapExceededError

SCHEMA_VERSION = "1"
"""Forward-compatible schema version stamped onto every record in this module."""

_CENT = Decimal("0.01")
_ONE = Decimal("1")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


class LibertadAmortizacionElection(BaseModel):
    """Opt-in election for LIS art. 12 accelerated amortization cases.

    Attributes:
        enabled: Whether the asset opts into accelerated amortization.
        legal_basis: BOE provision the election leans on (free-text
            citation for audit).
        amount_limit: Optional ceiling on the accelerated amount per
            year. Must be strictly positive when set.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    enabled: bool = False
    legal_basis: str | None = None
    amount_limit: Decimal | None = Field(default=None, gt=Decimal("0"))


class AssetRecord(BaseModel):
    """A depreciable asset affected to an economic activity.

    Strict, frozen, no extra fields. Tracks both the invoice-level VAT
    decomposition (``taxable_base`` / ``vat_amount`` / ``gross_total``)
    and the derived ``cost_basis`` used as the depreciable basis. When
    only a fraction of input VAT is deductible, the non-deductible
    portion is rolled into ``cost_basis`` per LIS / LIRPF practice.

    Attributes:
        identifier: Stable natural key chosen by the operator.
        description: Free-text human description.
        asset_class: :class:`aeat.domain.formulas.AssetClass` slot driving the
            LIS art. 12.1.a coefficient lookup.
        acquisition_date: Date the asset was acquired.
        cost_basis: Depreciable basis. Strictly positive.
        taxable_base: Invoice taxable base (VAT-exclusive). When set,
            ``cost_basis`` must equal ``taxable_base + non-deductible
            VAT``.
        vat_rate: VAT percentage applied to the invoice (0-100).
        vat_amount: Optional explicit VAT amount; when set, must equal
            ``taxable_base * vat_rate / 100``.
        deductible_vat_ratio: Fraction of input VAT the contribuyente
            may deduct (0-1).
        gross_total: Optional explicit invoice total; when set, must
            equal ``taxable_base + vat_amount``.
        useful_life_years: Override for the LIS art. 12.1.a default
            coefficient. Must not exceed the table maximum coefficient
            or period for ``asset_class``.
        libertad_amortizacion: :class:`LibertadAmortizacionElection`.
        actividad_id: Optional activity identifier when the asset is
            allocated to a specific actividad.
        allocation_ratio: Fraction of the asset allocated to the
            activity (0-1).
        schema_version: Forward-compatible schema version. ``"1"``.
    """

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
        """Reject any schema_version other than the current :data:`SCHEMA_VERSION`."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AssetRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_vat_decomposition(self) -> AssetRecord:
        """Cross-check VAT decomposition against ``cost_basis``."""
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
        """Return the invoice taxable base, falling back to ``cost_basis``."""
        return self.taxable_base or self.cost_basis

    @property
    def resolved_vat_amount(self) -> Decimal:
        """Return the explicit VAT amount or derive it from the taxable base and rate."""
        return self.vat_amount or _quantize(self.resolved_taxable_base * self.vat_rate / _HUNDRED)

    @property
    def resolved_gross_total(self) -> Decimal:
        """Return the explicit gross total or derive it from base + VAT."""
        return self.gross_total or _quantize(self.resolved_taxable_base + self.resolved_vat_amount)


class AmortizationEntry(BaseModel):
    """One immutable amortization amount for an asset/year.

    Attributes:
        asset_id: Foreign key into :class:`AssetRecord` by identifier.
        year: Calendar year the entry covers.
        amount: Amortization amount (non-negative Decimal).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    amount: Decimal = Field(ge=Decimal("0"))


class AmortizationLedger(BaseModel):
    """Per-asset yearly amortization already recorded.

    Attributes:
        entries: Tuple of immutable :class:`AmortizationEntry` rows.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    entries: tuple[AmortizationEntry, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`SCHEMA_VERSION`."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AmortizationLedger schema_version {value!r}")
        return value


class AmortizationRecordResult(BaseModel):
    """Result of an atomic amortization record operation.

    Attributes:
        ledger: Resulting :class:`AmortizationLedger` after the write.
        amount: Amortization amount stored (or that would have been
            stored when ``stored`` is ``False``).
        stored: ``True`` when the entry was newly persisted.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger: AmortizationLedger
    amount: Decimal
    stored: bool


class AssetsLedgerDocument(BaseModel):
    """JSON document containing the asset ledger.

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        assets: Tuple of :class:`AssetRecord` rows.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    assets: tuple[AssetRecord, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`SCHEMA_VERSION`."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported AssetsLedgerDocument schema_version {value!r}")
        return value


def compute_amortization_for_year(asset: AssetRecord, year: int, ledger: AmortizationLedger) -> Decimal:
    """Compute allowable amortization for one asset and year.

    Applies LIS art. 12.1.a lineal coefficients via
    :data:`aeat.domain.formulas.LIS_ART_12_LINEAL_TABLE`, with a libertad-de-
    amortización fast-path when :attr:`AssetRecord.libertad_amortizacion`
    is enabled. Always quantises to euro-cents (half-up) and clamps
    the result at the remaining cost basis.

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


def compute_anexo_d_amortization_aggregate(
    year: int,
    *,
    assets: tuple[AssetRecord, ...] = (),
    ledger: AmortizationLedger | None = None,
    actividad_id: str | None = None,
) -> Decimal:
    """Compute Anexo D normal casilla ``0173`` from assets.

    Sums :func:`compute_amortization_for_year` across every asset
    (optionally filtered to ``actividad_id``), weighted by
    :attr:`AssetRecord.allocation_ratio`.

    Args:
        year: Calendar year being filed.
        assets: Asset records to aggregate.
        ledger: Existing :class:`AmortizationLedger`. Defaults to an
            empty ledger.
        actividad_id: When set, restricts the aggregate to assets
            allocated to that activity (or with no activity).

    Returns:
        Aggregate amortization for the year, quantised to cents.
    """
    resolved_ledger = ledger if ledger is not None else AmortizationLedger()
    total = _ZERO
    for asset in assets:
        if actividad_id is not None and asset.actividad_id not in {None, actividad_id}:
            continue
        amount = compute_amortization_for_year(asset, year, resolved_ledger)
        total += amount * asset.allocation_ratio
    return _quantize(total)


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


__all__ = [
    "AmortizationEntry",
    "AmortizationLedger",
    "AssetRecord",
    "LibertadAmortizacionElection",
    "compute_amortization_for_year",
    "compute_anexo_d_amortization_aggregate",
]

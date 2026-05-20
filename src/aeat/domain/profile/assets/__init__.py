"""Asset ledger records for actividad economica amortizacion tracking.

Provides the strict, frozen pydantic v2 records that back the
registry-backed amortizacion workflow:
:class:`AssetRecord` (a depreciable asset affected to an economic
activity), :class:`AmortizacionLedger` (the recorded per-asset / per-
year accruals), and :class:`LibertadAmortizacionElection`.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..errors import AssetValidationError

SCHEMA_VERSION = "1"
"""Forward-compatible schema version stamped onto every record in this module."""

_CENT = Decimal("0.01")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class AssetClass(StrEnum):
    """Asset category token retained for encrypted user-ledger records."""

    OBRA_CIVIL_GENERAL = "obra_civil.general"
    OBRA_CIVIL_PAVIMENTOS = "obra_civil.pavimentos"
    OBRA_CIVIL_INFRA_MINERAS = "obra_civil.infraestructuras_obras_mineras"
    CENTRALES_HIDRAULICAS = "centrales.hidraulicas"
    CENTRALES_NUCLEARES = "centrales.nucleares"
    CENTRALES_CARBON = "centrales.carbon"
    CENTRALES_RENOVABLES = "centrales.renovables"
    CENTRALES_OTRAS = "centrales.otras"
    EDIFICIOS_INDUSTRIALES = "edificios.industriales"
    EDIFICIOS_ESCOMBRERAS = "edificios.escombreras"
    EDIFICIOS_ALMACENES = "edificios.almacenes_depositos"
    EDIFICIOS_COMERCIALES = "edificios.comerciales_administrativos_servicios_viviendas"
    INSTALACIONES_SUBESTACIONES = "instalaciones.subestaciones_redes"
    INSTALACIONES_CABLES = "instalaciones.cables"
    INSTALACIONES_RESTO = "instalaciones.resto"
    MAQUINARIA_GENERAL = "maquinaria.general"
    MAQUINARIA_MEDICOS = "maquinaria.equipos_medicos"
    TRANSPORTE_LOCOMOTORAS = "transporte.locomotoras_vagones_traccion"
    TRANSPORTE_BUQUES_AERONAVES = "transporte.buques_aeronaves"
    TRANSPORTE_INTERNO = "transporte.interno"
    TRANSPORTE_EXTERNO = "transporte.externo"
    TRANSPORTE_AUTOCAMIONES = "transporte.autocamiones"
    MOBILIARIO_GENERAL = "mobiliario.general"
    MOBILIARIO_LENCERIA = "mobiliario.lenceria"
    MOBILIARIO_CRISTALERIA = "mobiliario.cristaleria"
    MOBILIARIO_UTILES = "mobiliario.utiles_herramientas"
    MOBILIARIO_MOLDES = "mobiliario.moldes_matrices_modelos"
    MOBILIARIO_OTROS = "mobiliario.otros_enseres"
    ELECTRONICA_GENERAL = "electronica.equipos_electronicos"
    ELECTRONICA_INFORMATICA = "electronica.equipos_tratamiento_informacion"
    ELECTRONICA_SOFTWARE = "electronica.sistemas_programas_informaticos"
    PRODUCCIONES_AUDIOVISUALES = "producciones.audiovisuales"
    OTROS_ELEMENTOS = "otros.elementos"


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
        asset_class: Asset class token. Legal coefficients are supplied by
            registry definitions, not this record module.
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
            raise AssetValidationError(f"unsupported AssetRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_vat_decomposition(self) -> AssetRecord:
        """Cross-check VAT decomposition against ``cost_basis``."""
        base = self.taxable_base or self.cost_basis
        computed_vat = _quantize(base * self.vat_rate / _HUNDRED)
        if self.vat_amount is not None and self.vat_amount != computed_vat:
            raise AssetValidationError("vat_amount must equal taxable_base * vat_rate")
        computed_gross = _quantize(base + computed_vat)
        if self.gross_total is not None and self.gross_total != computed_gross:
            raise AssetValidationError("gross_total must equal taxable_base + vat_amount")
        if self.taxable_base is not None:
            non_deductible_vat = computed_vat * (_ONE - self.deductible_vat_ratio)
            expected_basis = _quantize(self.taxable_base + non_deductible_vat)
            if self.cost_basis != expected_basis:
                raise AssetValidationError("cost_basis must equal taxable_base plus non-deductible VAT")
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


class AmortizacionEntry(BaseModel):
    """One immutable amortizacion amount for an asset/year.

    Attributes:
        asset_id: Foreign key into :class:`AssetRecord` by identifier.
        year: Calendar year the entry covers.
        amount: Amortizacion amount (non-negative Decimal).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    amount: Decimal = Field(ge=Decimal("0"))


class AmortizacionLedger(BaseModel):
    """Per-asset yearly amortizacion already recorded.

    Attributes:
        entries: Tuple of immutable :class:`AmortizacionEntry` rows.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    entries: tuple[AmortizacionEntry, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`SCHEMA_VERSION`."""
        if value != SCHEMA_VERSION:
            raise AssetValidationError(f"unsupported AmortizacionLedger schema_version {value!r}")
        return value


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
            raise AssetValidationError(f"unsupported AssetsLedgerDocument schema_version {value!r}")
        return value


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


__all__ = [
    "AmortizacionEntry",
    "AmortizacionLedger",
    "AssetClass",
    "AssetRecord",
    "LibertadAmortizacionElection",
]

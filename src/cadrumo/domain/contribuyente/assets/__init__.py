"""Asset ledger records for actividad economica amortizacion tracking.

Provides the strict, frozen pydantic v2 records that back the
registry-backed amortizacion workflow:
:class:`AssetRecord` (a depreciable asset affected to an economic
activity), :class:`AmortizacionLedger` (the recorded per-asset / per-
year accruals), and :class:`LibertadAmortizacionElection`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.errors.hierarchy import CadrumoError as _CadrumoError
from ....core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT as _DEFAULT_IVA_GENERAL_RATE_PCT
from ....core.money import round_to_cents as _quantize
from ....core.percentage import Percentage
from ....core.unit_proportion import UnitProportion


class AssetRecordError(_CadrumoError):
    """Raised when an asset record is structurally invalid."""


class AssetValidationError(AssetRecordError, ValueError):
    """Raised when an asset record fails Pydantic validation."""


ASSETS_SCHEMA_VERSION = "1"
"""Forward-compatible schema version stamped onto every record in this module."""

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

    model_config = _STRICT_FROZEN_CONFIG

    enabled: bool = False
    legal_basis: str | None = None
    amount_limit: Decimal | None = Field(default=None, gt=Decimal("0"))


class AssetRecord(BaseModel):
    """A depreciable asset affected to an economic activity.

    Strict, frozen, no extra fields. Tracks both the invoice-level IVA
    decomposition (``taxable_base`` / ``iva_amount`` / ``gross_total``)
    and the derived ``cost_basis`` used as the depreciable basis. When
    only a fraction of input IVA is deductible, the non-deductible
    portion is rolled into ``cost_basis`` per LIS / LIRPF practice.

    Attributes:
        identifier: Stable natural key chosen by the operator.
        description: Free-text human description.
        asset_class: Asset class token. Legal coefficients are supplied by
            registry definitions, not this record module.
        acquisition_date: Date the asset was acquired.
        cost_basis: Depreciable basis. Strictly positive.
        taxable_base: Invoice taxable base (IVA-exclusive). When set,
            ``cost_basis`` must equal ``taxable_base + non-deductible
            IVA``.
        iva_rate: IVA percentage applied to the invoice (0-100).
        iva_amount: Optional explicit IVA amount; when set, must equal
            ``taxable_base * iva_rate / 100``.
        deductible_iva_ratio: Fraction of input IVA the contribuyente
            may deduct (0-1).
        gross_total: Optional explicit invoice total; when set, must
            equal ``taxable_base + iva_amount``.
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

    model_config = _STRICT_FROZEN_CONFIG

    identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    asset_class: AssetClass
    acquisition_date: date
    cost_basis: Decimal = Field(gt=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, gt=Decimal("0"))
    iva_rate: Percentage = _DEFAULT_IVA_GENERAL_RATE_PCT
    iva_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_iva_ratio: UnitProportion = Decimal("1.00")
    gross_total: Decimal | None = Field(default=None, gt=Decimal("0"))
    useful_life_years: int | None = Field(default=None, gt=0)
    libertad_amortizacion: LibertadAmortizacionElection = Field(default_factory=LibertadAmortizacionElection)
    actividad_id: str | None = None
    allocation_ratio: UnitProportion = Decimal("1.00")
    schema_version: str = ASSETS_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`ASSETS_SCHEMA_VERSION`."""
        if value != ASSETS_SCHEMA_VERSION:
            raise AssetValidationError(f"unsupported AssetRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_iva_decomposition(self) -> AssetRecord:
        """Cross-check IVA decomposition against ``cost_basis``."""
        base = self.taxable_base or self.cost_basis
        computed_iva = _quantize(base * self.iva_rate / _HUNDRED)
        if self.iva_amount is not None and self.iva_amount != computed_iva:
            raise AssetValidationError("iva_amount must equal taxable_base * iva_rate")
        computed_gross = _quantize(base + computed_iva)
        if self.gross_total is not None and self.gross_total != computed_gross:
            raise AssetValidationError("gross_total must equal taxable_base + iva_amount")
        if self.taxable_base is not None:
            non_deductible_iva = computed_iva * (_ONE - self.deductible_iva_ratio)
            expected_basis = _quantize(self.taxable_base + non_deductible_iva)
            if self.cost_basis != expected_basis:
                raise AssetValidationError("cost_basis must equal taxable_base plus non-deductible IVA")
        return self

    @property
    def resolved_taxable_base(self) -> Decimal:
        """Return the invoice taxable base, falling back to ``cost_basis``."""
        return self.taxable_base or self.cost_basis

    @property
    def resolved_iva_amount(self) -> Decimal:
        """Return the explicit IVA amount or derive it from the taxable base and rate."""
        return self.iva_amount or _quantize(self.resolved_taxable_base * self.iva_rate / _HUNDRED)

    @property
    def resolved_gross_total(self) -> Decimal:
        """Return the explicit gross total or derive it from base + IVA."""
        return self.gross_total or _quantize(self.resolved_taxable_base + self.resolved_iva_amount)


class AmortizacionEntry(BaseModel):
    """One immutable amortizacion amount for an asset/year.

    Attributes:
        asset_id: Foreign key into :class:`AssetRecord` by identifier.
        year: Calendar year the entry covers.
        amount: Amortizacion amount (non-negative Decimal).
    """

    model_config = _STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    amount: Decimal = Field(ge=Decimal("0"))


class AmortizacionLedger(BaseModel):
    """Per-asset yearly amortizacion already recorded.

    Attributes:
        entries: Tuple of immutable :class:`AmortizacionEntry` rows.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    entries: tuple[AmortizacionEntry, ...] = ()
    schema_version: str = ASSETS_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`ASSETS_SCHEMA_VERSION`."""
        if value != ASSETS_SCHEMA_VERSION:
            raise AssetValidationError(f"unsupported AmortizacionLedger schema_version {value!r}")
        return value


class AssetsLedgerDocument(BaseModel):
    """JSON document containing the asset ledger.

    ``AssetRecord.identifier`` is the ledger's natural key: amortisation
    entries reference an asset by it, so two rows sharing one identifier leave
    later lookup and amortisation consumers without a canonical asset. The
    uniqueness invariant lives here, on the document, because the repository
    had two competing versions of it -- incremental ``add`` refused a repeated
    identifier while bulk ``save``/``save_assets`` accepted any document and
    wrote it straight through, so the same ledger enforced the rule on one
    write path and not the other.

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        assets: Tuple of :class:`AssetRecord` rows, each with a distinct
            ``identifier``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = ASSETS_SCHEMA_VERSION
    assets: tuple[AssetRecord, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`ASSETS_SCHEMA_VERSION`."""
        if value != ASSETS_SCHEMA_VERSION:
            raise AssetValidationError(f"unsupported AssetsLedgerDocument schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _reject_duplicate_identifiers(self) -> AssetsLedgerDocument:
        """Refuse a ledger carrying two assets under one identifier.

        Enforced on the document rather than at a write method so every path
        that can produce a ledger -- incremental insert, bulk replacement, and
        the read boundary -- answers the same way. Applying at the read
        boundary is deliberate: a stored ledger that already holds a duplicate
        has no canonical asset for that identifier, and surfacing it silently
        is what the repository used to do.
        """
        identifiers = [asset.identifier for asset in self.assets]
        duplicates = sorted({value for value in identifiers if identifiers.count(value) > 1})
        if duplicates:
            raise AssetValidationError(
                f"AssetsLedgerDocument carries duplicate asset identifiers: {', '.join(duplicates)}",
            )
        return self


__all__ = [
    "AmortizacionEntry",
    "AmortizacionLedger",
    "AssetClass",
    "AssetRecord",
    "AssetRecordError",
    "AssetValidationError",
    "LibertadAmortizacionElection",
]

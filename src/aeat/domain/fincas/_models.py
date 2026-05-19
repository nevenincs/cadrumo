"""Frozen-strict pydantic v2 records for the rental register.

Defines the persistent record types backing rental aggregate
calculation: :class:`RentalFinca` (urban inmueble metadata),
:class:`RentalContract` (per-tenant arrendamiento), :class:`RentalIncomeRecord`
(per-period gross-rent ledger), :class:`RentalExpense` (LIRPF
art. 23.1 deductible-category surface), and
:class:`RentalAmortizationLedgerEntry` (LIRPF art. 23.1.f 3 %
amortización cumulative ledger).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._enums import ExpenseCategory, UseType
from ._errors import RentalValidationError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _RentalRecord(BaseModel):
    """Shared base — frozen, strict, no extra fields."""

    model_config = _STRICT_FROZEN


class RentalFinca(_RentalRecord):
    """Public record for one row in ``rental_fincas``.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        identifier: Stable natural key chosen by the operator
            (e.g. ``"calle-mayor-12-3a"``).
        address: Free-text street address of the property. Stored
            encrypted at rest; round-trips as plain ``str`` here.
        valor_catastral_total: Catastro total value at the most
            recent ejercicio (suelo + construcción).
        valor_catastral_construccion: Catastro construction-only
            value at the most recent ejercicio.
        valor_catastral_revision_year: Year of the most recent
            revisión catastral, or ``None`` if pre-1994 / unknown.
            Drives the LIRPF art. 85 1,1 % vs 2 % imputación rate.
        coste_adquisicion: Acquisition cost of the whole property,
            net of taxes that did not enrich the seller.
        coste_adquisicion_construccion: Acquisition cost attributable
            to the construction component (cost * valor_catastral_
            construccion / valor_catastral_total). The depreciable
            basis cap for the LIRPF art. 23.1.f amortización 3 %
            ledger.
        acquisition_date: Date the contribuyente acquired the property.
        disposal_date: Date the contribuyente disposed of the
            property, or ``None`` if still held.
        use_type: Closed enum classifying the finca's use.
        is_stressed_area: Whether the property sits in a declared
            zona de mercado residencial tensionado at the resolver
            consultation date. Set by the operator at finca
            registration; future CCAA-driven enrichment supersedes
            this flag automatically.
        schema_version: Rental record schema version. ``"1"``.
    """

    id: int | None = Field(default=None, ge=1)
    identifier: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=1)
    valor_catastral_total: Decimal = Field(ge=Decimal("0"))
    valor_catastral_construccion: Decimal = Field(ge=Decimal("0"))
    valor_catastral_revision_year: int | None = Field(default=None, ge=1900, le=2100)
    coste_adquisicion: Decimal = Field(ge=Decimal("0"))
    coste_adquisicion_construccion: Decimal = Field(ge=Decimal("0"))
    acquisition_date: date
    disposal_date: date | None = None
    use_type: UseType
    is_stressed_area: bool = False
    schema_version: str = "1"

    @model_validator(mode="after")
    def _validate_ratios(self) -> RentalFinca:
        if self.valor_catastral_construccion > self.valor_catastral_total:
            raise RentalValidationError(
                "valor_catastral_construccion must not exceed valor_catastral_total",
            )
        if self.coste_adquisicion_construccion > self.coste_adquisicion:
            raise RentalValidationError(
                "coste_adquisicion_construccion must not exceed coste_adquisicion",
            )
        if self.disposal_date is not None and self.disposal_date < self.acquisition_date:
            raise RentalValidationError("disposal_date must not precede acquisition_date")
        return self


class RentalContract(_RentalRecord):
    """Public record for one row in ``rental_contracts``.

    Models the per-contract metadata required by the LIRPF art. 23.2
    tier resolver. The qualifying-share fraction for tier 70-b-1 is
    computed at resolver time from
    ``qualifying_co_tenant_count / tenant_count``.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        finca_id: Foreign key to :class:`RentalFinca`.
        contract_celebration_date: Date the contract was signed.
            Drives DT 38ª grandfathering (pre-26/05/2023) and the
            "Los requisitos señalados deberán cumplirse en el momento
            de celebrar el contrato" anchor.
        contract_termination_date: Date the contract terminated, or
            ``None`` if active.
        tenant_count: Total number of co-tenants on the contract.
        qualifying_co_tenant_count: Co-tenants meeting the tier
            70-b-1 age range. Drives the qualifying-share split.
        tenant_min_age: Minimum age across co-tenants at contract
            celebration. Optional; required only for tier 70-b-1
            evaluation.
        tenant_max_age: Maximum age across co-tenants at contract
            celebration. Optional; required only for tier 70-b-1
            evaluation.
        tenant_is_public_admin: Tenant is a Public Administration
            destining the dwelling to alquiler social per
            Ley 12/2023 disposición final segunda apartado uno
            letra b) ordinal 2.º.
        tenant_is_ley_49_2002_entity_with_social_use: Tenant is a
            Ley 49/2002 régimen-especial entity destining the
            dwelling to alquiler social or to vulnerability
            accommodation per Ley 19/2021 IMV.
        tenant_is_imv_beneficiary: Tenant is an IMV beneficiary
            housed via the dwelling.
        dwelling_in_public_program: Dwelling enrolled in a public
            housing program with a rent cap.
        prior_contract_last_rent: Last rent of the immediately prior
            contract on the same dwelling, after applying the prior
            contract's annual indexation. Required for tier 90-a
            evaluation.
        prior_contract_indexation: Annual indexation factor applied
            on the prior contract's last rent. Optional metadata
            (the indexed last rent is what the resolver compares).
        initial_rent: Initial monthly rent of the new contract.
        is_first_rental: Whether this contract is the dwelling's
            first ever rental contract. Tier 70-b-1 trigger.
        rehabilitation_finished_date: Date the most recent
            qualifying actuación de rehabilitación finished, per
            RIRPF art. 41.1. Drives tier 60-c evaluation.
        lau_17_6_compliant: Whether the contract complies with LAU
            art. 17.6 (rent cap for new contracts in declared
            zonas tensionadas where the landlord is a gran tenedor).
            ``False`` triggers ``FORFEIT_LAU_17_6``.
        schema_version: Rental record schema version. ``"1"``.
    """

    id: int | None = Field(default=None, ge=1)
    finca_id: int = Field(ge=1)
    contract_celebration_date: date
    contract_termination_date: date | None = None
    tenant_count: int = Field(ge=1)
    qualifying_co_tenant_count: int = Field(default=0, ge=0)
    tenant_min_age: int | None = Field(default=None, ge=0, le=150)
    tenant_max_age: int | None = Field(default=None, ge=0, le=150)
    tenant_is_public_admin: bool = False
    tenant_is_ley_49_2002_entity_with_social_use: bool = False
    tenant_is_imv_beneficiary: bool = False
    dwelling_in_public_program: bool = False
    prior_contract_last_rent: Decimal | None = Field(default=None, ge=Decimal("0"))
    prior_contract_indexation: Decimal | None = None
    initial_rent: Decimal = Field(ge=Decimal("0"))
    is_first_rental: bool = False
    rehabilitation_finished_date: date | None = None
    lau_17_6_compliant: bool = True
    schema_version: str = "1"

    @model_validator(mode="after")
    def _validate_invariants(self) -> RentalContract:
        if self.qualifying_co_tenant_count > self.tenant_count:
            raise RentalValidationError(
                "qualifying_co_tenant_count must not exceed tenant_count",
            )
        if (
            self.tenant_min_age is not None
            and self.tenant_max_age is not None
            and self.tenant_min_age > self.tenant_max_age
        ):
            raise RentalValidationError("tenant_min_age must not exceed tenant_max_age")
        if (
            self.contract_termination_date is not None
            and self.contract_termination_date < self.contract_celebration_date
        ):
            raise RentalValidationError(
                "contract_termination_date must not precede contract_celebration_date",
            )
        return self


class RentalIncomeRecord(_RentalRecord):
    """Public record for one row in ``rental_income_records``.

    Per-contract per-period gross-rent ledger. The aggregate layer
    sums ``gross_rent_received`` across active contracts in the
    period. ``dias_alquilados`` drives the amortización pro-rate.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        contract_id: Foreign key to :class:`RentalContract`.
        period_year: Ejercicio (e.g. ``2025``).
        gross_rent_received: Gross rent collected during the period.
        dias_alquilados: Days the dwelling was let during the period
            (0-366).
        schema_version: Rental record schema version. ``"1"``.
    """

    id: int | None = Field(default=None, ge=1)
    contract_id: int = Field(ge=1)
    period_year: int = Field(ge=1900, le=2100)
    gross_rent_received: Decimal = Field(ge=Decimal("0"))
    dias_alquilados: int = Field(ge=0, le=366)
    schema_version: str = "1"


class RentalExpense(_RentalRecord):
    """Public record for one row in ``rental_expenses``.

    Per-finca per-period categorised expense surface. Multiple rows
    may share ``(finca_id, period_year, category)`` — the aggregator
    sums them. The art. 23.1.a) cap (``FINANCIACION_INTERESES`` +
    ``CONSERVACION_REPARACION`` capped at ingresos) is applied at
    rollup time, not at the per-row boundary.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        finca_id: Foreign key to :class:`RentalFinca`.
        period_year: Ejercicio.
        category: Closed expense-category enum.
        amount: Gasto amount (positive Decimal).
        schema_version: Rental record schema version. ``"1"``.
    """

    id: int | None = Field(default=None, ge=1)
    finca_id: int = Field(ge=1)
    period_year: int = Field(ge=1900, le=2100)
    category: ExpenseCategory
    amount: Decimal = Field(ge=Decimal("0"))
    schema_version: str = "1"


class RentalAmortizationLedgerEntry(_RentalRecord):
    """Public record for one row in ``rental_amortization_ledger``.

    Per-finca per-period 3 % amortización accrual with cumulative-
    through-year tracking. Cumulative-through-year is the SUM of
    ``amortization_amount`` across all entries for the same finca
    with ``period_year <= self.period_year``. The cap rule
    (cumulative ≤ ``RentalFinca.coste_adquisicion_construccion``)
    is enforced by the ledger writer, not at the row level.

    Attributes:
        id: Surrogate primary key. ``None`` for records not yet persisted.
        finca_id: Foreign key to :class:`RentalFinca`.
        period_year: Ejercicio.
        dias_alquilados: Days the dwelling was let during the period
            (drives the pro-rate factor).
        basis_used: ``max(coste_adquisicion_construccion,
            valor_catastral_construccion)`` at the period — the
            depreciable basis the 3 % rate applied to.
        amortization_amount: ``basis_used * 0.03 * dias_alquilados / 365``,
            clamped down by the cap if cumulative would otherwise
            exceed ``coste_adquisicion_construccion``.
        cumulative_amortization_through_year: Sum of
            ``amortization_amount`` for this finca for periods
            ≤ ``period_year``.
        schema_version: Rental record schema version. ``"1"``.
    """

    id: int | None = Field(default=None, ge=1)
    finca_id: int = Field(ge=1)
    period_year: int = Field(ge=1900, le=2100)
    dias_alquilados: int = Field(ge=0, le=366)
    basis_used: Decimal = Field(ge=Decimal("0"))
    amortization_amount: Decimal = Field(ge=Decimal("0"))
    cumulative_amortization_through_year: Decimal = Field(ge=Decimal("0"))
    schema_version: str = "1"


__all__ = [
    "RentalAmortizationLedgerEntry",
    "RentalContract",
    "RentalExpense",
    "RentalFinca",
    "RentalIncomeRecord",
]

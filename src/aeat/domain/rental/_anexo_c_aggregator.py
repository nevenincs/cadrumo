"""M100 Anexo C aggregator — derives 0061/0066/0072/0078/0085 from the rental register (#454).

The aggregator pulls per-finca + per-contract data from the rental
register repositories for a given ejercicio and produces the five
caller-supplied casillas that the existing M100 Anexo C ruleset
consumes:

  - 0061: Σ per-contract gross_rent_received for the period.
  - 0066: Σ per-finca total_deductible (LIRPF art. 23.1) including
    capped + uncapped + consumed carry-forward.
  - 0072: Σ per-finca capped_amortization (LIRPF art. 23.1.f).
  - 0078: Σ per-contract reducción amount = tier_pct *
    qualifying_share * clamp_pos(per-contract rendimiento neto
    positivo) per LIRPF art. 23.2.
  - 0085: Σ per-finca imputación 1,1 % / 2 % (LIRPF art. 85) for
    fincas whose ``use_type`` is ``OTRO_INMUEBLE_NO_AFECTO`` or
    ``VIVIENDA_DESOCUPADA``.

Per-finca attribution and per-contract tier resolutions are exposed
on the result for audit traceability.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...core.logging import get_logger
from ._amortization_ledger import compute_amortization_for_year
from ._enums import UseType
from ._errors import AnexoCAggregationError
from ._expense_rollup import CarryForwardEntry, compute_gastos_for_year
from ._models import RentalContract, RentalFinca
from ._repository import (
    RentalAmortizationLedgerRepository,
    RentalContractRepository,
    RentalExpenseRepository,
    RentalFincaRepository,
    RentalIncomeRepository,
)
from ._tier_resolver import TierResolution, resolve_reduccion

_log = get_logger(__name__)
_CENT = Decimal("0.01")

IMPUTACION_RATE_RECENT_REVISION: Decimal = Decimal("0.011")
"""LIRPF art. 85: 1,1 % when valor catastral was revised in the 10
ejercicios prior to the period."""

IMPUTACION_RATE_OLD_OR_NO_REVISION: Decimal = Decimal("0.02")
"""LIRPF art. 85: 2 % when no qualifying recent catastral revision."""

CATASTRAL_REVISION_LOOKBACK_YEARS: int = 10
"""LIRPF art. 85: ``en los 10 períodos impositivos anteriores``."""


def _round_to_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


class FincaAttribution(BaseModel):
    """Per-finca contribution to the Anexo C aggregates."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    finca_id: int
    finca_identifier: str
    ingresos: Decimal = Field(ge=Decimal("0"))
    gastos_deducibles: Decimal = Field(ge=Decimal("0"))
    amortizacion: Decimal = Field(ge=Decimal("0"))
    reduccion_total: Decimal = Field(ge=Decimal("0"))
    imputacion: Decimal = Field(ge=Decimal("0"))


class ContractTierAttribution(BaseModel):
    """Per-contract tier resolution + reducción amount."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    contract_id: int
    finca_id: int
    rendimiento_neto_positivo: Decimal = Field(ge=Decimal("0"))
    tier: TierResolution
    reduccion_amount: Decimal = Field(ge=Decimal("0"))


class AnexoCAggregates(BaseModel):
    """Derived M100 Anexo C aggregates plus audit attribution.

    Attributes:
        period_year: Ejercicio.
        casilla_0061: Σ ingresos íntegros del arrendamiento.
        casilla_0066: Σ gastos deducibles per LIRPF art. 23.1
            (capped + uncapped + consumed carry-forward).
        casilla_0072: Σ amortización 3 % per LIRPF art. 23.1.f.
        casilla_0078: Σ reducción art. 23.2 import.
        casilla_0085: Σ imputación rentas inmobiliarias art. 85.
        per_finca_attribution: Per-finca breakdown of the above.
        per_contract_tier: Per-contract tier resolution + reducción
            amount.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    period_year: int
    casilla_0061: Decimal = Field(ge=Decimal("0"))
    casilla_0066: Decimal = Field(ge=Decimal("0"))
    casilla_0072: Decimal = Field(ge=Decimal("0"))
    casilla_0078: Decimal = Field(ge=Decimal("0"))
    casilla_0085: Decimal = Field(ge=Decimal("0"))
    per_finca_attribution: Mapping[int, FincaAttribution]
    per_contract_tier: Mapping[int, ContractTierAttribution]


def compute_anexo_c_aggregates(
    *,
    period_year: int,
    finca_repo: RentalFincaRepository,
    contract_repo: RentalContractRepository,
    income_repo: RentalIncomeRepository,
    expense_repo: RentalExpenseRepository,
    ledger_repo: RentalAmortizationLedgerRepository,
) -> AnexoCAggregates:
    """Aggregate the M100 Anexo C casillas from the rental register.

    Args:
        period_year: Ejercicio whose casillas to compute.
        finca_repo: Live :class:`RentalFincaRepository`.
        contract_repo: Live :class:`RentalContractRepository`.
        income_repo: Live :class:`RentalIncomeRepository`.
        expense_repo: Live :class:`RentalExpenseRepository`.
        ledger_repo: Live :class:`RentalAmortizationLedgerRepository`.

    Returns:
        :class:`AnexoCAggregates` carrying the five derived casillas
        plus per-finca and per-contract attribution maps for audit
        traceability.

    Raises:
        AnexoCAggregationError: When a contract references a missing
            finca, or when the ledger surfaces an inconsistent
            cumulative entry.
    """
    fincas = finca_repo.list_all()
    if not fincas:
        return AnexoCAggregates(
            period_year=period_year,
            casilla_0061=Decimal("0.00"),
            casilla_0066=Decimal("0.00"),
            casilla_0072=Decimal("0.00"),
            casilla_0078=Decimal("0.00"),
            casilla_0085=Decimal("0.00"),
            per_finca_attribution={},
            per_contract_tier={},
        )

    fincas_by_id: dict[int, RentalFinca] = {finca.id: finca for finca in fincas if finca.id is not None}

    casilla_0061 = Decimal("0.00")
    casilla_0066 = Decimal("0.00")
    casilla_0072 = Decimal("0.00")
    casilla_0078 = Decimal("0.00")
    casilla_0085 = Decimal("0.00")
    finca_attribution: dict[int, FincaAttribution] = {}
    contract_tier: dict[int, ContractTierAttribution] = {}

    for finca in fincas:
        if finca.id is None:
            continue
        if _finca_is_active_for_period(finca, period_year):
            ingresos, gastos, amortization, reduccion_total, contract_attribs = _aggregate_finca(
                finca,
                period_year=period_year,
                contract_repo=contract_repo,
                income_repo=income_repo,
                expense_repo=expense_repo,
                ledger_repo=ledger_repo,
            )
            for attrib in contract_attribs:
                contract_tier[attrib.contract_id] = attrib
        else:
            ingresos = gastos = amortization = reduccion_total = Decimal("0.00")

        imputacion = _compute_imputacion(
            finca,
            period_year=period_year,
            contract_repo=contract_repo,
            income_repo=income_repo,
        )

        finca_attribution[finca.id] = FincaAttribution(
            finca_id=finca.id,
            finca_identifier=finca.identifier,
            ingresos=ingresos,
            gastos_deducibles=gastos,
            amortizacion=amortization,
            reduccion_total=reduccion_total,
            imputacion=imputacion,
        )
        casilla_0061 += ingresos
        casilla_0066 += gastos
        casilla_0072 += amortization
        casilla_0078 += reduccion_total
        casilla_0085 += imputacion

    # Validate that every contract attribution references a known finca.
    for attrib in contract_tier.values():
        if attrib.finca_id not in fincas_by_id:
            raise AnexoCAggregationError(
                f"contract id={attrib.contract_id} references unknown finca id={attrib.finca_id}",
            )

    return AnexoCAggregates(
        period_year=period_year,
        casilla_0061=_round_to_cents(casilla_0061),
        casilla_0066=_round_to_cents(casilla_0066),
        casilla_0072=_round_to_cents(casilla_0072),
        casilla_0078=_round_to_cents(casilla_0078),
        casilla_0085=_round_to_cents(casilla_0085),
        per_finca_attribution=finca_attribution,
        per_contract_tier=contract_tier,
    )


def _finca_is_active_for_period(finca: RentalFinca, period_year: int) -> bool:
    """Whether the finca was held during ``period_year`` AND is in an
    arrendable use_type.
    """
    if finca.use_type not in {UseType.VIVIENDA_ARRENDADA, UseType.LOCAL_COMERCIAL}:
        return False
    if finca.acquisition_date.year > period_year:
        return False
    return finca.disposal_date is None or finca.disposal_date.year >= period_year


def _aggregate_finca(
    finca: RentalFinca,
    *,
    period_year: int,
    contract_repo: RentalContractRepository,
    income_repo: RentalIncomeRepository,
    expense_repo: RentalExpenseRepository,
    ledger_repo: RentalAmortizationLedgerRepository,
) -> tuple[Decimal, Decimal, Decimal, Decimal, list[ContractTierAttribution]]:
    """Compute (ingresos, gastos, amortization, reduccion_total,
    [per-contract attribution]) for one finca."""
    if finca.id is None:
        raise AnexoCAggregationError("finca lacks persistent id")
    contracts = contract_repo.list_for_finca(finca.id)
    active_contracts = [c for c in contracts if _contract_is_active_for_period(c, period_year)]
    ingresos = Decimal("0.00")
    contract_attribs: list[ContractTierAttribution] = []
    contract_to_income: dict[int, tuple[RentalContract, Decimal, int]] = {}
    for contract in active_contracts:
        if contract.id is None:
            continue
        income = income_repo.get_for_contract_period(contract.id, period_year)
        if income is None:
            contract_to_income[contract.id] = (contract, Decimal("0.00"), 0)
            continue
        contract_to_income[contract.id] = (contract, income.gross_rent_received, income.dias_alquilados)
        ingresos += income.gross_rent_received

    expenses = expense_repo.list_for_finca_period(finca.id, period_year)
    rollup = compute_gastos_for_year(
        expenses,
        period_year=period_year,
        ingresos_for_period=ingresos,
        carry_forward_in=_existing_carry_forward(),
    )
    gastos = rollup.total_deductible

    total_dias_alquilados = sum(dias for _, _, dias in contract_to_income.values())
    amortization = _compute_finca_amortization(
        finca=finca,
        period_year=period_year,
        total_dias_alquilados=total_dias_alquilados,
        ledger_repo=ledger_repo,
    )

    # Distribute gastos + amortization proportionally to ingresos to compute per-
    # contract rendimiento neto for the reducción dispatch. Single-contract
    # fincas pass through 100 %; multi-contract distributes by ingreso share.
    reduccion_total = Decimal("0.00")
    for contract_id, (contract, contract_ingresos, _) in contract_to_income.items():
        share = (contract_ingresos / ingresos) if ingresos > Decimal("0") else Decimal("0")
        contract_gastos = gastos * share
        contract_amortization = amortization * share
        rendimiento = max(
            contract_ingresos - contract_gastos - contract_amortization,
            Decimal("0"),
        )
        rendimiento = _round_to_cents(rendimiento)
        tier = resolve_reduccion(contract, finca, period_year=period_year)
        reduccion = _round_to_cents(rendimiento * tier.reduccion_pct * tier.qualifying_share)
        reduccion_total += reduccion
        contract_attribs.append(
            ContractTierAttribution(
                contract_id=contract_id,
                finca_id=finca.id,
                rendimiento_neto_positivo=rendimiento,
                tier=tier,
                reduccion_amount=reduccion,
            ),
        )

    return (
        _round_to_cents(ingresos),
        _round_to_cents(gastos),
        _round_to_cents(amortization),
        _round_to_cents(reduccion_total),
        contract_attribs,
    )


def _contract_is_active_for_period(contract: RentalContract, period_year: int) -> bool:
    if contract.contract_celebration_date.year > period_year:
        return False
    return contract.contract_termination_date is None or contract.contract_termination_date.year >= period_year


def _existing_carry_forward() -> tuple[CarryForwardEntry, ...]:
    """Future hook for persistent carry-forward queue.

    The ledger schema currently tracks per-finca per-period
    amortización but not the art. 23.1.a) cap excess. A subsequent
    PR can add a ``rental_carry_forward`` table; this aggregator
    will then consult it. For now, returns an empty queue.
    """
    return ()


def _compute_finca_amortization(
    *,
    finca: RentalFinca,
    period_year: int,
    total_dias_alquilados: int,
    ledger_repo: RentalAmortizationLedgerRepository,
) -> Decimal:
    """Compute the per-finca amortización for ``period_year``, threading
    cumulative-through-prior-year from the ledger.
    """
    if finca.id is None:
        return Decimal("0.00")
    if total_dias_alquilados == 0:
        return Decimal("0.00")
    cumulative_prior = _cumulative_through_prior_year(ledger_repo, finca.id, period_year)
    from ._models import RentalIncomeRecord

    synthetic_income = RentalIncomeRecord(
        contract_id=finca.id,  # synthetic — contract_id not used by the computation
        period_year=period_year,
        gross_rent_received=Decimal("0.00"),
        dias_alquilados=total_dias_alquilados,
    )
    computation = compute_amortization_for_year(
        finca,
        synthetic_income,
        cumulative_through_prior_year=cumulative_prior,
    )
    return computation.capped_amortization


def _cumulative_through_prior_year(
    ledger_repo: RentalAmortizationLedgerRepository,
    finca_id: int,
    period_year: int,
) -> Decimal:
    entries = ledger_repo.list_for_finca(finca_id)
    cumulative = Decimal("0")
    for entry in entries:
        if entry.period_year < period_year:
            cumulative += entry.amortization_amount
    return cumulative


def _compute_imputacion(
    finca: RentalFinca,
    *,
    period_year: int,
    contract_repo: RentalContractRepository,
    income_repo: RentalIncomeRepository,
) -> Decimal:
    """Compute LIRPF art. 85 imputación for a non-let finca.

    Applies only to ``use_type in {OTRO_INMUEBLE_NO_AFECTO,
    VIVIENDA_DESOCUPADA}`` whose acquisition_date is on or before
    period_year and disposal_date is None or in / after period_year.

    The current scope assumes full-year non-let occupancy. Partial-
    year imputación pro-rate (e.g. dwelling let part of the year and
    non-let the rest) is a follow-up issue per ADR §Consequences.
    """
    if finca.use_type not in {UseType.OTRO_INMUEBLE_NO_AFECTO, UseType.VIVIENDA_DESOCUPADA}:
        return Decimal("0.00")
    if finca.acquisition_date.year > period_year:
        return Decimal("0.00")
    if finca.disposal_date is not None and finca.disposal_date.year < period_year:
        return Decimal("0.00")
    rate = (
        IMPUTACION_RATE_RECENT_REVISION
        if (
            finca.valor_catastral_revision_year is not None
            and (period_year - finca.valor_catastral_revision_year) <= CATASTRAL_REVISION_LOOKBACK_YEARS
        )
        else IMPUTACION_RATE_OLD_OR_NO_REVISION
    )
    # silence unused-arg warnings: contract / income repos are reserved for
    # future partial-year pro-rate; current impl only needs the finca metadata.
    _ = contract_repo
    _ = income_repo
    return _round_to_cents(finca.valor_catastral_total * rate)


__all__ = [
    "AnexoCAggregates",
    "ContractTierAttribution",
    "FincaAttribution",
    "compute_anexo_c_aggregates",
]

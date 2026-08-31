"""Rental-register aggregate calculations.

:func:`compute_finca_aggregates` pulls per-finca and per-contract data from the
rental register repositories for a given ejercicio and returns a
:class:`FincaAggregates` result with :class:`FincaAttribution` and
:class:`ContractTierAttribution` audit breakdowns for factual LIRPF rental amounts:

* gross rent collected from active contracts.
* deductible expenses after the art. 23.1 cap.
* amortization under art. 23.1.f.
* residential rental reduction under art. 23.2.
* real-estate imputation under art. 85.

Filing targets are registry-owned; this module does not encode
filing-line identifiers.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents as _round_to_cents
from .amortization_ledger import compute_amortization_for_year
from .enums import ReduccionTier, UseType
from .errors import FincaAggregationError
from .expense_rollup import CarryForwardEntry, compute_gastos_for_year
from .imputacion_parameters import load_imputacion_parameters
from .models import Arrendamiento, Finca
from .repository_ports import (
    ArrendamientoReader,
    FincaAmortizacionLedgerReader,
    FincaGastoReader,
    FincaReader,
    FincaRendimientoReader,
)
from .tier_resolver import TierResolution, resolve_reduccion

_log = get_logger(__name__)

#: art. 23.2 LIRPF reducción applies only to permanent-residence lettings;
#: a LOCAL_COMERCIAL or VIVIENDA_TURISTICA finca still earns rendimiento
#: (it is in :data:`_RENDIMIENTO_ELIGIBLE_USE_TYPES` below) but is out of
#: the reducción article's scope entirely, so it must never reach
#: :func:`resolve_reduccion` — that function's ``TierResolutionError`` is
#: reserved for a genuine caller defect, not an expected non-qualifying use.
_NOT_APPLICABLE_REDUCCION = TierResolution(
    tier=ReduccionTier.NOT_APPLICABLE,
    reduccion_pct=Decimal("0"),
    qualifying_share=Decimal("0"),
    legal_refs=("ley-35-2006:art-23",),
)


class FincaAttribution(BaseModel):
    """Per-finca contribution to rental aggregate totals."""

    model_config = STRICT_FROZEN_CONFIG

    finca_id: int
    finca_identifier: str
    ingresos: Decimal = Field(ge=Decimal("0"))
    gastos_deducibles: Decimal = Field(ge=Decimal("0"))
    amortizacion: Decimal = Field(ge=Decimal("0"))
    reduccion_total: Decimal = Field(ge=Decimal("0"))
    imputacion: Decimal = Field(ge=Decimal("0"))


class ContractTierAttribution(BaseModel):
    """Per-contract tier resolution + reducción amount."""

    model_config = STRICT_FROZEN_CONFIG

    contract_id: int
    finca_id: int
    rendimiento_neto_positivo: Decimal = Field(ge=Decimal("0"))
    tier: TierResolution
    reduccion_amount: Decimal = Field(ge=Decimal("0"))


class FincaAggregates(BaseModel):
    """Derived rental aggregates plus audit attribution.

    Attributes:
        period_year: Ejercicio.
        ingresos_integros: Sum of rental income.
        gastos_deducibles: Sum of deductible expenses per LIRPF art. 23.1
            (capped + uncapped + consumed carry-forward).
        amortizacion: Sum of amortization per LIRPF art. 23.1.f.
        reduccion_arrendamiento_vivienda: Sum of art. 23.2 reduction.
        imputacion_rentas_inmobiliarias: Sum of art. 85 imputation.
        per_finca_attribution: Per-finca breakdown of the above.
        per_contract_tier: Per-contract tier resolution + reducción
            amount.
    """

    model_config = STRICT_FROZEN_CONFIG

    period_year: int
    ingresos_integros: Decimal = Field(ge=Decimal("0"))
    gastos_deducibles: Decimal = Field(ge=Decimal("0"))
    amortizacion: Decimal = Field(ge=Decimal("0"))
    reduccion_arrendamiento_vivienda: Decimal = Field(ge=Decimal("0"))
    imputacion_rentas_inmobiliarias: Decimal = Field(ge=Decimal("0"))
    per_finca_attribution: Mapping[int, FincaAttribution]
    per_contract_tier: Mapping[int, ContractTierAttribution]


def compute_finca_aggregates(
    *,
    period_year: int,
    finca_repo: FincaReader,
    contract_repo: ArrendamientoReader,
    income_repo: FincaRendimientoReader,
    expense_repo: FincaGastoReader,
    ledger_repo: FincaAmortizacionLedgerReader,
) -> FincaAggregates:
    """Aggregate factual rental amounts from the rental register.

    Args:
        period_year: Ejercicio whose rental amounts to compute.
        finca_repo: Live :class:`FincaReader`.
        contract_repo: Live :class:`ArrendamientoReader`.
        income_repo: Live :class:`FincaRendimientoReader`.
        expense_repo: Live :class:`FincaGastoReader`.
        ledger_repo: Live :class:`FincaAmortizacionLedgerReader`.

    Returns:
        :class:`FincaAggregates` carrying the derived rental totals
        and attribution maps for audit traceability.

    Raises:
        FincaAggregationError: When a contract references a missing
            finca, or when the ledger surfaces an inconsistent
            cumulative entry.
    """
    fincas = finca_repo.list_all()
    if not fincas:
        _log.debug("rental aggregates: no fincas registered for period %d; returning zero totals", period_year)
        return FincaAggregates(
            period_year=period_year,
            ingresos_integros=Decimal("0.00"),
            gastos_deducibles=Decimal("0.00"),
            amortizacion=Decimal("0.00"),
            reduccion_arrendamiento_vivienda=Decimal("0.00"),
            imputacion_rentas_inmobiliarias=Decimal("0.00"),
            per_finca_attribution={},
            per_contract_tier={},
        )

    fincas_by_id: dict[int, Finca] = {finca.id: finca for finca in fincas if finca.id is not None}

    ingresos_integros = Decimal("0.00")
    gastos_deducibles = Decimal("0.00")
    amortizacion_total = Decimal("0.00")
    reduccion_arrendamiento_vivienda = Decimal("0.00")
    imputacion_rentas_inmobiliarias = Decimal("0.00")
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
            _log.debug(
                "rental aggregates: finca id=%s identifier=%s skipped "
                "(not active or non-arrendable use_type=%s) for period %d",
                finca.id,
                finca.identifier,
                finca.use_type.value,
                period_year,
            )
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
        ingresos_integros += ingresos
        gastos_deducibles += gastos
        amortizacion_total += amortization
        reduccion_arrendamiento_vivienda += reduccion_total
        imputacion_rentas_inmobiliarias += imputacion

    # Validate that every contract attribution references a known finca.
    for attrib in contract_tier.values():
        if attrib.finca_id not in fincas_by_id:
            raise FincaAggregationError(
                f"contract id={attrib.contract_id} references unknown finca id={attrib.finca_id}",
            )

    aggregates = FincaAggregates(
        period_year=period_year,
        ingresos_integros=_round_to_cents(ingresos_integros),
        gastos_deducibles=_round_to_cents(gastos_deducibles),
        amortizacion=_round_to_cents(amortizacion_total),
        reduccion_arrendamiento_vivienda=_round_to_cents(reduccion_arrendamiento_vivienda),
        imputacion_rentas_inmobiliarias=_round_to_cents(imputacion_rentas_inmobiliarias),
        per_finca_attribution=finca_attribution,
        per_contract_tier=contract_tier,
    )
    _log.debug(
        "rental aggregates computed: period=%d fincas=%d contracts=%d "
        "income=%s expenses=%s amortization=%s reduction=%s imputation=%s",
        period_year,
        len(fincas),
        len(contract_tier),
        aggregates.ingresos_integros,
        aggregates.gastos_deducibles,
        aggregates.amortizacion,
        aggregates.reduccion_arrendamiento_vivienda,
        aggregates.imputacion_rentas_inmobiliarias,
    )
    return aggregates


_RENDIMIENTO_ELIGIBLE_USE_TYPES: frozenset[UseType] = frozenset(
    {UseType.VIVIENDA_ARRENDADA, UseType.LOCAL_COMERCIAL, UseType.VIVIENDA_TURISTICA},
)


def _finca_is_active_for_period(finca: Finca, period_year: int) -> bool:
    """Return True if the finca was held during ``period_year`` and has an arrendable use type."""
    if finca.use_type not in _RENDIMIENTO_ELIGIBLE_USE_TYPES:
        return False
    if finca.acquisition_date.year > period_year:
        return False
    return finca.disposal_date is None or finca.disposal_date.year >= period_year


def _aggregate_finca(
    finca: Finca,
    *,
    period_year: int,
    contract_repo: ArrendamientoReader,
    income_repo: FincaRendimientoReader,
    expense_repo: FincaGastoReader,
    ledger_repo: FincaAmortizacionLedgerReader,
) -> tuple[Decimal, Decimal, Decimal, Decimal, list[ContractTierAttribution]]:
    """Compute income, expenses, amortization, total reduccion, and per-contract attribution for one finca.

    Returns a 5-tuple of (ingresos, gastos, amortization, reduccion_total, contract_attributions).
    """
    if finca.id is None:
        raise FincaAggregationError("finca lacks persistent id")
    contracts = contract_repo.list_for_finca(finca.id)
    active_contracts = [c for c in contracts if _contract_is_active_for_period(c, period_year)]
    ingresos = Decimal("0.00")
    contract_attribs: list[ContractTierAttribution] = []
    contract_to_income: dict[int, tuple[Arrendamiento, Decimal, int]] = {}
    for contract in active_contracts:
        if contract.id is None:
            continue
        income = income_repo.get_for_contract_period(contract.id, period_year)
        if income is None:
            _log.debug(
                "rental aggregates: no income record for contract_id=%s finca_id=%s period=%d; treating as zero",
                contract.id,
                finca.id,
                period_year,
            )
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
        tier = (
            resolve_reduccion(contract, finca, period_year=period_year)
            if finca.use_type is UseType.VIVIENDA_ARRENDADA
            else _NOT_APPLICABLE_REDUCCION
        )
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


def _contract_is_active_for_period(contract: Arrendamiento, period_year: int) -> bool:
    if contract.contract_celebration_date.year > period_year:
        return False
    return contract.contract_termination_date is None or contract.contract_termination_date.year >= period_year


def _existing_carry_forward() -> tuple[CarryForwardEntry, ...]:
    """Return the registered carry-forward queue for the finca.

    Persistent carry-forward storage is not part of the current
    rental register surface, so the aggregate layer fails closed by
    consuming no prior-year excess.
    """
    _log.debug(
        "rental aggregates: no carry-forward persistence registered; "
        "art. 23.1.a) cap excess from prior years is not consumed",
    )
    return ()


def _compute_finca_amortization(
    *,
    finca: Finca,
    period_year: int,
    total_dias_alquilados: int,
    ledger_repo: FincaAmortizacionLedgerReader,
) -> Decimal:
    """Compute the per-finca amortización for ``period_year``.

    Threads cumulative-through-prior-year deductions from the ledger to enforce
    the acquisition-cost ceiling.
    """
    if finca.id is None:
        return Decimal("0.00")
    if total_dias_alquilados == 0:
        return Decimal("0.00")
    cumulative_prior = _cumulative_through_prior_year(ledger_repo, finca.id, period_year)
    from .models import FincaRendimientoRecord

    amortization_input = FincaRendimientoRecord(
        contract_id=finca.id,
        period_year=period_year,
        gross_rent_received=Decimal("0.00"),
        dias_alquilados=total_dias_alquilados,
    )
    computation = compute_amortization_for_year(
        finca,
        amortization_input,
        cumulative_through_prior_year=cumulative_prior,
    )
    return computation.capped_amortization


def _cumulative_through_prior_year(
    ledger_repo: FincaAmortizacionLedgerReader,
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
    finca: Finca,
    *,
    period_year: int,
    contract_repo: ArrendamientoReader,
    income_repo: FincaRendimientoReader,
) -> Decimal:
    """Compute LIRPF art. 85 imputación for a non-let finca.

    Applies only to ``use_type in {OTRO_INMUEBLE_NO_AFECTO,
    VIVIENDA_DESOCUPADA}`` whose acquisition_date is on or before
    period_year and disposal_date is None or in / after period_year.

    The current scope assumes full-year non-let occupancy. Partial-
    year imputación pro-rate belongs in the registry-backed filing
    binding for the affected modelo.
    """
    if finca.use_type not in {UseType.OTRO_INMUEBLE_NO_AFECTO, UseType.VIVIENDA_DESOCUPADA}:
        return Decimal("0.00")
    if finca.acquisition_date.year > period_year:
        return Decimal("0.00")
    if finca.disposal_date is not None and finca.disposal_date.year < period_year:
        return Decimal("0.00")
    imputacion = load_imputacion_parameters()
    rate = (
        imputacion.recent_revision_rate
        if (
            finca.valor_catastral_revision_year is not None
            and (period_year - finca.valor_catastral_revision_year) <= imputacion.catastral_revision_lookback_years
        )
        else imputacion.old_or_no_revision_rate
    )
    # silence unused-arg warnings: contract / income repos are reserved for
    # future partial-year pro-rate; current impl only needs the finca metadata.
    _ = contract_repo
    _ = income_repo
    return _round_to_cents(finca.valor_catastral_total * rate)


__all__ = [
    "ContractTierAttribution",
    "FincaAggregates",
    "FincaAttribution",
    "compute_finca_aggregates",
]

"""LIRPF art. 23.1.f amortización 3 % multi-year ledger.

Per-finca per-period amortización accrual with cumulative-through-
year cap tracking. The depreciable basis at year N is
``max(coste_adquisicion_construccion, valor_catastral_construccion)``;
the per-year accrual is ``basis * 3 % * dias_alquilados / 365``,
clamped down so the cumulative-through-year never exceeds
``coste_adquisicion_construccion``.

Default behaviour clamps to the remaining cap and never raises.
Strict callers (preflight verifiers that surface the cap on the
filing surface) opt in via ``strict=True`` and receive
:class:`AmortizationLedgerCapExceededError` when an accrual would
overflow.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, Modelo
from ...core.external_constants import AMORTIZACION_INMUEBLE_RATE
from ...core.logging import get_logger
from ...core.money import round_to_cents as _round_to_cents
from ._models import Finca, FincaAmortizacionLedgerEntry, FincaRendimientoRecord
from .errors import AmortizationLedgerCapExceededError

_logger = get_logger(__name__)

ART_23_1_F_RATE: Decimal = AMORTIZACION_INMUEBLE_RATE
"""3 % amortización of capital-inmobiliario rental properties; rate fixed by RD 439/2007
(RIRPF) art. 14.2.a; deductibility base Ley 35/2006 art. 23.  Re-export alias for
:data:`~core.external_constants.AMORTIZACION_INMUEBLE_RATE`."""

DAYS_PER_YEAR: Decimal = Decimal("365")
"""Pro-rate denominator. The BOE wording uses "anual" — we adopt 365
days for every year (including leap years), matching AEAT's manual
práctico Renta worked-example convention."""


def _resolve_amortizacion_inmueble_rate(period_year: int) -> Decimal:
    """Read the RIRPF art. 14 amortisation rate from the registry parameter.

    Reads ``renta-<period_year>-rental-amortizacion-rate`` from Modelo 100.
    A missing registry revision or parameter is a grounding defect and raises
    :class:`RegistryValidationError`. The registry parameter is grounded on
    RD 439/2007 art. 14 (``rd-439-2007:art-14``), which fixes the 3 por ciento
    rate, and on Ley 35/2006 art. 23 as the substantive base.
    """
    from cadrumo.domain.calculations.registry.formula_runtime_ops import read_parameter

    return read_parameter(
        Modelo.M100.value,
        str(period_year),
        f"renta-{period_year}-rental-amortizacion-rate",
        date_context={"filing_period": date(period_year, 12, 31)},
    )


class AmortizationComputation(BaseModel):
    """Outcome of a single :func:`compute_amortization_for_year` invocation.

    Attributes:
        period_year: Ejercicio.
        basis: Depreciable basis used (``max(coste_construccion,
            valor_catastral_construccion)``).
        gross_amortization: ``basis * 0.03 * dias_alquilados / 365``,
            rounded to cents — what would accrue if the cap were not
            in play.
        capped_amortization: Final accrual after clamping at the
            remaining cap. Equal to ``gross_amortization`` when no
            clamp applied.
        cumulative_through_year: Cumulative-through-year sum
            (including the current accrual).
        clamp_applied: ``True`` when the cap reduced the gross
            amortización below its theoretical value.
    """

    model_config = STRICT_FROZEN_CONFIG

    period_year: int
    basis: Decimal = Field(ge=Decimal("0"))
    gross_amortization: Decimal = Field(ge=Decimal("0"))
    capped_amortization: Decimal = Field(ge=Decimal("0"))
    cumulative_through_year: Decimal = Field(ge=Decimal("0"))
    clamp_applied: bool


def compute_amortization_for_year(
    finca: Finca,
    income: FincaRendimientoRecord,
    *,
    cumulative_through_prior_year: Decimal,
    strict: bool = False,
) -> AmortizationComputation:
    """Compute the per-finca per-year amortización 3 % entry.

    Args:
        finca: Owning :class:`Finca`.
        income: Income record for the same finca/contract for the
            target period — provides ``period_year`` and
            ``dias_alquilados``.
        cumulative_through_prior_year: Sum of prior years'
            ``capped_amortization`` for this finca. The caller (the
            ledger orchestrator) sources this from the persisted
            ledger.
        strict: When ``True`` and the gross accrual would push
            cumulative beyond ``coste_adquisicion_construccion``,
            raise :class:`AmortizationLedgerCapExceededError`
            instead of clamping.

    Returns:
        An :class:`AmortizationComputation` carrying the per-year
        result.

    Raises:
        AmortizationLedgerCapExceededError: When ``strict`` is
            ``True`` and the gross accrual would overflow the cap.
    """
    basis = max(finca.coste_adquisicion_construccion, finca.valor_catastral_construccion)
    gross = _round_to_cents(
        basis
        * _resolve_amortizacion_inmueble_rate(income.period_year)
        * Decimal(income.dias_alquilados)
        / DAYS_PER_YEAR,
    )
    cap = finca.coste_adquisicion_construccion
    remaining_cap = max(cap - cumulative_through_prior_year, Decimal("0"))
    capped = min(gross, remaining_cap)
    capped = _round_to_cents(capped)
    clamped = capped < gross
    if clamped:
        _logger.debug(
            "amortization capped: finca_id=%s period=%d gross=%s cap_remaining=%s capped=%s",
            finca.id,
            income.period_year,
            gross,
            remaining_cap,
            capped,
        )
    if strict and clamped:
        raise AmortizationLedgerCapExceededError(
            "amortización accrual exceeds coste_adquisicion_construccion cap",
            context={
                "finca_id": finca.id,
                "period_year": income.period_year,
                "gross": str(gross),
                "remaining_cap": str(remaining_cap),
            },
        )
    cumulative = _round_to_cents(cumulative_through_prior_year + capped)
    return AmortizationComputation(
        period_year=income.period_year,
        basis=basis,
        gross_amortization=gross,
        capped_amortization=capped,
        cumulative_through_year=cumulative,
        clamp_applied=clamped,
    )


def computation_to_ledger_entry(
    finca_id: int,
    income: FincaRendimientoRecord,
    computation: AmortizationComputation,
) -> FincaAmortizacionLedgerEntry:
    """Project an :class:`AmortizationComputation` into a persistable record.

    Returns:
        A :class:`FincaAmortizacionLedgerEntry` ready for persistence.
    """
    return FincaAmortizacionLedgerEntry(
        finca_id=finca_id,
        period_year=computation.period_year,
        dias_alquilados=income.dias_alquilados,
        basis_used=computation.basis,
        amortization_amount=computation.capped_amortization,
        cumulative_amortization_through_year=computation.cumulative_through_year,
    )


__all__ = [
    "ART_23_1_F_RATE",
    "AmortizationComputation",
    "computation_to_ledger_entry",
    "compute_amortization_for_year",
]

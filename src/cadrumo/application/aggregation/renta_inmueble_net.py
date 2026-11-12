"""Carry one let property from its gross income to its reduced net yield.

The chain follows LIRPF art. 23 and RIRPF arts. 13 and 14, in the order the
official design states the boxes of one ``Inmueble``:

* Financing interest and repair and conservation are limited, for each
  property, to its gross income (LIRPF art. 23.1.a.1.º; RIRPF art. 13.a).
  Earlier ejercicios' pending amounts apply first, then the year's own; what
  the year's own leaves over is pending for the four following years. What
  earlier ejercicios left pending is never inferred: while it is unknown the
  net yield is not computed. A pending amount, earlier or the year's own, is
  filed split by the ejercicio it arose in; the property states one total, so
  the split is never invented and the property blocks.
* The building is amortised at the registry's rate on the greater of the
  acquisition cost and the cadastral value, the land excluded (LIRPF art.
  23.1.b; RIRPF art. 14.2.a), for the days the property was let. Without a
  stated land value the cost is split by the ejercicio's cadastral values;
  improvements made before the ejercicio join the cost. Cumulative
  amortisation never passes the acquisition value without the land.
* The net yield is the gross income less every deduction the chain computes;
  the boxes it does not offer (furniture, special cases, an accessory property)
  stay out of it and are named as a limitation.
* The art. 23.2 reduction applies per contract to the contract's positive net
  yield, at the rate derived from the lease's facts and the dated regime.
* The withholding is the suffered-withholding records whose payer is a tenant
  of the property; a record that names no tenant, or a tenant of two
  properties, cannot be placed and blocks.

The figures enter as the taxpayer's part: the ledger amounts already carry the
share where the rows hold whole-property amounts, and the property record's
acquisition and cadastral facts, which state the whole property, are scaled by
the ownership percentage here. Each figure is rounded once to the cent.

A fact the chain needs and the records do not state leaves the boxes that
depend on it unresolved with a finding; it is never read as zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.money.rounding import round_to_cents
from ...domain.calculations.registry.gasto_capital_inmobiliario import GastoCapitalInmobiliarioCatalogue
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_record import InmuebleRecord, ValorCatastral
from ...domain.renta.rental_reduction import RentalReductionArt232Tier
from ...domain.renta.rental_reduction_derivation import (
    RentalReductionArt232Rules,
    RentalReductionRefusal,
    derive_rental_reduction,
)
from ...domain.renta.retencion_soportada import RetencionSoportadaRecord
from .renta_inmueble_findings import RentaInmuebleCause

_ZERO: Final = Decimal(0)
_HUNDRED: Final = Decimal(100)


@dataclass(frozen=True, slots=True)
class RentaInmuebleTerms:
    """The dated registry data the chain reads for one ejercicio."""

    amortizacion_rate: Decimal
    """The annual amortisation rate of a building (RIRPF art. 14.2.a)."""
    reduction_rules: RentalReductionArt232Rules
    reduction_rates: Mapping[RentalReductionArt232Tier, Decimal]
    """The rate of every reduction a lease can take at the ejercicio's devengo."""


@dataclass(frozen=True, slots=True)
class RentaInmuebleNetInputs:
    """What the occurrence already established, which the chain starts from."""

    record: InmuebleRecord
    leases: tuple[ArrendamientoRecord, ...]
    ejercicio_first: date
    ejercicio_last: date
    days_let: int
    lease_days: Mapping[int, int]
    """The days let under each lease, by its row key."""
    ingresos: Decimal
    lease_ingresos: Mapping[int, Decimal]
    """The taxpayer's part of the rent of each lease, by its row key."""
    gastos: Mapping[str, Decimal]
    """The taxpayer's part of each prorated expense concept."""
    improvements_before: Decimal
    """The taxpayer's part of the improvements the ledger states before the ejercicio."""
    improvements_in: Decimal
    """The taxpayer's part of the improvements made in the ejercicio."""
    withholding: tuple[RetencionSoportadaRecord, ...]
    """The suffered-withholding records placed on this property."""
    pendiente: Decimal | None
    """The interest and repair earlier ejercicios left pending, or ``None`` when it is not known."""
    prior_return_held: bool = False
    """Whether the profile holds the return of the previous ejercicio, which states its pending amounts unmatched."""

    @property
    def ejercicio_days(self) -> int:
        """Return the days of the ejercicio."""
        return (self.ejercicio_last - self.ejercicio_first).days + 1


@dataclass(slots=True)
class RentaInmuebleNet:
    """The boxes of one property's chain; ``None`` leaves a box off the row."""

    valor_catastral: Decimal | None = None
    valor_catastral_construccion: Decimal | None = None
    porcentaje_construccion: Decimal | None = None
    importe_adquisicion: Decimal | None = None
    gastos_adquisicion: Decimal | None = None
    mejoras_anteriores: Decimal | None = None
    mejoras_ejercicio: Decimal | None = None
    base_amortizacion: Decimal | None = None
    amortizacion: Decimal | None = None
    gastos_pendientes_anteriores: Decimal | None = None
    gastos_pendientes_aplicados: Decimal | None = None
    intereses_reparacion_aplicados: Decimal | None = None
    intereses_reparacion_pendientes: Decimal | None = None
    rendimiento_neto: Decimal | None = None
    reduccion_aplicable: bool | None = None
    reduccion: Decimal | None = None
    retenciones: Decimal | None = None
    rendimiento_neto_reducido: Decimal | None = None
    causes: list[RentaInmuebleCause] = field(default_factory=list)


def _ownership(record: InmuebleRecord) -> Decimal:
    """Return the share of the whole property the record's own figures are scaled by."""
    titularidad = record.titularidad
    percentage = None if titularidad is None else titularidad.porcentaje_propiedad
    return Decimal(1) if percentage is None else percentage / _HUNDRED


def _scaled(value: Decimal | None, share: Decimal) -> Decimal | None:
    return None if value is None else round_to_cents(value * share)


def _nonzero(value: Decimal) -> Decimal | None:
    return value if value else None


def _cadastral_values(record: InmuebleRecord, ejercicio: int) -> ValorCatastral | None:
    return next((valor for valor in record.valores_catastrales if valor.year == ejercicio), None)


@dataclass(frozen=True, slots=True)
class _Amortisation:
    base: Decimal
    """The whole property's base, the land excluded."""
    acquisition_side: Decimal
    """The whole property's acquisition value without the land, improvements included."""
    acquisition_is_base: bool


def _construction_cost(
    inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, cadastral: ValorCatastral | None
) -> Decimal | None:
    """Return the whole property's acquisition cost without the land, or ``None`` when it cannot be split."""
    record = inputs.record
    if record.importe_adquisicion is None or record.gastos_tributos_adquisicion is None:
        net.causes.append(RentaInmuebleCause.ACQUISITION_COST_UNSTATED)
        return None
    cost = record.importe_adquisicion + record.gastos_tributos_adquisicion
    if record.valor_suelo is not None and record.importe_adquisicion > 0:
        return cost * (record.importe_adquisicion - record.valor_suelo) / record.importe_adquisicion
    if cadastral is None or cadastral.total == 0:
        net.causes.append(RentaInmuebleCause.CADASTRAL_VALUES_UNSTATED)
        return None
    # RIRPF art. 14.2.a: without a stated land value the cost is split by the cadastral values of
    # the year; the design states the construction share as a percentage with two decimals.
    percentage = (cadastral.construccion / cadastral.total * _HUNDRED).quantize(Decimal("0.01"))
    net.porcentaje_construccion = percentage
    return round_to_cents(cost * percentage / _HUNDRED)


def _amortisation_base(inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, share: Decimal) -> _Amortisation | None:
    record = inputs.record
    cadastral = _cadastral_values(record, inputs.ejercicio_last.year)
    net.importe_adquisicion = _scaled(record.importe_adquisicion, share)
    net.gastos_adquisicion = _scaled(record.gastos_tributos_adquisicion, share)
    if cadastral is not None:
        net.valor_catastral = round_to_cents(cadastral.total * share)
        net.valor_catastral_construccion = round_to_cents(cadastral.construccion * share)
    cost = _construction_cost(inputs, net, cadastral)
    if cost is None:
        return None
    profile_before = sum((mejora.importe for mejora in record.mejoras if mejora.fecha < inputs.ejercicio_first), _ZERO)
    improvements = profile_before * share + inputs.improvements_before
    net.mejoras_anteriores = _nonzero(round_to_cents(improvements))
    net.mejoras_ejercicio = _nonzero(round_to_cents(inputs.improvements_in))
    acquisition_side = cost * share + improvements
    cadastral_side = _ZERO if cadastral is None else cadastral.construccion * share
    base = max(acquisition_side, cadastral_side)
    return _Amortisation(base=base, acquisition_side=acquisition_side, acquisition_is_base=base == acquisition_side)


@dataclass(frozen=True, slots=True)
class _Room:
    """How much amortisation the acquisition value still admits: ``None`` when the cap cannot bind."""

    known: bool
    remaining: Decimal | None = None


def _cumulative_room(
    inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, amortisation: _Amortisation, rate: Decimal, share: Decimal
) -> _Room:
    """Return the room the cumulative cap leaves (RIRPF art. 14.2.a; the manual's limit).

    The cap cannot bind when the base is the acquisition side and the rate
    times the calendar years from the acquisition through the ejercicio does
    not reach one. Otherwise the cumulative amortisation attested to the first
    day of the ejercicio is required.
    """
    record = inputs.record
    acquired = record.fecha_adquisicion
    if amortisation.acquisition_is_base and acquired is not None:
        years = inputs.ejercicio_last.year - acquired.year + 1
        if rate * years <= 1:
            return _Room(known=True)
    if record.amortizacion_acumulada is None or record.amortizacion_acumulada_desde != inputs.ejercicio_first:
        net.causes.append(RentaInmuebleCause.CUMULATIVE_AMORTISATION_UNSTATED)
        return _Room(known=False)
    remaining = amortisation.acquisition_side - record.amortizacion_acumulada * share
    return _Room(known=True, remaining=max(remaining, _ZERO))


def _amortise(inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, rate: Decimal) -> bool:
    """Fill the amortisation boxes; return whether the year's amortisation is known."""
    share = _ownership(inputs.record)
    amortisation = _amortisation_base(inputs, net, share)
    if amortisation is None:
        return False
    room = _cumulative_room(inputs, net, amortisation, rate, share)
    if not room.known:
        return False
    net.base_amortizacion = round_to_cents(amortisation.base)
    year = net.base_amortizacion * rate * inputs.days_let / inputs.ejercicio_days
    net.amortizacion = round_to_cents(year if room.remaining is None else min(year, room.remaining))
    return True


def _limited_concepts(concepts: GastoCapitalInmobiliarioCatalogue) -> frozenset[str]:
    return frozenset(str(concept.token) for concept in concepts.concepts if concept.limited)


def _apply_limit(
    inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, concepts: GastoCapitalInmobiliarioCatalogue
) -> Decimal | None:
    """Fill the limited-expense boxes; return what they deduct, or ``None`` while the carry is unknown.

    Earlier ejercicios' pending amounts take the room the gross income leaves
    first; the year's own interest and repairs take what remains. Any amount
    pending, carried in or left over, needs its split by year of origin.
    """
    limited = _limited_concepts(concepts)
    own = sum((amount for concept, amount in inputs.gastos.items() if concept in limited), _ZERO)
    if inputs.pendiente is None:
        net.causes.append(
            RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED
            if inputs.prior_return_held
            else RentaInmuebleCause.PENDING_EXPENSES_UNSTATED
        )
        if own > inputs.ingresos:
            net.causes.append(RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)
        return None
    net.gastos_pendientes_anteriores = _nonzero(inputs.pendiente)
    earlier = min(inputs.pendiente, inputs.ingresos)
    applied = min(own, inputs.ingresos - earlier)
    net.gastos_pendientes_aplicados = _nonzero(earlier)
    net.intereses_reparacion_aplicados = _nonzero(applied)
    net.intereses_reparacion_pendientes = _nonzero(own - applied)
    if inputs.pendiente or own > applied:
        net.causes.append(RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)
    return earlier + applied


def _reduction_tiers(
    inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet, terms: RentaInmuebleTerms
) -> dict[int, RentalReductionArt232Tier | None] | None:
    """Derive each lease's reduction, ``None`` for a lease without one; ``None`` when one cannot be derived."""
    tiers: dict[int, RentalReductionArt232Tier | None] = {}
    for lease in inputs.leases:
        outcome = derive_rental_reduction((lease,), devengo=inputs.ejercicio_last, rules=terms.reduction_rules)
        if outcome.refusal is not None:
            net.causes.append(
                RentaInmuebleCause.REDUCTION_TENANTS_MIXED
                if outcome.refusal is RentalReductionRefusal.MIXED_TENANT_AGES
                else RentaInmuebleCause.REDUCTION_FACT_UNSTATED
            )
            return None
        tiers[lease.clave] = outcome.tier if outcome.aplicable is True else None
    return tiers


def _reduce(
    inputs: RentaInmuebleNetInputs,
    net: RentaInmuebleNet,
    rates: Mapping[RentalReductionArt232Tier, Decimal],
    tiers: Mapping[int, RentalReductionArt232Tier | None],
    deductions: Decimal,
) -> None:
    """Fill the reduction: per contract, on the contract's positive net yield, at its derived rate.

    The deductions are the property's, so each contract bears them in
    proportion to the days it was let.
    """
    reduction = _ZERO
    applies = False
    for lease in inputs.leases:
        tier = tiers.get(lease.clave)
        if tier is None:
            continue
        applies = True
        share_of_days = Decimal(inputs.lease_days.get(lease.clave, 0)) / Decimal(inputs.days_let)
        lease_net = inputs.lease_ingresos.get(lease.clave, _ZERO) - deductions * share_of_days
        if lease_net > 0:
            reduction += round_to_cents(lease_net * rates[tier])
    if applies:
        net.reduccion_aplicable = True
        net.reduccion = reduction
    if net.rendimiento_neto is not None:
        net.rendimiento_neto_reducido = net.rendimiento_neto - reduction


def _withhold(inputs: RentaInmuebleNetInputs, net: RentaInmuebleNet) -> None:
    """Total the withholding placed on the property; none placed is none suffered on it."""
    net.retenciones = round_to_cents(sum((record.pago_a_cuenta for record in inputs.withholding), _ZERO))


def renta_inmueble_net(
    inputs: RentaInmuebleNetInputs, *, terms: RentaInmuebleTerms, concepts: GastoCapitalInmobiliarioCatalogue
) -> RentaInmuebleNet:
    """Compute one let property's chain from its occurrence's figures.

    Returns:
        Every box the chain could settle, and the cause of each it could not.
    """
    net = RentaInmuebleNet()
    _withhold(inputs, net)
    amortised = _amortise(inputs, net, terms.amortizacion_rate)
    limited = _apply_limit(inputs, net, concepts)
    tiers = _reduction_tiers(inputs, net, terms)
    if not amortised or limited is None or net.amortizacion is None:
        return net
    limited_tokens = _limited_concepts(concepts)
    others = sum((amount for concept, amount in inputs.gastos.items() if concept not in limited_tokens), _ZERO)
    deductions = limited + others + net.amortizacion
    net.rendimiento_neto = inputs.ingresos - deductions
    if tiers is not None:
        _reduce(inputs, net, terms.reduction_rates, tiers, deductions)
    return net


__all__ = [
    "RentaInmuebleNet",
    "RentaInmuebleNetInputs",
    "RentaInmuebleTerms",
    "renta_inmueble_net",
]

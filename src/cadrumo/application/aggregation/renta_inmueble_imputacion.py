"""The imputed income of LIRPF art. 85 for the days a property stood at its owner's disposal.

A held day of the ejercicio is let, or in one of the property's dated uses: the
habitual dwelling, an economic activity, or at the owner's disposal. Only a day
at the owner's disposal imputes income; a day in none of them is unknown, and
says so, because a property waiting to be let imputes too.

The imputed income is the ejercicio's cadastral value times the rate, times the
days at disposal over the year-days the registry states, times the holder's
share (LIRPF art. 85.1 and 85.2, art. 11.3). The reduced rate applies when the
general collective valuation behind that value entered into force in the
ejercicio or in the look-back periods before it, or, where the edition declares
it, from the first day of a stated year. A whole ejercicio at disposal counts
the year-days; any shorter span counts its own days. Every rate, count and year
comes from the registry; the record gives only dated facts.

A fact the rule needs and the record does not state withholds the amount with a
blocking finding: it is never read as zero. So does what the Inmueble boxes
cannot carry: a property without a cadastral value, whose base is half its
acquisition or checked value, a day at disposal shared with another use, and a
rustic property.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from ...core.money.rounding import round_to_cents
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_record import (
    InmuebleNaturaleza,
    InmuebleRecord,
    TitularidadRegimen,
    UsoInmueble,
    UsoInmuebleTipo,
    ValorCatastral,
)
from .renta_inmueble_findings import RentaInmuebleCause
from .renta_inmueble_period import Ejercicio, held_interval, lease_days

_HUNDRED: Final = Decimal(100)
_WHOLE_PROPERTY: Final = Decimal(100)
"""The share of the property at disposal when the whole of it was (casilla 0087)."""
_NO_DAYS: Final = frozenset[date]()


@dataclass(frozen=True, slots=True)
class ImputacionTerms:
    """The dated registry data of art. 85 for one ejercicio."""

    rate_general: Decimal
    rate_reduced: Decimal
    year_days: int
    """The divisor of the days at disposal, and what a whole ejercicio at disposal counts."""
    revision_periods: int
    """How many periods before the ejercicio a collective valuation may have entered into force."""
    revision_from_year: int | None
    """A year from whose first day a collective valuation qualifies whatever the look-back; ``None`` when undeclared."""


def _days(start: date, end: date) -> frozenset[date]:
    return frozenset(start + timedelta(days=offset) for offset in range((end - start).days + 1))


def _use_days(uso: UsoInmueble, held: tuple[date, date]) -> frozenset[date]:
    start = max(held[0], uso.desde)
    end = held[1] if uso.hasta is None else min(held[1], uso.hasta)
    return _days(start, end) if start <= end else _NO_DAYS


@dataclass(frozen=True, slots=True)
class HeldDays:
    """How each held day of the ejercicio was used: let, or in one of the property's dated uses."""

    held: frozenset[date]
    let: frozenset[date]
    uses: Mapping[UsoInmuebleTipo, frozenset[date]]

    @property
    def disposal(self) -> frozenset[date]:
        """Return the days the property stood at its owner's disposal."""
        return self.uses.get(UsoInmuebleTipo.DISPOSICION_PROPIETARIO, _NO_DAYS)

    @property
    def unaccounted(self) -> bool:
        """Report whether some held day was neither let nor in any stated use."""
        accounted = self.let.union(*self.uses.values())
        return not self.held <= accounted

    @property
    def disposal_shared(self) -> bool:
        """Report whether a day at disposal was also let or in another use."""
        others = self.let.union(
            *(days for tipo, days in self.uses.items() if tipo is not UsoInmuebleTipo.DISPOSICION_PROPIETARIO)
        )
        return not self.disposal.isdisjoint(others)


def held_days(record: InmuebleRecord, held: tuple[date, date], leases: Iterable[ArrendamientoRecord]) -> HeldDays:
    """Return how the held days ``held`` of ``record`` were used under ``leases`` and its dated uses."""
    uses: dict[UsoInmuebleTipo, frozenset[date]] = {}
    for uso in record.usos:
        uses[uso.tipo] = uses.get(uso.tipo, _NO_DAYS) | _use_days(uso, held)
    return HeldDays(
        held=_days(*held),
        let=_NO_DAYS.union(*(lease_days(lease, held) for lease in leases)),
        uses=uses,
    )


@dataclass(frozen=True, slots=True)
class RentaInmuebleImputacion:
    """What one property at its owner's disposal states in casillas 0083 to 0089, and what withholds it."""

    dias: int
    """The days at disposal the return states (casilla 0085)."""
    valor_catastral: Decimal | None
    """The ejercicio's cadastral value (casilla 0083), or ``None`` when the record states none."""
    revisado: bool | None
    """Whether the reduced rate's collective valuation applies (casilla 0084), or ``None`` when unknown."""
    porcentaje: Decimal | None
    """The share of the property at disposal (casilla 0087), or ``None`` when it shared its days with another use."""
    importe: Decimal | None
    """The income imputed to the filer (casilla 0089), or ``None`` while a finding withholds it."""
    causes: tuple[RentaInmuebleCause, ...]


def _reduced(vigor: int, ejercicio: int, terms: ImputacionTerms) -> bool:
    if ejercicio - terms.revision_periods <= vigor <= ejercicio:
        return True
    return terms.revision_from_year is not None and terms.revision_from_year <= vigor <= ejercicio


def _share(record: InmuebleRecord) -> Decimal | None:
    """Return the holder's share in pleno dominio; any other right is withheld by the property's own finding."""
    titularidad = record.titularidad
    if titularidad is None or titularidad.regimen is not TitularidadRegimen.PLENO_DOMINIO:
        return None
    percentage = titularidad.porcentaje_propiedad
    return None if percentage is None else percentage / _HUNDRED


def _valor(record: InmuebleRecord, ejercicio: int) -> ValorCatastral | None:
    valor = next((item for item in record.valores_catastrales if item.year == ejercicio), None)
    return None if valor is None or valor.total == 0 else valor


def _counted_days(disposal: int, ejercicio: Ejercicio, terms: ImputacionTerms) -> int:
    days = terms.year_days if disposal == ejercicio.days else disposal
    if days > terms.year_days:
        raise ValueError(f"the year-days of art. 85, {terms.year_days}, are fewer than {days} days at disposal")
    return days


def _causes(record: InmuebleRecord, days: HeldDays, valor: ValorCatastral | None) -> tuple[RentaInmuebleCause, ...]:
    """Return what withholds the imputed amount of ``record``: a fact unstated, or a case the boxes cannot carry."""
    causes: list[RentaInmuebleCause] = []
    if days.disposal_shared:
        causes.append(RentaInmuebleCause.IMPUTACION_USO_SIMULTANEO)
    if record.naturaleza is InmuebleNaturaleza.RUSTICA:
        causes.append(RentaInmuebleCause.IMPUTACION_RUSTICA)
    if valor is None:
        causes.append(RentaInmuebleCause.IMPUTACION_VALOR_CATASTRAL_UNSTATED)
    elif valor.vigor is None:
        causes.append(RentaInmuebleCause.IMPUTACION_VIGOR_UNSTATED)
    return tuple(causes)


def _importe(
    valor: ValorCatastral | None, revisado: bool | None, dias: int, share: Decimal | None, terms: ImputacionTerms
) -> Decimal | None:
    if valor is None or revisado is None or share is None:
        return None
    rate = terms.rate_reduced if revisado else terms.rate_general
    return round_to_cents(valor.total * rate * Decimal(dias) / Decimal(terms.year_days) * share)


def renta_inmueble_imputacion(
    record: InmuebleRecord, days: HeldDays, ejercicio: Ejercicio, terms: ImputacionTerms
) -> RentaInmuebleImputacion | None:
    """Return the art. 85 boxes of ``record`` for ``ejercicio``, or ``None`` when no day stood at disposal."""
    if not days.disposal:
        return None
    year = ejercicio.first.year
    valor = _valor(record, year)
    causes = _causes(record, days, valor)
    revisado = None if valor is None or valor.vigor is None else _reduced(valor.vigor, year, terms)
    dias = _counted_days(len(days.disposal), ejercicio, terms)
    return RentaInmuebleImputacion(
        dias=dias,
        valor_catastral=None if valor is None else valor.total,
        revisado=revisado,
        porcentaje=None if days.disposal_shared else _WHOLE_PROPERTY,
        importe=None if causes else _importe(valor, revisado, dias, _share(record), terms),
        causes=causes,
    )


@dataclass(frozen=True, slots=True)
class PropertyImputacion:
    """The art. 85 boxes of one held property, and every finding its held days raise."""

    boxes: RentaInmuebleImputacion | None
    """The boxes, or ``None`` when no day stood at the owner's disposal."""
    causes: tuple[RentaInmuebleCause, ...]


def property_imputacion(
    record: InmuebleRecord, ejercicio: Ejercicio, leases: Iterable[ArrendamientoRecord], terms: ImputacionTerms
) -> PropertyImputacion | None:
    """Return the art. 85 boxes of ``record`` under ``leases``, or ``None`` when it was not held in ``ejercicio``."""
    held = held_interval(record, ejercicio)
    if held is None:
        return None
    days = held_days(record, held, leases)
    boxes = renta_inmueble_imputacion(record, days, ejercicio, terms)
    unaccounted = (RentaInmuebleCause.DAYS_UNACCOUNTED,) if days.unaccounted else ()
    return PropertyImputacion(boxes=boxes, causes=(*unaccounted, *(() if boxes is None else boxes.causes)))


__all__ = [
    "HeldDays",
    "ImputacionTerms",
    "PropertyImputacion",
    "RentaInmuebleImputacion",
    "held_days",
    "property_imputacion",
    "renta_inmueble_imputacion",
]

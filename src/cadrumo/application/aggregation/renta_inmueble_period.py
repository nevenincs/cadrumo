"""The days an ejercicio covers, the days a property is held and the days each lease lets it.

These are the calendar facts the ``Inmueble`` occurrence is prorated by: the ejercicio's own span, the
interval of it the property is held, and, inside that interval, the days each lease is in force.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_record import InmuebleRecord


@dataclass(frozen=True, slots=True)
class Ejercicio:
    """The calendar span of the ejercicio a return declares."""

    first: date
    last: date

    @property
    def days(self) -> int:
        """Return the number of days the ejercicio spans."""
        return (self.last - self.first).days + 1

    def covers(self, day: date) -> bool:
        """Report whether ``day`` falls inside the ejercicio."""
        return self.first <= day <= self.last


def held_interval(record: InmuebleRecord, ejercicio: Ejercicio) -> tuple[date, date] | None:
    """Return the held days of the ejercicio, or ``None`` when the acquisition is unstated or nothing is held."""
    if record.fecha_adquisicion is None:
        return None
    start = max(ejercicio.first, record.fecha_adquisicion)
    end = ejercicio.last if record.fecha_transmision is None else min(ejercicio.last, record.fecha_transmision)
    return (start, end) if start <= end else None


def lease_days(lease: ArrendamientoRecord, held: tuple[date, date]) -> set[date]:
    """Return the held days a lease is in force."""
    start = max(held[0], lease.fecha_inicio)
    end = held[1] if lease.fecha_fin is None else min(held[1], lease.fecha_fin)
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)} if start <= end else set()


@dataclass(frozen=True, slots=True)
class Occupancy:
    """How a held property was let: the leases that cover some held day and the days held and let."""

    leases: tuple[ArrendamientoRecord, ...]
    days_held: int
    days_let: int
    concurrent: bool
    lease_days: Mapping[int, int]
    """The days each active lease covers, by its row key."""


def occupancy(leases: Iterable[ArrendamientoRecord], held: tuple[date, date]) -> Occupancy:
    """Return the occupancy of a property held over ``held`` under ``leases``."""
    spans = sorted(
        ((lease, lease_days(lease, held)) for lease in leases),
        key=lambda item: (item[0].fecha_inicio, item[0].clave),
    )
    active = tuple((lease, days) for lease, days in spans if days)
    let_days = {day for _lease, days in active for day in days}
    return Occupancy(
        leases=tuple(lease for lease, _days in active),
        days_held=(held[1] - held[0]).days + 1,
        days_let=len(let_days),
        concurrent=sum(len(days) for _lease, days in active) > len(let_days),
        lease_days={lease.clave: len(days) for lease, days in active},
    )


def within_lease(lease: ArrendamientoRecord, day: date) -> bool:
    """Report whether ``day`` lies inside the lease's term."""
    return lease.fecha_inicio <= day and (lease.fecha_fin is None or day <= lease.fecha_fin)


__all__ = ["Ejercicio", "Occupancy", "held_interval", "lease_days", "occupancy", "within_lease"]

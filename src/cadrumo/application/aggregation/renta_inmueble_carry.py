"""What a let property carries into anexo C.1 from earlier ejercicios, and what must be stated first.

The interest and repair excess of a property carries into the following
ejercicios of the registry's carry window (LIRPF art. 23.1.a.1.º; RIRPF art.
13.a), so only an ejercicio in which the property was let can have left one.
The property record states when the property was first let, or that it never
was. The window asks for a statement of each origin year that is not before
that start. A lease that started before the ejercicio shows earlier letting
too, but it never stands in for an unstated start: then every origin year of
the window is asked for, and the unstated start blocks on its own. A property
whose start is unstated blocks on that start even when it was first let in the
ejercicio, because nothing stored says so.

An opening amount is a carry of earlier returns, never inferred. The filer
states it per property and origin year, as nothing pending or as the amount;
a held earlier return is not read for it, and the finding says so. Before
anexo C.1 was followed by origin year, a property's carry was stated as one
total: a total of nothing still answers every origin year of the window, but
an amount cannot be split here, so the filer is asked for the split.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_record import InmuebleRecord
from .renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFinding
from .renta_inmueble_period import Ejercicio

_ZERO: Final = Decimal(0)


@dataclass(frozen=True, slots=True)
class PendingStatements:
    """The filer's statements of what earlier ejercicios left pending, by property row."""

    by_origin: Mapping[int, Mapping[str, Decimal]] = field(default_factory=dict)
    """Each origin year's statements, by origin back and then by the property's row identity."""
    totals: Mapping[str, Decimal] = field(default_factory=dict)
    """The one total a property's carry was stated as before it was split by origin year, by row identity."""


@dataclass(frozen=True, slots=True)
class CarryWindow:
    """The origin years a let property must have stated, and whether its first letting is unstated."""

    backs: tuple[int, ...]
    """The origin years, counted back from the ejercicio, whose opening amount needs a statement."""
    start_unstated: bool


def carry_window(
    record: InmuebleRecord, leases: Iterable[ArrendamientoRecord], ejercicio: Ejercicio, window: int
) -> CarryWindow:
    """Return the origin years of ``window`` whose carry ``record`` must state for ``ejercicio``.

    ``leases`` are every lease of the property, active in the ejercicio or not.
    """
    if record.sin_arrendar:
        return CarryWindow(backs=(), start_unstated=False)
    every = tuple(range(1, window + 1))
    let_earlier = any(lease.fecha_inicio < ejercicio.first for lease in leases)
    start = record.arrendado_desde
    if start is None:
        return CarryWindow(backs=every if let_earlier else (), start_unstated=True)
    if start < ejercicio.first:
        # An origin ejercicio counts when it ends on or after the day the property was first let.
        let_years = ejercicio.first.year - start.year
        return CarryWindow(backs=tuple(back for back in every if back <= let_years), start_unstated=False)
    return CarryWindow(backs=every if let_earlier else (), start_unstated=False)


@dataclass(frozen=True, slots=True)
class PendingCarry:
    """The opening amount of every origin year, or ``None`` while one is unknown, and the findings."""

    pendientes: Mapping[int, Decimal] | None
    findings: tuple[RentaInmuebleFinding, ...]


def pending_carry(
    *,
    subject: str,
    carry: CarryWindow,
    window: int,
    stated: PendingStatements,
    prior_return_held: bool,
) -> PendingCarry:
    """Resolve the opening amount of each origin year of ``window`` for the property ``subject`` names.

    A statement for the origin year decides it. An origin year the window does
    not ask for carries nothing. One the window asks for, unstated, takes a
    stated total of nothing as its own absence; otherwise it is unknown, and its
    finding names the origin year so its door can name the column.
    """
    findings: list[RentaInmuebleFinding] = []
    if carry.start_unstated:
        findings.append(RentaInmuebleFinding(RentaInmuebleCause.LETTING_START_UNSTATED, subject))
    total = stated.totals.get(subject)
    unstated = (
        RentaInmuebleCause.PENDING_EXPENSES_TOTAL_UNSPLIT
        if total is not None
        else RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED
        if prior_return_held
        else RentaInmuebleCause.PENDING_EXPENSES_UNSTATED
    )
    pendientes: dict[int, Decimal] = {}
    known = True
    for back in range(1, window + 1):
        statement = stated.by_origin.get(back, {}).get(subject)
        if statement is not None:
            pendientes[back] = statement
        elif back not in carry.backs or total == _ZERO:
            pendientes[back] = _ZERO
        else:
            known = False
            findings.append(RentaInmuebleFinding(unstated, subject, back=back))
    return PendingCarry(pendientes=pendientes if known else None, findings=tuple(findings))


__all__ = ["CarryWindow", "PendingCarry", "PendingStatements", "carry_window", "pending_carry"]

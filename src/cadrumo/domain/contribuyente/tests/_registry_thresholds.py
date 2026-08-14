"""The Art. 58/61 eligibility ceilings, read from the registry rather than retyped.

Two test modules in this package need a
:class:`~cadrumo.domain.contribuyente.MinimoDescendientesThresholds` to
exercise the ordinary-eligibility predicate. Both previously built one from
inline ``Decimal`` literals carrying the real regulatory figures, which
``aeat-registry-authority-flow`` forbids: a regulatory value inlined at a call
site is a second authority, and a revision that moved either ceiling would
leave those modules passing against a stale figure while the engine used the
new one.

The ceilings live in the registry as ``money`` parameters, one pair per filing
year, authored alongside the legal-catalogue entries that ground them. This
module resolves that pair and is the single home for doing so on the domain
side, so neither consuming module grows its own copy of the lookup.

Neither consumer asserts the ceiling VALUES -- they pass the thresholds in to
exercise age, cohabitation, discapacidad and custody logic. The external
grounding of the figures themselves is asserted where it belongs, against the
registry parameters and their corpus anchors. What this module buys is that a
moved ceiling cannot silently diverge from what these tests assume.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

from ....core.resources import resources
from ...calculations.registry import resolve_parameter
from .. import MinimoDescendientesThresholds

__all__ = [
    "registry_birth_order_amounts",
    "registry_menor_tres_supplement",
    "registry_thresholds",
]

_BIRTH_ORDER_SUFFIXES = (
    "primer-hijo",
    "segundo-hijo",
    "tercer-hijo",
    "cuarto-y-siguientes",
)


def _parameter(filing_year: int, suffix: str) -> Decimal:
    """Resolve one ``minimo-descendientes`` parameter for *filing_year*."""
    snapshot = resources().modelos.authority.snapshot("100", filing_year=filing_year, period="0A")
    by_id = {parameter.id: parameter for parameter in snapshot.revision.parameters}
    return resolve_parameter(
        by_id[f"renta-{filing_year}-minimo-descendientes-{suffix}-{filing_year}"],
        {"filing_period": date(filing_year, 12, 31)},
    )


@cache
def registry_thresholds(filing_year: int) -> MinimoDescendientesThresholds:
    """The Art. 58.1 and Art. 61 norma 2a ceilings the registry declares for *filing_year*.

    Cached because the registry load is the expensive part and the answer is
    fixed for a given year.
    """
    return MinimoDescendientesThresholds(
        rentas_anuales_limite=_parameter(filing_year, "rentas-anuales-limite"),
        declaracion_propia_rentas_limite=_parameter(filing_year, "declaracion-propia-rentas-limite"),
    )


@cache
def registry_birth_order_amounts(filing_year: int) -> tuple[Decimal, ...]:
    """The four Art. 58.1 birth-order tranches the registry declares, in order.

    The same argument this module's docstring makes for the ceilings applies to
    the granted AMOUNTS: a module that restates 2.400 / 2.700 / 4.000 / 4.500 as
    literals keeps passing against a stale table if a revision moves one. The
    figures' own external grounding is asserted in
    :mod:`test_minimo_personal_familiar_grounded`, which is where a euro literal
    legitimately appears because there the figure is the assertion target.
    """
    return tuple(_parameter(filing_year, suffix) for suffix in _BIRTH_ORDER_SUFFIXES)


@cache
def registry_menor_tres_supplement(filing_year: int) -> Decimal:
    """The Art. 58.2 under-three supplement the registry declares for *filing_year*."""
    return _parameter(filing_year, "menor-tres-anos")


def registry_fallecimiento_amount(filing_year: int) -> Decimal:
    """The Art. 61 norma 4ª death-in-period flat cuantía the registry declares for *filing_year*.

    Read from its OWN parameter rather than from the first birth-order tranche,
    which carries the same figure in every served revision. A test that took the
    tranche would keep passing if the two were ever wrongly bound together,
    which is precisely the confusion the separate parameter exists to prevent.
    """
    return _parameter(filing_year, "fallecimiento")

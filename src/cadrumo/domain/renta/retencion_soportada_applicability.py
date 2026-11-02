"""Whether a suffered-withholding income class needs payer evidence, from the profile's income categories.

The profile declares the taxpayer's IRPF income categories for an ejercicio
(registry fact 0128). A class whose income the taxpayer declares, or whose
declaration cannot be read, needs payer records or an explicit absence
attestation before its credit resolves: fail-closed, so a missing certificate
never reads as zero. A class whose income the profile positively declares
absent resolves to a proven zero without either.

The class-to-category table maps each income class to the profile categories
whose income it is withheld on. A class with no unambiguous category stays
:attr:`RetencionSoportadaApplicability.UNKNOWN` whatever the profile says: an
absence is never inferred for it.

A declaration is the complete list of categories the taxpayer has. An empty or
unanswered declaration is unknown rather than a declaration of no income,
which is how the modelo applicability rules read the same fact.

An urban rental carried on as an activity is activity income, but so is every
other activity, so the category alone cannot say whether one exists. For that
class a declared activity category is refined by the IAE epigraph of each
declared activity (:func:`arrendamiento_actividad_applicability`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ...core.retencion_soportada import RetencionSoportadaClase

__all__ = [
    "IAE_URBAN_RENTAL_GROUP",
    "RETENCION_SOPORTADA_INCOME_CATEGORIES",
    "RetencionSoportadaApplicability",
    "arrendamiento_actividad_applicability",
    "retencion_soportada_applicability",
]


class RetencionSoportadaApplicability(StrEnum):
    """What the profile says about whether a class's income exists in the ejercicio."""

    DECLARED = "declared"
    """The profile declares income of a category this class is withheld on."""
    UNKNOWN = "unknown"
    """The profile declares nothing readable, or the class maps to no unambiguous category."""
    DECLARED_ABSENT = "declared_absent"
    """The profile declares its categories and none of them is one this class is withheld on."""


RETENCION_SOPORTADA_INCOME_CATEGORIES: Final[Mapping[RetencionSoportadaClase, frozenset[str] | None]] = (
    MappingProxyType(
        {
            # Work income, pensions included (LIRPF art. 17.2.a); the vocabulary keeps pension apart.
            RetencionSoportadaClase.TRABAJO: frozenset({"trabajo", "pension"}),
            RetencionSoportadaClase.CAPITAL_MOBILIARIO: frozenset({"capital_mobiliario"}),
            # An urban rental that is not an activity is capital inmobiliario income (LIRPF art. 22).
            RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO: frozenset({"capital_inmobiliario"}),
            # A rental that constitutes an activity is activity income (LIRPF art. 27.2); whether one is
            # declared is read from the activities' IAE group (RIRPF art. 100; RDLeg 1175/1990, group 861).
            RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD: frozenset({"actividad_economica"}),
            RetencionSoportadaClase.ACTIVIDAD_ECONOMICA: frozenset({"actividad_economica"}),
            # Premios are ganancias patrimoniales (LIRPF art. 33).
            RetencionSoportadaClase.GANANCIA_PATRIMONIAL: frozenset({"ganancias_patrimoniales"}),
            # Income attributed by an entidad en régimen de atribución, or imputed by an AIE, UTE or
            # image-rights assignee, has no category of its own in the profile vocabulary.
            RetencionSoportadaClase.ATRIBUCION_CAPITAL_MOBILIARIO: None,
            RetencionSoportadaClase.ATRIBUCION_CAPITAL_INMOBILIARIO: None,
            RetencionSoportadaClase.ATRIBUCION_ACTIVIDAD_ECONOMICA: None,
            RetencionSoportadaClase.ATRIBUCION_GANANCIA_PATRIMONIAL: None,
            RetencionSoportadaClase.IMPUTACION_AIE_UTE: None,
            RetencionSoportadaClase.IMPUTACION_DERECHOS_IMAGEN: None,
        },
    )
)
"""The profile income categories (fact 0128 tokens) each class's withholding is practised on.

Total over :class:`~cadrumo.core.retencion_soportada.RetencionSoportadaClase`.
``None`` marks a class no profile category identifies unambiguously.
"""

if set(RETENCION_SOPORTADA_INCOME_CATEGORIES) != set(RetencionSoportadaClase):
    raise ValueError("every suffered-withholding income class has exactly one income-category entry")


IAE_URBAN_RENTAL_GROUP: Final[str] = "861"
"""The IAE group of urban property rental, whose withholding RIRPF art. 100 makes an activity's.

Group 861 of the tariffs' sección primera (empresariales) is "alquiler de
viviendas" and "alquiler de locales industriales y otros alquileres n.c.o.p."
(RDLeg 1175/1990, tarifas, sección primera, agrupación 86). Sección segunda
(profesionales) reuses the number: its group 861 is pintores, escultores y
ceramistas. The profile records no sección, so a declared 861 is read as the
rental group; that reading only ever asks for payer evidence, never proves an
absence, so it fails closed.
"""

_IAE_EPIGRAPH: Final[re.Pattern[str]] = re.compile(r"(?P<group>[0-9]{3})(?:\.[0-9])?")
"""A three-digit IAE group, optionally followed by one epigraph digit; nothing else parses."""


def arrendamiento_actividad_applicability(
    activity_epigraphs: Sequence[str | None] | None,
) -> RetencionSoportadaApplicability:
    """Return whether the declared activities include an urban rental carried on as an activity.

    ``activity_epigraphs`` holds the IAE epigraph of each declared activity, or
    ``None`` for an activity that records none. Any activity in group 861 is
    declared; every activity parsing to another group is a proven absence; no
    activity, or any epigraph that does not parse, is unknown. The group is read
    exactly: a prefix of 861 is not 861.
    """
    if activity_epigraphs is None or len(activity_epigraphs) == 0:
        return RetencionSoportadaApplicability.UNKNOWN
    groups = [
        None if epigraph is None else _IAE_EPIGRAPH.fullmatch(epigraph.strip()) for epigraph in activity_epigraphs
    ]
    if any(match is not None and match.group("group") == IAE_URBAN_RENTAL_GROUP for match in groups):
        return RetencionSoportadaApplicability.DECLARED
    if any(match is None for match in groups):
        return RetencionSoportadaApplicability.UNKNOWN
    return RetencionSoportadaApplicability.DECLARED_ABSENT


def retencion_soportada_applicability(
    income_class: RetencionSoportadaClase,
    declared_categories: frozenset[str] | None,
    activity_epigraphs: Sequence[str | None] | None = None,
) -> RetencionSoportadaApplicability:
    """Return what the profile's declared categories say about ``income_class``.

    ``declared_categories`` is the profile's declaration in force for the
    ejercicio, or ``None`` when it declares none. ``activity_epigraphs`` is the
    IAE epigraph of each declared activity, read only for the urban rental
    carried on as an activity, once the profile declares activity income.
    """
    categories = RETENCION_SOPORTADA_INCOME_CATEGORIES[income_class]
    if categories is None or declared_categories is None or not bool(declared_categories):
        return RetencionSoportadaApplicability.UNKNOWN
    if not categories & declared_categories:
        return RetencionSoportadaApplicability.DECLARED_ABSENT
    if income_class is RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD:
        return arrendamiento_actividad_applicability(activity_epigraphs)
    return RetencionSoportadaApplicability.DECLARED

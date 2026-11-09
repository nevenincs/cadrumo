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
declared activity (:func:`arrendamiento_actividad_applicability`), against the
IAE groups the governed fact :data:`IAE_URBAN_RENTAL_GROUPS_FACT_ID` declares.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ...core.retencion_soportada import RetencionSoportadaClase
from ..calculations.registry.governed_fact_scope import GovernedFactSource
from ..calculations.registry.iae_activity_groups import (
    ActivityGroupMembership,
    activity_group_membership,
)

__all__ = [
    "IAE_URBAN_RENTAL_GROUPS_FACT_ID",
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
            # declared is read from the activities' IAE group (RIRPF art. 75.3.g; RDLeg 1175/1990 tarifas).
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


IAE_URBAN_RENTAL_GROUPS_FACT_ID: Final[str] = "rd-439-2007-art-75:iae-grupos-arrendamiento-inmuebles-urbanos"
"""The governed fact naming the IAE groups that classify an urban property rental as an activity.

RIRPF art. 75.3.g).3.º names the group of the tariffs' sección primera
(empresariales) under which a lessor's urban rental activity is classified
(RDLeg 1175/1990, tarifas, sección primera, agrupación 86). Sección segunda
(profesionales) reuses the same group numbers for unrelated professions. The
profile records no sección, so a declared epigraph in a fact group is read as
the rental group; that reading only ever asks for payer evidence, never proves
an absence, so it fails closed.
"""

_MEMBERSHIP_APPLICABILITY: Final[Mapping[ActivityGroupMembership, RetencionSoportadaApplicability]] = MappingProxyType(
    {
        ActivityGroupMembership.DECLARED: RetencionSoportadaApplicability.DECLARED,
        ActivityGroupMembership.DECLARED_ABSENT: RetencionSoportadaApplicability.DECLARED_ABSENT,
        ActivityGroupMembership.UNKNOWN: RetencionSoportadaApplicability.UNKNOWN,
    },
)


def arrendamiento_actividad_applicability(
    activity_epigraphs: Sequence[str | None] | None,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> RetencionSoportadaApplicability:
    """Return whether the declared activities include an urban rental carried on as an activity.

    ``activity_epigraphs`` holds the IAE epigraph of each declared activity, or
    ``None`` for an activity that records none. Any activity in a rental group
    the fact declares on ``effective_date`` is declared; every activity parsing
    to another group is a proven absence; no activity, or any epigraph that does
    not parse, is unknown. The group reading itself belongs to
    :func:`domain.calculations.registry.iae_activity_groups.activity_group_membership`,
    which every rule keying off an IAE classification shares; only the mapping
    into this module's own vocabulary is local.
    """
    return _MEMBERSHIP_APPLICABILITY[
        activity_group_membership(
            activity_epigraphs,
            fact_id=IAE_URBAN_RENTAL_GROUPS_FACT_ID,
            effective_date=effective_date,
            authority=authority,
        )
    ]


def retencion_soportada_applicability(
    income_class: RetencionSoportadaClase,
    declared_categories: frozenset[str] | None,
    activity_epigraphs: Sequence[str | None] | None = None,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> RetencionSoportadaApplicability:
    """Return what the profile's declared categories say about ``income_class``.

    ``declared_categories`` is the profile's declaration in force for the
    ejercicio, or ``None`` when it declares none. ``activity_epigraphs`` is the
    IAE epigraph of each declared activity, read only for the urban rental
    carried on as an activity, once the profile declares activity income; the
    rental groups are then read from ``authority`` on ``effective_date``.
    """
    categories = RETENCION_SOPORTADA_INCOME_CATEGORIES[income_class]
    if categories is None or declared_categories is None or not bool(declared_categories):
        return RetencionSoportadaApplicability.UNKNOWN
    if not categories & declared_categories:
        return RetencionSoportadaApplicability.DECLARED_ABSENT
    if income_class is RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD:
        return arrendamiento_actividad_applicability(
            activity_epigraphs, effective_date=effective_date, authority=authority
        )
    return RetencionSoportadaApplicability.DECLARED

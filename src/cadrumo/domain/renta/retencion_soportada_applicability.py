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
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ...core.retencion_soportada import RetencionSoportadaClase

__all__ = [
    "RETENCION_SOPORTADA_INCOME_CATEGORIES",
    "RetencionSoportadaApplicability",
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
            # A rental that constitutes an activity is activity income (LIRPF art. 27.2).
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


def retencion_soportada_applicability(
    income_class: RetencionSoportadaClase,
    declared_categories: frozenset[str] | None,
) -> RetencionSoportadaApplicability:
    """Return what the profile's declared categories say about ``income_class``.

    ``declared_categories`` is the profile's declaration in force for the
    ejercicio, or ``None`` when it declares none.
    """
    categories = RETENCION_SOPORTADA_INCOME_CATEGORIES[income_class]
    if categories is None or declared_categories is None or not bool(declared_categories):
        return RetencionSoportadaApplicability.UNKNOWN
    if categories & declared_categories:
        return RetencionSoportadaApplicability.DECLARED
    return RetencionSoportadaApplicability.DECLARED_ABSENT

"""Closed AEAT Renta profile-code vocabularies.

These enums model the small code sets consumed by the Modelo 100
profile bindings. They are intentionally domain-owned so CLI and wizard
surfaces can expose accepted values without hard-coding tax vocabulary
in the presentation layer.
"""

from __future__ import annotations

from enum import StrEnum


class RentaDeclaracionType(StrEnum):
    """Modelo 100 ``TIPOTRIBUTACION`` values."""

    INDIVIDUAL = "1"
    JOINT = "2"


class RentaSexCode(StrEnum):
    """Modelo 100 ``tipo_Sexo`` values."""

    HOMBRE = "H"
    MUJER = "M"


class RentaMaritalStatus(StrEnum):
    """Modelo 100 ``tipo_EstadoCivil`` values."""

    SOLTERO = "1"
    CASADO = "2"
    VIUDO = "3"
    SEPARADO_DIVORCIADO = "4"


class RentaDisabilityGrade(StrEnum):
    """Modelo 100 ``tipo_GradoDiscapacidad`` values."""

    GE_33_LT_65 = "1"
    GE_65 = "2"
    JUDICIAL_INCAPACITY = "3"
    ASSISTANCE_OR_REDUCED_MOBILITY = "4"


__all__ = [
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
]

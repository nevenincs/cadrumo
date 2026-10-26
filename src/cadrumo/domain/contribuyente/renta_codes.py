"""AEAT Renta profile-code types and stable export projections.

The closed profile vocabularies remain here where they are form-owned. The
cross-cutting fiscal-residency vocabulary is an opaque token projected from
the governed facts registry, so CLI and wizard surfaces obtain its choices
through the registry resolver rather than maintaining a second catalogue.

:class:`RentaSexCode`, :class:`RentaMaritalStatus`, and
:class:`RentaDisabilityGrade` back Modelo 100
profile bindings; :class:`SituacionFamiliar` and
:class:`SituacionFamiliarM145` keep the Art. 82 LIRPF joint-taxation axis
separate from Modelo 145 withholding categories.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from functools import cache
from types import MappingProxyType

from ...core.registry_token import StrictRegistryToken
from .ccaa import CCAA


class RentaSexCode(StrEnum):
    """Modelo 100 ``tipo_Sexo`` values."""

    HOMBRE = "H"
    MUJER = "M"


class RentaMaritalStatus(StrEnum):
    """Renta taxpayer marital / registered-partnership profile values."""

    SOLTERO = "1"
    CASADO = "2"
    VIUDO = "3"
    SEPARADO_DIVORCIADO = "4"
    PAREJA_HECHO = "5"


RENTA_MODELO100_ECIVIL_EXPORT_CODES: frozenset[str] = frozenset(
    {
        RentaMaritalStatus.SOLTERO.value,
        RentaMaritalStatus.CASADO.value,
        RentaMaritalStatus.VIUDO.value,
        RentaMaritalStatus.SEPARADO_DIVORCIADO.value,
    }
)
"""Official Modelo 100 ECIVIL export codes accepted by the bundled XSD."""


def modelo100_ecivil_export_code(value: object) -> str:
    """Return a validated official Modelo 100 ECIVIL export code.

    ``RentaMaritalStatus.PAREJA_HECHO`` is intentionally profile-only. The
    official Modelo 100 ECIVIL field is restricted to Estado Civil codes 1-4,
    so callers must supply the taxpayer's true official civil-status code
    instead of exporting the registered-partnership profile marker.
    """
    code = str(value).strip()
    if code in RENTA_MODELO100_ECIVIL_EXPORT_CODES:
        return code
    if code == RentaMaritalStatus.PAREJA_HECHO.value:
        raise ValueError(
            "profile-only pareja de hecho marital status code '5' is not a valid Modelo 100 ECIVIL export code; "
            "supply the official Estado Civil code 1-4"
        )
    raise ValueError(f"Modelo 100 ECIVIL export code must be one of 1, 2, 3, or 4; got {code!r}")


# The código each autonomous community carries on a Modelo 100 declaration.
#
# Grounded in the ``tipo_CCAA`` simpleType of the bundled Modelo 100 record-design
# XSD (``corpus/aeat_official/disenos_registro/modelo_100/files/``): the código
# table is an ``xs:documentation`` annotation sitting inside the same simpleType
# that carries the ``xs:enumeration`` constraining ``codigoCADeclaracion``, so it
# cannot disagree with AEAT's own validator. All six bundled exercises (2020-2025,
# four distinct AEAT update dates) carry a byte-identical enumeration and table.
#
# This table is Modelo 100's, and is NOT a general-purpose CCAA numbering. Two
# other numberings for the same communities disagree with it and must never be
# substituted:
#   * Modelo 763's design register diverges almost everywhere past código 03 --
#     its 13 is Madrid, where Modelo 100's 13 is Región de Murcia.
#   * The INE comunidad codes agree on 01-06, 09, 18 and 19 and then diverge on
#     eight entries -- INE swaps Castilla y León with Castilla-La Mancha, and its
#     12, 13, 16 and 17 are Galicia, Madrid, País Vasco and La Rioja against
#     Modelo 100's Madrid, Murcia, La Rioja and C. Valenciana. A spot-check of
#     the leading entries passes against INE while more than half of Spain would
#     still misfile, which is why the grounding test derives every código from
#     the XSD rather than checking a sample.
#
# Códigos 18, 19 and 20 (Ceuta, Melilla, no residente) are declared by the XSD but
# unreachable from :class:`CCAA`, which is the ordinary common-regime catalogue:
# the autonomous cities raise ``ForalRegimeError`` and "no residente" is not a
# comunidad. Códigos 14 and 15 are assigned to nothing in the AEAT table.
_MODELO100_CCAA_CODIGOS_BY_NAME: Mapping[str, str] = MappingProxyType(
    {
        "ANDALUCIA": "01",
        "ARAGON": "02",
        "ASTURIAS": "03",
        "BALEARES": "04",
        "CANARIAS": "05",
        "CANTABRIA": "06",
        "CASTILLA_LA_MANCHA": "07",
        "CASTILLA_Y_LEON": "08",
        "CATALUNA": "09",
        "EXTREMADURA": "10",
        "GALICIA": "11",
        "MADRID": "12",
        "MURCIA": "13",
        "LA_RIOJA": "16",
        "COMUNIDAD_VALENCIANA": "17",
    },
)


@cache
def renta_modelo100_ccaa_codigos() -> Mapping[CCAA, str]:
    """Return the official Modelo 100 CCAA códigos accepted by the bundled XSD.

    Keyed lazily rather than at module scope because :class:`CCAA` members are
    projected from the governed facts registry: naming one resolves the
    catalogue, and resolving it while this module is being imported reaches the
    registry authority through an import cycle. The códigos themselves are the
    form's own datum and stay here.
    """
    return MappingProxyType({getattr(CCAA, name): codigo for name, codigo in _MODELO100_CCAA_CODIGOS_BY_NAME.items()})


def modelo100_ccaa_codigo(value: CCAA | str) -> str:
    """Return the official Modelo 100 código for an autonomous community.

    Args:
        value: The community to look up, as a :class:`CCAA` member or its
            canonical lowercase token (``"madrid"``). Any other string is a
            community this export cannot name, and is refused rather than
            resolved.

    Returns:
        The two-digit código AEAT's Modelo 100 schema accepts for ``value``.

    Raises:
        ValueError: when ``value`` names no community that carries a Modelo 100
            código. Refusing is deliberate: a community exported under the wrong
            código produces a declaration that validates against the AEAT schema
            while naming the wrong comunidad, so an absent código must fail the
            export rather than fall back to a default.
    """
    try:
        community: CCAA | None = CCAA(value)
    except ValueError:
        community = None
    if community is not None and not isinstance(value, CCAA) and str(community) != value:
        community = None
    codigos = renta_modelo100_ccaa_codigos()
    codigo = codigos.get(community) if community is not None else None
    if codigo is None:
        valid = ", ".join(sorted(member.value for member in codigos))
        raise ValueError(f"no Modelo 100 CCAA código is assigned to {value!r}; communities carrying a código: {valid}")
    return codigo


class RentaDisabilityGrade(StrEnum):
    """Modelo 100 ``tipo_GradoDiscapacidad`` values."""

    GE_33_LT_65 = "1"
    GE_65 = "2"
    JUDICIAL_INCAPACITY = "3"
    ASSISTANCE_OR_REDUCED_MOBILITY = "4"


class FiscalResidency(StrictRegistryToken):
    """Opaque fiscal-residency token projected from the facts registry.

    The registry owns residency membership and its downstream regime meaning.
    This type retains only the stable wire-token shape; callers obtain values
    through the typed residency catalogue resolver.
    """

    __slots__ = ()

    _projection_source = "registry"


class SituacionFamiliar(StrictRegistryToken):
    """Opaque Art. 82 family-situation token projected from the facts registry.

    The registry owns the five-token vocabulary and the joint-taxation
    eligibility mapping.  This type retains only the stable wire-token shape;
    callers obtain a value through the typed registry projection.
    """

    __slots__ = ()


class SituacionFamiliarM145(StrictRegistryToken):
    """Opaque Modelo 145 family-situation token projected from the facts registry.

    Fact 0142 owns the three form values, their legal descriptions, and the
    supplementary-reduction eligibility mapping. This type retains only the
    stable wire-token shape; callers obtain values through the typed registry
    projection in ``situacion_familiar_m145_catalogue``.
    """

    __slots__ = ()


__all__ = [
    "RENTA_MODELO100_ECIVIL_EXPORT_CODES",
    "FiscalResidency",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
    "modelo100_ccaa_codigo",
    "modelo100_ecivil_export_code",
    "renta_modelo100_ccaa_codigos",
]

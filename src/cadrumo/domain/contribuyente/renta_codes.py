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
from types import MappingProxyType
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError
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
RENTA_MODELO100_CCAA_CODIGOS: Mapping[CCAA, str] = MappingProxyType(
    {
        CCAA.ANDALUCIA: "01",
        CCAA.ARAGON: "02",
        CCAA.ASTURIAS: "03",
        CCAA.BALEARES: "04",
        CCAA.CANARIAS: "05",
        CCAA.CANTABRIA: "06",
        CCAA.CASTILLA_LA_MANCHA: "07",
        CCAA.CASTILLA_Y_LEON: "08",
        CCAA.CATALUNA: "09",
        CCAA.EXTREMADURA: "10",
        CCAA.GALICIA: "11",
        CCAA.MADRID: "12",
        CCAA.MURCIA: "13",
        CCAA.LA_RIOJA: "16",
        CCAA.COMUNIDAD_VALENCIANA: "17",
    },
)
"""Official Modelo 100 CCAA códigos accepted by the bundled XSD."""


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
    codigo = RENTA_MODELO100_CCAA_CODIGOS.get(community) if community is not None else None
    if codigo is None:
        valid = ", ".join(sorted(member.value for member in RENTA_MODELO100_CCAA_CODIGOS))
        raise ValueError(f"no Modelo 100 CCAA código is assigned to {value!r}; communities carrying a código: {valid}")
    return codigo


class RentaDisabilityGrade(StrEnum):
    """Modelo 100 ``tipo_GradoDiscapacidad`` values."""

    GE_33_LT_65 = "1"
    GE_65 = "2"
    JUDICIAL_INCAPACITY = "3"
    ASSISTANCE_OR_REDUCED_MOBILITY = "4"


class FiscalResidency(str):
    """Opaque fiscal-residency token projected from the facts registry.

    The registry owns residency membership and its downstream regime meaning.
    This type retains only the stable wire-token shape; callers obtain values
    through the typed residency catalogue resolver.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("FiscalResidency tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("FiscalResidency token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("FiscalResidency must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only an already projected token and serialize it as text."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token for diagnostics."""
        return str(self)


class SituacionFamiliar(StrEnum):
    """Legal family situation for the Art. 82 LIRPF unidad-familiar eligibility test.

    Determines which of the two Art. 82.1 unidad-familiar modalities a
    tributación conjunta (joint) declaration may form:

    - ``casado``: married and not legally separated; conjunta available as a
      couple (Art. 82.1.1ª), with the couple's minor / judicially-incapacitated
      children if any — children are optional.
    - ``pareja_hecho_registrada`` / ``pareja_hecho_no_registrada``: a de-facto
      couple, registered or not. Art. 82.1.2ª keys the second modality on the
      absence of a *marriage bond* ("cuando no existiera vínculo matrimonial"),
      which is registration-agnostic: a de-facto couple has no marriage bond,
      so conjunta is available only as a monoparental unit (one parent with the
      qualifying children), never as a couple.
    - ``soltero`` / ``separado_divorciado``: single, or legally separated /
      divorced; conjunta available only as a monoparental unit (Art. 82.1.2ª)
      when qualifying children are present.
    """

    CASADO = "casado"
    PAREJA_HECHO_REGISTRADA = "pareja_hecho_registrada"
    PAREJA_HECHO_NO_REGISTRADA = "pareja_hecho_no_registrada"
    SOLTERO = "soltero"
    SEPARADO_DIVORCIADO = "separado_divorciado"

    def monoparental_required(self) -> bool:
        """True when conjunta is available only as a monoparental unit.

        Per Art. 82.1.2ª LIRPF the monoparental unidad familiar applies
        whenever no marriage bond exists — legal separation, single, or a
        de-facto couple whether or not it is registered. The modality is
        registration-agnostic, and every such situation may opt for conjunta
        only as a single-parent unit, which requires qualifying children. Only
        ``CASADO`` (Art. 82.1.1ª, the married couple) may opt as a couple.
        """
        return self in (
            SituacionFamiliar.SOLTERO,
            SituacionFamiliar.SEPARADO_DIVORCIADO,
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
        )


class SituacionFamiliarM145(StrEnum):
    """Trinary "Situación familiar" axis declared on Modelo 145 (box 1).

    The Modelo 145 form (Comunicación de datos al pagador, BOE-A-2011-208,
    art. 88 RIRPF) collects the recipient's family-situation trinary that the
    pagador uses to apply Art. 81 RIRPF withholding adjustments. It is a
    distinct axis from :class:`SituacionFamiliar`, which encodes the Art. 82
    LIRPF unidad-familiar conjunta-eligibility test — Art. 81 retención
    arithmetic and Art. 82 conjunta arithmetic do not share categories.

    Form-numbered values (mirroring the three numbered boxes on the
    physical mod145 form):

    - ``familia_1``: viudo/a o casado/a separado/a legalmente con
      descendientes que dan derecho a la totalidad del mínimo por
      descendientes. Eligible for the supplementary withholding reduction
      under RIRPF art. 81.1.1°.
    - ``familia_2``: casado/a y no separado/a legalmente cuyo cónyuge no
      obtiene rentas anuales > €1,500 (excluidas las exentas).  Eligible
      for the supplementary withholding reduction under RIRPF art. 81.1.2°.
    - ``familia_3``: situación familiar distinta de las anteriores. The
      default; no supplementary withholding reduction.
    """

    FAMILIA_1 = "familia_1"
    FAMILIA_2 = "familia_2"
    FAMILIA_3 = "familia_3"

    def is_eligible_for_supplementary_reduction(self) -> bool:
        """True when the situation grants the RIRPF art. 81.1.1°/2° reduction."""
        return self in (
            SituacionFamiliarM145.FAMILIA_1,
            SituacionFamiliarM145.FAMILIA_2,
        )


__all__ = [
    "RENTA_MODELO100_CCAA_CODIGOS",
    "RENTA_MODELO100_ECIVIL_EXPORT_CODES",
    "FiscalResidency",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
    "modelo100_ccaa_codigo",
    "modelo100_ecivil_export_code",
]

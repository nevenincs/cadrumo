"""Closed AEAT Renta profile-code vocabularies.

These enums model the small code sets consumed by the Modelo 100
profile bindings. They are intentionally domain-owned so CLI and wizard
surfaces can expose accepted values without hard-coding tax vocabulary
in the presentation layer.

:class:`RentaDeclaracionType`, :class:`RentaSexCode`,
:class:`RentaMaritalStatus`, and :class:`RentaDisabilityGrade` back Modelo 100
profile bindings; :class:`SituacionFamiliar` and
:class:`SituacionFamiliarM145` keep the Art. 82 LIRPF joint-taxation axis
separate from Modelo 145 withholding categories.
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


class RentaDisabilityGrade(StrEnum):
    """Modelo 100 ``tipo_GradoDiscapacidad`` values."""

    GE_33_LT_65 = "1"
    GE_65 = "2"
    JUDICIAL_INCAPACITY = "3"
    ASSISTANCE_OR_REDUCED_MOBILITY = "4"


# ISO 3166-1 alpha-2 codes for EU member states and EEA members.
# Post-Brexit: GB is excluded (left EU 2020-12-31, left EEA 2020-12-31).
# Source: https://ec.europa.eu/eurostat/statistics-explained/index.php/Glossary:European_Economic_Area_(EEA)
# EEA = EU27 + IS, LI, NO.  CH has bilateral agreements but is not EEA.
UE_EEA_COUNTRY_CODES: frozenset[str] = frozenset(
    {
        # EU 27
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "GR",
        "ES",
        "FI",
        "FR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
        # EEA non-EU
        "IS",
        "LI",
        "NO",
    },
)
"""Closed set of EU + EEA ISO-3166-1 alpha-2 country codes (post-Brexit)."""


class FiscalResidency(StrEnum):
    """Fiscal residency category governing the applicable tax regime.

    Determines whether the taxpayer files under IRPF (Spanish resident)
    or IRNR (non-resident), following TRLIRNR RDLeg 5/2004 Art. 2:

    - ``RESIDENT_IRPF``: habitual residence in Spain; subject to IRPF
      (Ley 35/2006 LIRPF). Files Modelo 100 (or Modelo 151 for impatriados).
    - ``NON_RESIDENT_IRNR``: no habitual residence in Spain; subject to
      IRNR (RDLeg 5/2004 TRLIRNR). Files Modelo 210 (general),
      Modelo 216 (retenciones), or Modelo 247 (pensiones).

    Post-Brexit note (from 1 January 2021): GB is no longer an EU/EEA
    member; ``ue_eee_status`` returns ``False`` for GB residents regardless
    of prior residence history.
    """

    RESIDENT_IRPF = "resident_irpf"
    NON_RESIDENT_IRNR = "non_resident_irnr"


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
    "RENTA_MODELO100_ECIVIL_EXPORT_CODES",
    "UE_EEA_COUNTRY_CODES",
    "FiscalResidency",
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
    "modelo100_ecivil_export_code",
]

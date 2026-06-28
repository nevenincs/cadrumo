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

    Determines whether conjunta (joint) taxation is available and which
    unidad familiar variant applies:

    - ``casado``: married; conjunta available (Art. 82.1.1°).
    - ``pareja_hecho_registrada``: registered civil partnership in an
      autonomic registry; conjunta available (Art. 82.1.2°).
    - ``pareja_hecho_no_registrada``: de-facto couple, not registered;
      conjunta NOT available.
    - ``soltero``: single; conjunta only available as monoparental
      (Art. 82.1.2° second indent) when hijos a cargo present.
    - ``separado_divorciado``: legally separated or divorced; conjunta
      only available as monoparental when hijos a cargo present.
    """

    CASADO = "casado"
    PAREJA_HECHO_REGISTRADA = "pareja_hecho_registrada"
    PAREJA_HECHO_NO_REGISTRADA = "pareja_hecho_no_registrada"
    SOLTERO = "soltero"
    SEPARADO_DIVORCIADO = "separado_divorciado"

    def conjunta_eligible(self) -> bool:
        """True when this situation permits conjunta taxation."""
        return self in (
            SituacionFamiliar.CASADO,
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            SituacionFamiliar.SOLTERO,
            SituacionFamiliar.SEPARADO_DIVORCIADO,
        )

    def requires_spouse_or_partner(self) -> bool:
        """True when a spouse / registered partner NIF is required for conjunta."""
        return self in (
            SituacionFamiliar.CASADO,
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
        )

    def monoparental_required(self) -> bool:
        """True for the single-parent situations a monoparental unit requires.

        Per Art. 82.1.2 LIRPF the monoparental unidad familiar applies to a
        non-partnered parent, i.e. soltero or separado/divorciado.
        """
        return self in (
            SituacionFamiliar.SOLTERO,
            SituacionFamiliar.SEPARADO_DIVORCIADO,
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
    "UE_EEA_COUNTRY_CODES",
    "FiscalResidency",
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
]

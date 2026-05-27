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


# ISO 3166-1 alpha-2 codes for EU member states and EEA members.
# Post-Brexit: GB is excluded (left EU 2020-12-31, left EEA 2020-12-31).
# Source: https://ec.europa.eu/eurostat/statistics-explained/index.php/Glossary:European_Economic_Area_(EEA)
# EEA = EU27 + IS, LI, NO.  CH has bilateral agreements but is not EEA.
UE_EEA_COUNTRY_CODES: frozenset[str] = frozenset({
    # EU 27
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "GR", "ES",
    "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    # EEA non-EU
    "IS", "LI", "NO",
})
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


__all__ = [
    "UE_EEA_COUNTRY_CODES",
    "FiscalResidency",
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
]

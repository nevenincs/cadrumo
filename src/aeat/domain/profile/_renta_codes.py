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
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
]

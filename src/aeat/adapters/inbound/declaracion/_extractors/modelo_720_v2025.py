"""Modelo 720 (Bienes y derechos en el extranjero) extractor for tax year 2025.

Declaración informativa anual (1-ene → 31-mar del año siguiente) sobre
cuentas (clave C), valores/seguros/rentas (clave V), e inmuebles (clave I)
en el extranjero cuando la valoración por clave supera los 50 000 €
(DA 18ª LGT).

This extractor uses the named-field primitive to capture the per-clave
counters (nº registros) and total valoraciones that the Orden
HAP/72/2013 diseño lógico requires on every registro de tipo 1 (resumen).

Legal base: Orden HAP/72/2013 (BOE-A-2013-954).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo720V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 720.

    Each pattern in :attr:`named_field_patterns` is line-anchored and tied
    to the clave letter (C / V / I). The anchored ``clave X`` form matches
    the Orden HAP/72/2013 registro tipo 1 field label and avoids false
    positives on any line that merely mentions ``cuentas``, ``valores``,
    or ``inmuebles`` elsewhere in the PDF.

    Attributes:
        template_revision: Identifier (modelo ``"720"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Empty — Modelo 720 prints no numbered casillas in
            the registro de resumen.
        named_field_patterns: Map ``field_id → raw regex pattern`` for
            the three per-clave counters.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="720",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    named_field_patterns: ClassVar[dict[str, str]] = {
        "num_registros_cuentas": r"(?m)^[^\n]*?clave\s+C\b[^\n]*?(\d+)",
        "num_registros_valores": r"(?m)^[^\n]*?clave\s+V\b[^\n]*?(\d+)",
        "num_registros_inmuebles": r"(?m)^[^\n]*?clave\s+I\b[^\n]*?(\d+)",
    }


__all__ = ["Modelo720V2025Extractor"]

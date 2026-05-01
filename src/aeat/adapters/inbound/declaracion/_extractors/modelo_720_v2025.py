"""Modelo 720 v2025 extractor — Bienes y derechos en el extranjero.

Declaración informativa anual (1-ene → 31-mar del año siguiente) sobre
cuentas (clave C), valores/seguros/rentas (clave V), e inmuebles
(clave I) en el extranjero cuando la valoración por clave supera los
50 000 € (DA 18ª LGT).

Wave 27 migrates this extractor off the header-only MVP to the
named-field primitive: we capture the per-clave counters (nº
registros) and total valoraciones that the Orden HAP/72/2013 diseño
lógico requires on every registro de tipo 1 (resumen).

Legal base: Orden HAP/72/2013 (BOE-A-2013-954).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo720V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 720."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="720",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    # Wave 33 H3: regex tightened — anchored to clave letter (C/V/I)
    # and line-scoped. The original loose "cuentas/valores/inmuebles"
    # alternation risked false-positives on any line mentioning those
    # words elsewhere in the PDF. The anchored "clave X" form matches
    # the Orden HAP/72/2013 registro tipo 1 field label. Still
    # speculative pending an L2 Modelo 720 fixture — the exact printed
    # literal may be "Clave C  N registros" OR "Clave C: N" OR similar;
    # tighten further once a real filing is sourced.
    named_field_patterns: ClassVar[dict[str, str]] = {
        "num_registros_cuentas": r"(?m)^[^\n]*?clave\s+C\b[^\n]*?(\d+)",
        "num_registros_valores": r"(?m)^[^\n]*?clave\s+V\b[^\n]*?(\d+)",
        "num_registros_inmuebles": r"(?m)^[^\n]*?clave\s+I\b[^\n]*?(\d+)",
    }


__all__ = ["Modelo720V2025Extractor"]

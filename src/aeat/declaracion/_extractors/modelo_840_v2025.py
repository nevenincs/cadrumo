"""Modelo 840 v2025 extractor — IAE (censal, declaración por actos).

Declaración censal del Impuesto sobre Actividades Económicas — alta,
variación, baja, o comunicación del importe neto de la cifra de
negocios. Not periodic: filed within one month of the hecho censal.
IAE affects only sujetos whose INCN exceeds 1M€ (art. 82.1.c LRHL);
most autónomos are exempt.

AEAT prints numbered casilla IDs on the form (14, 15, 33, 34, 37, 38,
40, 62) carrying text payloads (ejercicio, causa, clase de cuota,
tipo actividad, grupo/epígrafe, municipio, provincia, fecha). These
are captured as strings via the text-value primitive
(:data:`aeat._pdf_import._label_regex.TEXT_VALUE_GROUP`) — see wave 24.

Legal base: Orden HAC/2572/2003 (BOE 18/09/2003).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo840V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 840 (text-casillas MVP)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="840",
        año=2025,
        revision="2025.01",
    )
    # No decimal casillas — 840 printed payloads are all text.
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    text_casilla_ids: ClassVar[tuple[str, ...]] = (
        "14",  # ejercicio
        "15",  # causa de presentación (alta / variación / baja)
        "33",  # clase de cuota (municipal / provincial / nacional)
        "34",  # tipo actividad (empresarial / profesional / artística)
        "37",  # grupo o epígrafe
        "38",  # municipio
        "40",  # provincia
        "62",  # fecha de efectos
    )


__all__ = ["Modelo840V2025Extractor"]

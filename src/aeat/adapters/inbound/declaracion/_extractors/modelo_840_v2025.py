"""Modelo 840 (IAE censal) declaración extractor for tax year 2025.

Declaración censal del Impuesto sobre Actividades Económicas — alta,
variación, baja, o comunicación del importe neto de la cifra de negocios.
Not periodic: filed within one month of the hecho censal. IAE affects
only sujetos whose INCN exceeds 1M€ (art. 82.1.c LRHL); most autónomos
are exempt.

AEAT prints numbered casilla IDs on the form (14, 15, 33, 34, 37, 38, 40,
62) carrying text payloads (ejercicio, causa, clase de cuota, tipo
actividad, grupo/epígrafe, municipio, provincia, fecha). These are
captured as strings via the text-value primitive
(:data:`aeat.adapters.inbound.pdf._label_regex.TEXT_VALUE_GROUP`).

Legal base: Orden HAC/2572/2003 (BOE 18/09/2003).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo840V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 840 (text-casillas only).

    Modelo 840 prints no decimal payloads — every captured casilla is a
    text token (year, free-form code, municipio, fecha) consumed via
    :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`'s
    text-value primitive.

    Attributes:
        template_revision: Identifier (modelo ``"840"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Empty — no decimal casillas on Modelo 840.
        text_casilla_ids: Ordered tuple of text-payload casillas
            (ejercicio, causa, clase de cuota, tipo actividad, grupo o
            epígrafe, municipio, provincia, fecha de efectos).
        text_labels: Map ``casilla_id → expected label text`` used by
            the truncation-detection pass to catch silently dropped
            multi-token values (e.g. ``"Las Palmas"`` → ``"Palmas"``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="840",
        año=2025,
        revision="2025.01",
    )
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
    text_labels: ClassVar[dict[str, str]] = {
        "14": "Ejercicio",
        "15": "Causa presentacion",
        "33": "Clase de cuota",
        "34": "Tipo actividad",
        "37": "Grupo o epigrafe",
        "38": "Municipio",
        "40": "Provincia",
        "62": "Fecha de efectos",
    }


__all__ = ["Modelo840V2025Extractor"]

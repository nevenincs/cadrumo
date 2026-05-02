"""Modelo 111 declaración extractor (v2024 / v2025 / v2026 layouts).

Modelo 111 is the quarterly withholdings summary every employer /
autónomo files: number of perceivers + aggregate amounts + retenciones
across six categories (rendimientos del trabajo, actividades
económicas, premios, ganancias patrimoniales, imputación de rentas,
cesión derechos imagen) plus the total to pay.

The AEAT Modelo 111 form layout is unchanged across 2024 → 2025 → 2026
(Orden HAP/2194/2013 is the latest M111 form-layout amendment; no
2025/2026 BOE amendment to the M111 form layout has been published).
A single extraction implementation backs three thin per-year
subclasses: :class:`Modelo111V2024Extractor`,
:class:`Modelo111V2025Extractor`, :class:`Modelo111V2026Extractor`.
Each pins its own ``template_revision`` ClassVar so the registry under
:mod:`aeat.adapters.inbound.declaracion._extractors` resolves the right
``(modelo, año, revision)`` triple for every supported year. The
shared extraction logic lives on :class:`Modelo111V2025Extractor`'s
inherited
:class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`
flow.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo111V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 111 tax year 2025.

    Owns the shared casilla map covering Apartados I-VI (rendimientos
    del trabajo, actividades económicas, premios, ganancias
    patrimoniales aprovechamientos forestales, contraprestaciones en
    especie, imputación de rentas por cesión de derechos de imagen)
    plus the resultado block (casillas 28/29/30). Labels verified
    against AEAT Instrucciones Modelo 111 2025.

    Attributes:
        template_revision: Pinned to ``("111", 2025, "2025.01")``.
        casilla_ids: Tuple of every casilla ID parsed by the extractor,
            including the resultado block (casilla 28 = total
            liquidación, 29 = a deducir, 30 = resultado a ingresar).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="111",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        # Apartado I — Rendimientos del trabajo.
        "01",  # nº perceptores
        "02",  # importe percepciones
        "03",  # importe retenciones
        # Apartado II — Actividades económicas.
        "04",
        "05",
        "06",
        # Apartado III — Premios.
        "07",
        "08",
        "09",
        # Apartado IV — Ganancias patrimoniales aprovechamientos forestales.
        "10",
        "11",
        "12",
        # Apartado V — Contraprestaciones en especie (subsuma del apartado I).
        "13",
        "14",
        "15",
        # Apartado VI — Imputación de rentas por cesión de derechos de imagen.
        "16",
        "17",
        "18",
        # Resultado. Labels verified vs AEAT Instrucciones Modelo 111 2025.
        "28",  # Total liquidación (suma retenciones + ingresos a cuenta)
        "29",  # A deducir: exclusivamente en caso de declaración complementaria
        "30",  # Resultado a ingresar
    )


class Modelo111V2024Extractor(Modelo111V2025Extractor):
    """Modelo 111 v2024 extractor — same layout as v2025 / v2026.

    The AEAT Modelo 111 form layout is unchanged across
    2024 → 2025 → 2026 (Orden HAP/2194/2013 is the latest layout
    amendment; no 2025/2026 BOE amendment to the M111 form layout has
    been published). This subclass inherits the full
    :attr:`Modelo111V2025Extractor.casilla_ids` and the
    :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`
    extraction flow and pins only :attr:`template_revision` so the
    registry resolves ``("111", 2024, "2024.01")`` to a working
    extractor.

    Attributes:
        template_revision: Pinned to ``("111", 2024, "2024.01")``.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="111",
        año=2024,
        revision="2024.01",
    )


class Modelo111V2026Extractor(Modelo111V2025Extractor):
    """Modelo 111 v2026 extractor — same layout as v2024 / v2025.

    The AEAT Modelo 111 form layout is unchanged across
    2024 → 2025 → 2026. This subclass inherits the full
    :attr:`Modelo111V2025Extractor.casilla_ids` and the
    :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`
    extraction flow and pins only :attr:`template_revision` so the
    registry resolves ``("111", 2026, "2026.01")`` to a working
    extractor.

    Attributes:
        template_revision: Pinned to ``("111", 2026, "2026.01")``.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="111",
        año=2026,
        revision="2026.01",
    )


__all__ = [
    "Modelo111V2024Extractor",
    "Modelo111V2025Extractor",
    "Modelo111V2026Extractor",
]

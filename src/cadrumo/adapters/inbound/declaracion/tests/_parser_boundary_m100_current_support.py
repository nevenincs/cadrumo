"""Shared Modelo 100 current-year (2024/2025) declaración test expectations.

The committed synthetic fixture PDFs at
``tests/fixtures/justificantes/100/{2024,2025}-0A.pdf`` are produced by
``tests/fixtures/justificantes/_generate_modelo_100_current.py``; each line
reproduces the AEAT-published Diseño de Registro field-dictionary label text
verbatim for the target casilla (see
``corpus/aeat_official/disenos_registro/modelo_100/files/*-100-diccionario-declaracion-individual-ejercicio-{2024,2025}-*.properties``).
No real ejercicio-2024/2025 declaración PDF specimen is bundled; this is the
``synthetic_from_aeat_published_text`` grounding path documented on the
registry extraction profile.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100_current_year`
        Current-year round-trip tests consuming this expected casilla set.
    :func:`~domain.calculations.registry.validated_casilla_id`
        Core casilla-id validator used to keep fixture expectations typed.
    ``tests/fixtures/justificantes/_generate_modelo_100_current.py``
        Fixture generator that stamps the corresponding printed values.
"""

from __future__ import annotations

from .....core.casilla_id import CasillaId, validated_casilla_id

M100_CURRENT_YEAR_EXPECTED_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(value, surface="m100_current_year_pdf_fixture")
    for value in (
        "0545",
        "0546",
        "0505",
        "0585",
        "0586",
        "0587",
        "0595",
        "0604",
        "0610",
        "0670",
        "0180",
        "0218",
        "0223",
        "0224",
        "0226",
        "0231",
        "0235",
        "0432",
        "0500",
        "0510",
        "0171",
    )
)

__all__ = ["M100_CURRENT_YEAR_EXPECTED_CASILLAS"]

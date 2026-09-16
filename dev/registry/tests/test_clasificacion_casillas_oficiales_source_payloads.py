"""The M100 official XML dictionary classification needs published sources and their payloads.

Source payload bytes are read from the development compiler's validated
authority, which carries the authored evidence projection.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.estado_casilla_oficial import EstadoCasillaOficial
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import clasificar_casillas_oficiales

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_m100_2024_uses_the_official_xml_dictionary_and_requires_its_authority() -> None:
    authority = compiled_bundled_authority()
    revision = authority.snapshot("100", filing_year=2024, period="0A").revision

    with pytest.raises(RegistryValidationError, match="requires published sources and source payloads"):
        clasificar_casillas_oficiales(revision)

    statuses = clasificar_casillas_oficiales(
        revision,
        sources=authority.catalogues.sources,
        source_payloads={
            str(source_id): authority.evidence.source_bytes(str(source_id))
            for source_id in authority.catalogues.sources
        },
    )

    assert statuses[validated_casilla_id("0001", surface="M100 official box 0001")] is EstadoCasillaOficial.ADDRESSED
    assert statuses[validated_casilla_id("ANOASDLG", surface="M100 dictionary-only family field")] is (
        EstadoCasillaOficial.UNDEFINED
    )

"""The M100 official XML dictionary classification needs published sources and their payloads.

Source payload bytes are read from the development compiler's validated
authority, which carries the authored evidence projection.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.estado_casilla_oficial import EstadoCasillaOficial
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import clasificar_casillas_oficiales

from ..compiler.authority import compiled_bundled_authority
from .authored_edition_support import authored_revisions
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = committed_supported_filing_years()
# The first authored Modelo 100 edition that carries the ANOASDLG family field of
# its official XML dictionary; earlier editions omit it.
_FAMILY_FIELD_FIRST_DICTIONARY_EXERCISE = next(
    revision.valid_from.year
    for revision in authored_revisions("100")
    if any(c.id == "ANOASDLG" for c in revision.casillas)
)


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_m100_uses_the_official_xml_dictionary_and_requires_its_authority(filing_year: int) -> None:
    authority = compiled_bundled_authority()
    revision = authority.snapshot("100", filing_year=filing_year, period="0A").revision

    with pytest.raises(RegistryValidationError, match="requires published sources and source payloads"):
        clasificar_casillas_oficiales(revision)

    statuses = clasificar_casillas_oficiales(
        revision,
        sources=authority.catalogues.sources,
        # Read from the corpus on disk, not from the authority's evidence
        # projection: a COMPILATION carries no projection at all (it is the
        # published artifact that embeds evidence), so every lookup there was a
        # codec refusal rather than a payload.
        source_payloads={
            str(source_id): (bundled_path() / source.corpus_path).read_bytes()
            for source_id, source in authority.catalogues.sources.items()
            if source.corpus_path and (bundled_path() / source.corpus_path).is_file()
        },
    )

    assert statuses[validated_casilla_id("0001", surface="M100 official box 0001")] is EstadoCasillaOficial.ADDRESSED
    family_field = validated_casilla_id("ANOASDLG", surface="M100 dictionary-only family field")
    if filing_year >= _FAMILY_FIELD_FIRST_DICTIONARY_EXERCISE:
        assert statuses[family_field] is EstadoCasillaOficial.UNDEFINED
    else:
        assert family_field not in statuses

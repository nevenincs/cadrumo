"""A persona's recorded AEAT filing is what the production receipt checks take as the return's justificante."""

from __future__ import annotations

from datetime import datetime

import pytest

from ...adapters.inbound.justificante.parser import parse_justificante_bytes
from ...adapters.outbound.aeat.sede.declarations_remote import extract_csv_from_url
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.personas import read_persona
from .persona_aeat_filings import PRESENTED_TIME, justificante_pdf_bytes, recorded_filing
from .persona_materialisation import year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONAS = ("autonomo-electricista", "autonomo-fontanero", "intracomunitario-desarrollador", "minorista-recargo")


@pytest.mark.parametrize("persona_id", _PERSONAS)
def test_a_recorded_filing_carries_a_receipt_the_parser_reads_as_its_return(
    persona_id: str, operation: PinnedAuthorityOperation
) -> None:
    envelope = year_envelope(operation)
    persona = read_persona(persona_id, envelope=envelope)
    tax_id = persona.identity(persona.taxpayer)
    assert persona.aeat_filings
    for filing in persona.aeat_filings:
        year = filing.year.resolve(envelope)
        held = recorded_filing(persona, filing, envelope=envelope, operation=operation)
        (artefact,) = held.observation.artefacts
        receipt = parse_justificante_bytes(held.justificante)

        assert artefact.kind == "justificante_pdf"
        assert (artefact.byte_count, artefact.sha256) == (len(held.justificante), sha256_hex(held.justificante))
        assert extract_csv_from_url(str(artefact.source_url)) == filing.csv
        assert receipt.csv == filing.csv
        assert receipt.presentation_id == filing.justificante
        assert receipt.presented_at == datetime.combine(filing.presented.resolve(envelope), PRESENTED_TIME)
        assert receipt.matches_filing_target(
            modelo=filing.modelo, filing_year=year, period=Period.from_year_and_code(year, filing.period), tax_id=tax_id
        )
        assert held.observation.authenticated_identity == tax_id
        assert (held.observation.ejercicio, held.declaration.ejercicio) == (year, year)
        assert {(casilla.casilla_id, casilla.value) for casilla in held.observation.casillas} == set(filing.casillas)


def test_a_receipt_of_another_taxpayer_does_not_match_the_return(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("autonomo-fontanero", envelope=envelope)
    (filing,) = persona.aeat_filings
    other = read_persona("autonomo-electricista", envelope=envelope)
    year = filing.year.resolve(envelope)
    body = justificante_pdf_bytes(
        modelo=filing.modelo,
        year=year,
        period=filing.period,
        tax_id=other.identity(other.taxpayer),
        csv=filing.csv,
        number=filing.justificante,
        presented_at=datetime.combine(filing.presented.resolve(envelope), PRESENTED_TIME),
    )

    receipt = parse_justificante_bytes(body)

    assert not receipt.matches_filing_target(
        modelo=filing.modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, filing.period),
        tax_id=persona.identity(persona.taxpayer),
    )

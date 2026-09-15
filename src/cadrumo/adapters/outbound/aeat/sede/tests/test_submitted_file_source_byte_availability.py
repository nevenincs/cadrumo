"""Submitted-file reads request only the source bytes a published generation embeds.

Fixed-width layouts cite their record design as provenance, but the published
generation holds no record-design bytes, so the reader must never ask for them.
An XML dictionary layout still needs its dictionary bytes and refuses without
them. Every case reads through the real published authority; the refusal cases
use an isolated copy of one snapshot, never a mutated generation.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.schema import RegistrySnapshot
from ......domain.calculations.registry.schema_base import RegistrySourceKind
from ......domain.calculations.registry.source_byte_availability import layout_embedded_source_ids
from ..declarations_observations import (
    _submitted_file_coverage_for_casillas,
    observed_casillas_from_submitted_file,
    observed_header_facts_from_submitted_file,
    registry_observation_from_filed_declaration,
)
from ..declarations_schema import Declaracion
from ..errors import SedeParseError
from ..schema import FiledDeclaracionArtefact
from ._declarations_support import (
    _DECLARATIONS_LISTING_URL,
    _FIXTURE_ROOT,
    _SUBMITTED_FILE_100_2023_0A,
    _filed_observation,
    _submitted_file_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SUBMITTED_FILES = _FIXTURE_ROOT / "submitted-files"


def _declaration(modelo: str, ejercicio: int, period_code: str, expediente_id: str) -> Declaracion:
    return Declaracion(
        modelo=modelo,
        ejercicio=ejercicio,
        period=Period.from_year_and_code(ejercicio, period_code),
        expediente_id=expediente_id,
        estado="ALTA",
        presented_at=datetime(ejercicio, 4, 20, 10, 0, 0, tzinfo=UTC),
        justificante_link_text="Ver",
        archive_link_text="Ver",
    )


def _artefact(body: bytes) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime(2026, 5, 5, 6, 9, 7, tzinfo=UTC),
    )


def _with_source_kind(snapshot: RegistrySnapshot, source_id: str, kind: RegistrySourceKind) -> RegistrySnapshot:
    """Return an isolated snapshot copy whose one catalogued source declares ``kind``."""
    sources = dict(snapshot.sources)
    sources[source_id] = sources[source_id].model_copy(update={"kind": kind})
    return snapshot.model_copy(update={"sources": sources})


@pytest.mark.parametrize(
    ("modelo", "ejercicio", "period_code", "expediente_id", "fixture"),
    [
        ("111", 2025, "1T", "202511113520436S", _SUBMITTED_FILES / "modelo-111-2025-1T-redacted.txt"),
        ("130", 2026, "1T", "202610013522222A", _SUBMITTED_FILES / "modelo-130-2026-1T-redacted.txt"),
    ],
)
def test_fixed_width_read_succeeds_without_record_design_bytes_and_keeps_its_citations(
    operation: PinnedAuthorityOperation,
    modelo: str,
    ejercicio: int,
    period_code: str,
    expediente_id: str,
    fixture: Path,
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=ejercicio, period=period_code)
    layout = resolve_export_layout(snapshot).layout
    citation_only = [
        str(ref) for ref in layout.source_refs if snapshot.sources[str(ref)].kind is RegistrySourceKind.RECORD_DESIGN
    ]
    assert citation_only, "the fixed-width layout must cite its record design"
    assert layout_embedded_source_ids((layout,), sources=snapshot.sources) == frozenset()
    for source_id in citation_only:
        with pytest.raises(LookupError):
            operation.source_evidence(source_id)

    body = _submitted_file_payload(fixture)
    observed = observed_casillas_from_submitted_file(
        snapshot=snapshot,
        declaration=_declaration(modelo, ejercicio, period_code, expediente_id),
        body=body,
        artefact=_artefact(body),
        operation=operation,
    )
    coverage = _submitted_file_coverage_for_casillas(
        snapshot=snapshot, body=body, casillas=observed, operation=operation
    )
    headers = observed_header_facts_from_submitted_file(snapshot=snapshot, body=body, operation=operation)

    assert observed
    assert coverage == pytest.approx(1.0)
    assert all(fact.source_artefact_kind == "submitted_file" for fact in headers)

    registry_observation = registry_observation_from_filed_declaration(
        _filed_observation(
            modelo=modelo,
            ejercicio=ejercicio,
            period=period_code,
            casilla_values={item.casilla_id: Decimal(item.value) for item in observed},
        ),
        operation=operation,
    )
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    assert registry_observation.observations
    for row in registry_observation.observations:
        assert row.source_refs == casillas[row.casilla_id].source_refs
        assert row.legal_refs == casillas[row.casilla_id].legal_refs
    cited = {str(ref) for row in registry_observation.observations for ref in row.source_refs}
    assert set(citation_only) <= cited


def test_xml_dictionary_read_still_consumes_its_embedded_dictionary(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("100", filing_year=2023, period="0A")
    layout = resolve_export_layout(snapshot).layout
    body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)

    embedded = layout_embedded_source_ids((layout,), sources=snapshot.sources)
    observed = observed_casillas_from_submitted_file(
        snapshot=snapshot,
        declaration=_declaration("100", 2023, "0A", "202310010000001A"),
        body=body,
        artefact=_artefact(body),
        operation=operation,
    )

    assert str(layout.dictionary_source_ref) in embedded
    assert observed


def test_xml_dictionary_classified_without_bytes_refuses_the_read(operation: PinnedAuthorityOperation) -> None:
    published = operation.snapshot("100", filing_year=2023, period="0A")
    dictionary_id = str(resolve_export_layout(published).layout.dictionary_source_ref)
    snapshot = _with_source_kind(published, dictionary_id, RegistrySourceKind.RECORD_DESIGN)
    body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)

    with pytest.raises(SedeParseError) as refusal:
        observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=_declaration("100", 2023, "0A", "202310010000001A"),
            body=body,
            artefact=_artefact(body),
            operation=operation,
        )

    assert dictionary_id in str(refusal.value)


def test_embedded_source_missing_from_the_generation_fails_loudly(operation: PinnedAuthorityOperation) -> None:
    published = operation.snapshot("111", filing_year=2025, period="1T")
    record_design_id = str(resolve_export_layout(published).layout.source_refs[0])
    snapshot = _with_source_kind(published, record_design_id, RegistrySourceKind.DICTIONARY)
    body = _submitted_file_payload(_SUBMITTED_FILES / "modelo-111-2025-1T-redacted.txt")

    with pytest.raises(LookupError, match=record_design_id):
        observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=_declaration("111", 2025, "1T", "202511113520436S"),
            body=body,
            artefact=_artefact(body),
            operation=operation,
        )

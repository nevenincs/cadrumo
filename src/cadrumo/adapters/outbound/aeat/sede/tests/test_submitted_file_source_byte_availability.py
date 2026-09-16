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

import pytest
from pydantic import AnyHttpUrl

from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.schema import RegistrySnapshot
from ......domain.calculations.registry.schema_base import RegistrySourceKind
from ..declarations_observations import (
    observed_casillas_from_submitted_file,
    observed_header_facts_from_submitted_file,
    published_layout_source_payloads,
    registry_observation_from_filed_declaration,
)
from ..declarations_schema import Declaracion
from ..errors import SedeParseError
from ..schema import FiledDeclaracionArtefact
from ._declarations_support import (
    _DECLARATIONS_LISTING_URL,
    _SUBMITTED_FILE_100_2023_0A,
    _filed_observation,
    _submitted_file_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXED_WIDTH_CONTEXTS = pytest.mark.parametrize(
    ("modelo", "ejercicio", "period_code"),
    [("111", 2025, "1T"), ("130", 2026, "1T")],
)


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


def _without_source(snapshot: RegistrySnapshot, source_id: str) -> RegistrySnapshot:
    """Return an isolated snapshot copy whose catalogue omits ``source_id``."""
    sources = {key: value for key, value in snapshot.sources.items() if str(key) != source_id}
    return snapshot.model_copy(update={"sources": sources})


def _record_design_ids(snapshot: RegistrySnapshot) -> list[str]:
    layout = resolve_export_layout(snapshot).layout
    return [
        str(ref) for ref in layout.source_refs if snapshot.sources[str(ref)].kind is RegistrySourceKind.RECORD_DESIGN
    ]


@_FIXED_WIDTH_CONTEXTS
def test_fixed_width_layout_requests_no_source_bytes(
    operation: PinnedAuthorityOperation, modelo: str, ejercicio: int, period_code: str
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=ejercicio, period=period_code)
    record_designs = _record_design_ids(snapshot)
    assert record_designs, "the fixed-width layout must cite its record design"
    for source_id in record_designs:
        with pytest.raises(LookupError):
            operation.source_evidence(source_id)

    assert published_layout_source_payloads(snapshot=snapshot, operation=operation) == {}


@_FIXED_WIDTH_CONTEXTS
def test_record_design_citations_survive_into_registry_observations(
    operation: PinnedAuthorityOperation, modelo: str, ejercicio: int, period_code: str
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=ejercicio, period=period_code)
    record_designs = set(_record_design_ids(snapshot))
    cited_casillas = {
        casilla.id: casilla
        for casilla in snapshot.revision.casillas
        if casilla.legal_refs and record_designs.intersection(str(ref) for ref in casilla.source_refs)
    }
    assert cited_casillas

    registry_observation = registry_observation_from_filed_declaration(
        _filed_observation(
            modelo=modelo,
            ejercicio=ejercicio,
            period=period_code,
            casilla_values=dict.fromkeys(cited_casillas, Decimal("1")),
        ),
        operation=operation,
    )

    assert {row.casilla_id for row in registry_observation.observations} == set(cited_casillas)
    for row in registry_observation.observations:
        assert row.source_refs == cited_casillas[row.casilla_id].source_refs
        assert row.legal_refs == cited_casillas[row.casilla_id].legal_refs
        assert record_designs.intersection(str(ref) for ref in row.source_refs)


def test_header_read_refuses_a_layout_citing_an_uncatalogued_source(operation: PinnedAuthorityOperation) -> None:
    published = operation.snapshot("111", filing_year=2025, period="1T")
    record_design_id = _record_design_ids(published)[0]
    snapshot = _without_source(published, record_design_id)

    with pytest.raises(RegistryValidationError, match=record_design_id):
        observed_header_facts_from_submitted_file(snapshot=snapshot, body=b"", operation=operation)


def test_header_read_still_yields_nothing_for_an_unparseable_fichero(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("111", filing_year=2025, period="1T")

    assert (
        observed_header_facts_from_submitted_file(snapshot=snapshot, body=b"not a fichero", operation=operation) == ()
    )


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
    record_design_id = _record_design_ids(published)[0]
    snapshot = _with_source_kind(published, record_design_id, RegistrySourceKind.DICTIONARY)

    with pytest.raises(LookupError, match=record_design_id):
        published_layout_source_payloads(snapshot=snapshot, operation=operation)

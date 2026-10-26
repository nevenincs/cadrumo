"""Which catalogued source kinds a published authority carries bytes for."""

from __future__ import annotations

import pytest

from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..export import resolve_export_layout
from ..schema import RegistrySnapshot
from ..schema_base import RegistrySourceKind
from ..source_byte_availability import (
    EMBEDDED_SOURCE_KINDS,
    embedded_source_ids,
    layout_embedded_source_ids,
    source_bytes_are_embedded,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BYTES_EMBEDDED_BY_KIND: dict[RegistrySourceKind, bool] = {
    RegistrySourceKind.RECORD_DESIGN: False,
    RegistrySourceKind.MANUAL_PDF: False,
    RegistrySourceKind.INSTRUCTIONS: False,
    RegistrySourceKind.FORM_SPEC: False,
    RegistrySourceKind.DICTIONARY: True,
    RegistrySourceKind.XSD: True,
    RegistrySourceKind.SUPPRESSION_NOTICE: False,
}
"""Independent statement of the runtime byte needs: only XML parsing and XSD versioning read bytes."""


def _m100_2023(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("100", filing_year=2023, period="0A")


def test_every_source_kind_declares_its_byte_availability() -> None:
    assert set(_BYTES_EMBEDDED_BY_KIND) == set(RegistrySourceKind)


@pytest.mark.parametrize("kind", tuple(RegistrySourceKind))
def test_source_kind_classification(kind: RegistrySourceKind, operation: PinnedAuthorityOperation) -> None:
    source = next(iter(_m100_2023(operation).sources.values())).model_copy(update={"kind": kind})

    assert (kind in EMBEDDED_SOURCE_KINDS) is _BYTES_EMBEDDED_BY_KIND[kind]
    assert source_bytes_are_embedded(source) is _BYTES_EMBEDDED_BY_KIND[kind]


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [("100", 2023, "0A"), ("111", 2025, "1T"), ("130", 2026, "1T"), ("180", 2026, "0A")],
)
def test_published_generation_holds_bytes_exactly_for_embedded_sources(
    operation: PinnedAuthorityOperation, modelo: str, filing_year: int, period: str
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period)
    embedded = embedded_source_ids(snapshot.sources)

    for source_id, source in snapshot.sources.items():
        if str(source_id) in embedded:
            assert operation.source_evidence(str(source_id)).payload_sha256 == source.sha256
        else:
            with pytest.raises(LookupError):
                operation.source_evidence(str(source_id))


def test_fixed_width_layout_reads_no_source_bytes(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("111", filing_year=2025, period="1T")
    layout = resolve_export_layout(snapshot).layout

    assert layout.source_refs
    assert layout_embedded_source_ids((layout,), sources=snapshot.sources) == frozenset()


def test_xml_dictionary_layout_reads_its_dictionary_and_xsd(operation: PinnedAuthorityOperation) -> None:
    snapshot = _m100_2023(operation)
    layout = resolve_export_layout(snapshot).layout
    kinds = {
        snapshot.sources[source_id].kind
        for source_id in layout_embedded_source_ids((layout,), sources=snapshot.sources)
    }

    assert str(layout.dictionary_source_ref) in layout_embedded_source_ids((layout,), sources=snapshot.sources)
    assert kinds == {RegistrySourceKind.DICTIONARY, RegistrySourceKind.XSD}


def test_xml_dictionary_layout_refuses_a_dictionary_without_embedded_bytes(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _m100_2023(operation)
    layout = resolve_export_layout(snapshot).layout
    dictionary_id = str(layout.dictionary_source_ref)
    sources = dict(snapshot.sources)
    sources[dictionary_id] = sources[dictionary_id].model_copy(update={"kind": RegistrySourceKind.FORM_SPEC})

    with pytest.raises(RegistryValidationError, match="does not embed"):
        layout_embedded_source_ids((layout,), sources=sources)


def test_layout_citing_an_uncatalogued_source_refuses(operation: PinnedAuthorityOperation) -> None:
    snapshot = _m100_2023(operation)
    layout = resolve_export_layout(snapshot).layout
    sources = {key: value for key, value in snapshot.sources.items() if key != layout.dictionary_source_ref}

    with pytest.raises(RegistryValidationError, match="absent from the snapshot catalogue"):
        layout_embedded_source_ids((layout,), sources=sources)

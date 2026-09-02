"""Payload acceptance re-hashes emitted bytes and checks official field positions.

These tests once ran over modelo 200 and over ``LiveFilingExportProofAuthority``.
Both supports were withdrawn beneath them. The authority now refuses on
construction, because the single-channel filing proof it implements was replaced
by the two-channel source-and-custody authority, and modelo 200 lost both its
filing grade and every one of its export layouts while the tests still probed
into ``m200-2025.dp200001.f0001``.

What remains here is the part that was never about either: a pure re-hash of
emitted bytes against independently recorded acceptance evidence. That surface is
live, and while its tests sat red against a withdrawn modelo it was gated by
nothing. It is re-sited onto modelo 151, whose annual coordinate holds filing
grade and whose layout carries the filing envelope these checks need.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.application.filing.tests._export_support import (
    _m151_producer_snapshot,
    _modelo_151_export_coordinate_draft,
)
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..filing_export_proof import (
    FilingExportLiveProofEntry,
    FilingExportOfficialOffsetProbe,
    verify_filing_export_payload_acceptance,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIRST_RECORD = "m151-page-01"
_FIRST_FIELD = "m151-2023.pagina01.f001"
_SECOND_FIELD = "m151-2023.pagina01.f002"


def _m151_layout(registry_authority):
    return registry_authority.snapshot("151", filing_year=2025, period="0A").revision.export_layouts[0]


def _m151_entry() -> FilingExportLiveProofEntry:
    """One acceptance entry at the modelo 151 annual coordinate.

    The digest and extent are placeholders every test replaces with values
    computed from the payload it builds; only the coordinate, draft and probe
    identity are fixed here.
    """
    return FilingExportLiveProofEntry(
        modelo=Modelo.M151,
        revision="2025-y-siguientes",
        design_epoch="2023",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        draft=_modelo_151_export_coordinate_draft(),
        producer_snapshot=_m151_producer_snapshot(),
        expected_payload_sha256="0" * 64,
        expected_emitted_bytes=1,
        official_offset_probes=(FilingExportOfficialOffsetProbe(record_id=_FIRST_RECORD, field_id=_FIRST_FIELD),),
    )


def test_proof_entry_refuses_duplicate_official_probe_identities() -> None:
    """Two probes naming the same field would prove one position twice and call it two."""
    probe = FilingExportOfficialOffsetProbe(record_id=_FIRST_RECORD, field_id=_FIRST_FIELD)

    with pytest.raises(ValueError, match="probes must identify distinct fields"):
        replace(_m151_entry(), official_offset_probes=(probe, probe))


def test_payload_acceptance_rehashes_bytes_extent_and_official_offset(registry_authority) -> None:
    """Digest, extent and official field position are each re-derived from the payload.

    Each of the three is broken separately, because a single check passing does
    not show the other two are wired: a payload can hash correctly and still sit
    at the wrong offset.
    """
    layout = _m151_layout(registry_authority)
    prefix_extent = layout.filing_envelope.prefix_extent
    payload = b" " * prefix_extent + b"<T" + b" " * 8
    entry = replace(
        _m151_entry(),
        expected_payload_sha256=sha256_hex(payload),
        expected_emitted_bytes=len(payload),
    )

    verify_filing_export_payload_acceptance(entry=entry, layout=layout, payload=payload)

    with pytest.raises(RegistryValidationError, match="digest does not match"):
        verify_filing_export_payload_acceptance(entry=entry, layout=layout, payload=payload + b"x")

    wrong_extent = replace(entry, expected_emitted_bytes=len(payload) + 1)
    with pytest.raises(RegistryValidationError, match="extent does not match"):
        verify_filing_export_payload_acceptance(entry=wrong_extent, layout=layout, payload=payload)

    # The literal is present but displaced by one byte, so a check that only
    # searched for it rather than reading its declared position would pass.
    moved = b" " * prefix_extent + b"X<T" + b" " * 7
    moved_entry = replace(entry, expected_payload_sha256=sha256_hex(moved), expected_emitted_bytes=len(moved))
    with pytest.raises(RegistryValidationError, match="disagrees at official field"):
        verify_filing_export_payload_acceptance(entry=moved_entry, layout=layout, payload=moved)


def test_payload_acceptance_refuses_distinct_probe_ids_at_overlapping_emitted_bytes(registry_authority) -> None:
    """Distinct probes covering the same bytes are refused, not counted twice.

    The overlap is constructed by moving the second field onto the first rather
    than found in the corpus, because the shipped layouts do not overlap and a
    check that never sees the condition proves nothing about it.
    """
    layout = _m151_layout(registry_authority)
    first = min(layout.records, key=lambda record: record.order)
    overlapping_field = next(field for field in first.fields if str(field.id) == _SECOND_FIELD)
    overlapping_record = first.model_copy(
        update={
            "fields": tuple(
                field.model_copy(update={"offset": 2}) if field == overlapping_field else field
                for field in first.fields
            ),
        },
    )
    overlapping_layout = layout.model_copy(
        update={"records": tuple(record if record != first else overlapping_record for record in layout.records)},
    )
    prefix_extent = layout.filing_envelope.prefix_extent
    payload = b" " * prefix_extent + b"<T" + b" " * 8
    entry = replace(
        _m151_entry(),
        expected_payload_sha256=sha256_hex(payload),
        expected_emitted_bytes=len(payload),
        official_offset_probes=(
            FilingExportOfficialOffsetProbe(record_id=_FIRST_RECORD, field_id=_FIRST_FIELD),
            FilingExportOfficialOffsetProbe(record_id=_FIRST_RECORD, field_id=_SECOND_FIELD),
        ),
    )

    with pytest.raises(RegistryValidationError, match="distinct emitted byte positions"):
        verify_filing_export_payload_acceptance(entry=entry, layout=overlapping_layout, payload=payload)

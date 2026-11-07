"""A design's stated unused-slot fill reaches its layout, pinned to the design's own notes."""

from __future__ import annotations

import warnings

import openpyxl
import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import ZERO_PADDED_EXPORT_DATA_TYPES
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..note_absent_fill import NOTE_ABSENT_FILLS, note_absent_fill_for
from ..record_design_intermediate import RecordDesignIntermediateSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DESIGN = (
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_369",
    "files",
    "01-369-regimenes-especiales-aplicables-a-los-ser.xlsx",
)
_REVISIONS = (
    ("esquema-exterior", "EXT-1T"),
    ("esquema-union", "1T"),
    ("esquema-importacion", "01"),
)


def test_the_declared_notes_are_the_official_design_cells_verbatim() -> None:
    declaration = NOTE_ABSENT_FILLS["aeat-dr-369-2021"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        workbook = openpyxl.load_workbook(bundled_path(*_DESIGN), data_only=True, read_only=False)
    sheet = workbook[declaration.sheet]
    assert tuple(sheet[cell].value for cell in declaration.note_cells) == declaration.note_statements


def test_a_reading_refuses_a_design_other_than_the_reviewed_bytes() -> None:
    declaration = NOTE_ABSENT_FILLS["aeat-dr-369-2021"]
    source = RecordDesignIntermediateSource.model_construct(source_ref=declaration.source_ref, source_sha256="0" * 64)
    with pytest.raises(RegistryValidationError, match="not pinned"):
        note_absent_fill_for(source)


@pytest.mark.parametrize(("revision", "period"), _REVISIONS)
def test_every_valued_numeric_slot_of_the_design_declares_the_stated_fill(revision: str, period: str) -> None:
    snapshot = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period=period, revision_id=revision
    )
    fields = [
        field for layout in snapshot.revision.export_layouts for record in layout.records for field in record.fields
    ]
    numeric = [
        field
        for field in fields
        if field.data_type in ZERO_PADDED_EXPORT_DATA_TYPES and field.kind.value not in {"literal", "filler"}
    ]
    assert numeric
    assert {field.absent_fill for field in numeric} == {"spaces"}
    assert {field.absent_fill for field in fields if field not in numeric} == {None}


@pytest.mark.parametrize(("revision", "period"), _REVISIONS)
def test_the_design_row_gives_the_marker_and_the_closer_gives_the_bare_quarter(revision: str, period: str) -> None:
    snapshot = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period=period, revision_id=revision
    )
    [layout] = snapshot.revision.export_layouts
    markers = {field.presence_marker for record in layout.records for field in record.fields} - {None}
    assert markers == {"C"}
    assert layout.filing_envelope is not None
    assert layout.filing_envelope.scheme_period_form == "bare_quarter"

"""A design's notes on writing a negative reach only the amounts they name, pinned to the design."""

from __future__ import annotations

import warnings

import openpyxl
import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportSignPosition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..note_negative_amount import _NOTE_NEGATIVE_AMOUNTS, note_negative_amount_for
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
_DECLARATION = _NOTE_NEGATIVE_AMOUNTS["aeat-dr-369-2021"]


def test_the_declared_notes_are_printed_in_the_official_design_cells() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        workbook = openpyxl.load_workbook(bundled_path(*_DESIGN), data_only=True, read_only=False)
    sheet = workbook[_DECLARATION.sheet]
    printed = " ".join(str(sheet[cell].value) for cell in _DECLARATION.note_cells)
    assert all(statement in printed for statement in _DECLARATION.note_statements)


def test_a_reading_refuses_a_design_other_than_the_reviewed_bytes() -> None:
    source = RecordDesignIntermediateSource.model_construct(source_ref=_DECLARATION.source_ref, source_sha256="0" * 64)
    with pytest.raises(RegistryValidationError, match="not pinned"):
        note_negative_amount_for(source)


@pytest.mark.parametrize(
    ("revision", "period", "record"),
    [
        ("esquema-exterior", "EXT-1T", "modelo-369-exterior-t36902"),
        ("esquema-union", "1T", "modelo-369-union-t36908"),
        ("esquema-importacion", "01", "modelo-369-importacion-t36911"),
    ],
)
def test_only_the_correction_amounts_of_a_revision_are_signed(revision: str, period: str, record: str) -> None:
    layout = published_snapshot("369", filing_year=2026, period=period, revision_id=revision).revision.export_layouts[0]
    signed = [(item.id, field) for item in layout.records for field in item.fields if field.signed]
    assert len(signed) == 28
    assert all(record_id.startswith(record) for record_id, _ in signed)
    assert all(field.sign_position is ExportSignPosition.MINUS_DISPLACES_DIGIT for _, field in signed)

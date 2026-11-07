"""A design's notes on writing a negative reach only the amounts they name, pinned to the design."""

from __future__ import annotations

import warnings

import openpyxl
import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportSignPosition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ...form_layout.reconciliation import admit_note_signed_amount
from ..note_negative_amount import NOTE_NEGATIVE_AMOUNTS, note_negative_amount_for
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
_DECLARATION = NOTE_NEGATIVE_AMOUNTS["aeat-dr-369-2021"]


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
    layout = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period=period, revision_id=revision
    ).revision.export_layouts[0]
    signed = [(item.id, field) for item in layout.records for field in item.fields if field.signed]
    assert len(signed) == 28
    assert all(record_id.startswith(record) for record_id, _ in signed)
    assert all(field.sign_position is ExportSignPosition.MINUS_DISPLACES_DIGIT for _, field in signed)


_UNSIGNED: dict[str, object] = {
    "data_type": "decimal",
    "decimals": 2,
    "signed": False,
    "sign_position": None,
    "design_type": "Num",
}
_SIGNED: dict[str, object] = {
    "data_type": "money",
    "decimals": None,
    "signed": True,
    "sign_position": "minus_displaces_digit",
    "design_type": None,
}


def test_form_reconciliation_admits_an_amount_gaining_the_noted_sign() -> None:
    old = dict(_UNSIGNED)
    assert admit_note_signed_amount(old, _SIGNED) == 1
    assert old == _SIGNED


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ({**_UNSIGNED, "decimals": 3}, _SIGNED),
        ({**_UNSIGNED, "data_type": "text"}, _SIGNED),
        (_UNSIGNED, {**_SIGNED, "sign_position": "blank_or_n"}),
    ],
    ids=["other-scale", "not-an-amount", "other-sign"],
)
def test_form_reconciliation_admits_no_other_shape_change(old: dict[str, object], new: dict[str, object]) -> None:
    held = dict(old)
    assert admit_note_signed_amount(held, new) == 0
    assert held == old

"""A scheme period's design rows reach their layout, pinned to the design's own page."""

from __future__ import annotations

import warnings

import openpyxl
import pytest

from cadrumo.application.filing.export_envelope import render_declared_prefix
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.filing.errors import FilingExportValidationError

from ..design_scheme_period_fields import DESIGN_SCHEME_PERIOD_FIELDS, design_scheme_period_fields_for
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
_DECLARATION = DESIGN_SCHEME_PERIOD_FIELDS["aeat-dr-369-2021"]
_REVISIONS = (("esquema-exterior", "EXT-1T"), ("esquema-union", "1T"), ("esquema-importacion", "01"))


def _sheet_rows(sheet_name: str) -> list[tuple[object, ...]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        workbook = openpyxl.load_workbook(bundled_path(*_DESIGN), data_only=True, read_only=False)
    return [tuple(row) for row in workbook[sheet_name].iter_rows(values_only=True)]


def _layout(revision: str, period: str):
    snapshot = published_snapshot(
        "369", filing_year=filing_year_envelope().horizon, period=period, revision_id=revision
    )
    [layout] = snapshot.revision.export_layouts
    return layout


def _period_fields(revision: str, period: str) -> dict[str, ExportFieldDefinition]:
    return {
        field.scheme_period_part: field
        for record in _layout(revision, period).records
        for field in record.fields
        if field.scheme_period_part is not None
    }


def test_the_declared_rows_are_the_official_page_rows_verbatim() -> None:
    for sheet in _DECLARATION.ordinal_part_by_sheet:
        cells = {str(cell).strip() for row in _sheet_rows(sheet) for cell in row if cell is not None}
        assert {
            _DECLARATION.filing_year_description,
            _DECLARATION.period_type_description,
            _DECLARATION.ordinal_description,
        } <= cells


def test_a_reading_refuses_a_design_other_than_the_reviewed_bytes() -> None:
    source = RecordDesignIntermediateSource.model_construct(source_ref=_DECLARATION.source_ref, source_sha256="0" * 64)
    with pytest.raises(RegistryValidationError, match="not pinned"):
        design_scheme_period_fields_for(source)


@pytest.mark.parametrize(
    ("revision", "period", "ordinal_part", "period_type"),
    [
        ("esquema-exterior", "EXT-1T", "quarter_ordinal", "T"),
        ("esquema-union", "1T", "quarter_ordinal", "T"),
        ("esquema-importacion", "01", "month_ordinal", "M"),
    ],
)
def test_every_regime_prints_its_period_from_the_filed_period(
    revision: str, period: str, ordinal_part: str, period_type: str
) -> None:
    fields = _period_fields(revision, period)
    assert set(fields) == {"filing_year", "period_type", ordinal_part}
    assert fields["period_type"].scheme_period_type == period_type


def test_a_period_type_row_must_declare_the_constant_it_prints() -> None:
    field = _period_fields("esquema-exterior", "EXT-1T")["period_type"]
    with pytest.raises(ValueError, match="scheme period type"):
        ExportFieldDefinition.model_validate({**field.model_dump(mode="python"), "scheme_period_type": None})


@pytest.mark.parametrize(("revision", "period"), _REVISIONS)
def test_the_envelope_lists_the_tokens_the_design_period_row_prints(revision: str, period: str) -> None:
    envelope = _layout(revision, period).filing_envelope
    assert envelope is not None
    quarters = ("1T", "2T", "3T", "4T")
    months = tuple(f"{month:02d}" for month in range(1, 13))
    assert envelope.period_tokens == (*quarters, *months)
    printed = {str(cell) for row in _sheet_rows("T3690 Estruc. gral") for cell in row if cell is not None}
    assert any('["1T".."4T"]' in cell and '["01", "02".."12"]' in cell for cell in printed)


@pytest.mark.usefixtures("operation")
@pytest.mark.parametrize("token", ["0A", "1P"])
def test_a_declarant_envelope_refuses_a_period_its_design_does_not_list(token: str) -> None:
    envelope = _layout("esquema-union", "1T").filing_envelope
    assert envelope is not None
    with pytest.raises(FilingExportValidationError, match="range its design lists"):
        render_declared_prefix(
            envelope.prefix_fields,
            prefix_extent=envelope.prefix_extent,
            modelo=Modelo("369"),
            period=Period.from_year_and_code(filing_year_envelope().horizon, token),
            product_software_identity=None,
            declarant_tax_id="Y0001006P",
            envelope=envelope,
        )

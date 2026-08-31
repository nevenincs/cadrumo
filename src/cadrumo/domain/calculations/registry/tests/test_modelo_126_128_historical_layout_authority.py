"""Historical record-design authority for the Modelo 126 and 128 parent layouts.

The bundled 2015--2019 PDFs establish the last historical geometry that the
2019-y-siguientes parent layouts may claim.  They do not establish an earlier
registry selection: the calculation-grade revisions deliberately begin in
2019, while the 2020 workbooks independently confirm the same record bodies.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import NamedTuple

import pytest

from .....core.resources.bundled_data import bundled_path
from .._validate_export_layout_coverage import _position, validate_export_layout_record_coverage
from ..errors import NoRevisionForPeriodError
from ..loader import load_catalogue_file, load_modelo_directory
from ..record_design import extract_record_design
from ..temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _HistoricalLayoutCase(NamedTuple):
    modelo_id: str
    historic_source_id: str
    current_source_id: str
    body_extent: int
    body_field_count: int
    complementaria_offset: int


_CASES = (
    _HistoricalLayoutCase(
        modelo_id="126",
        historic_source_id="aeat-dr-126-2015-2019",
        current_source_id="aeat-dr-126-2020",
        body_extent=500,
        body_field_count=29,
        complementaria_offset=347,
    ),
    _HistoricalLayoutCase(
        modelo_id="128",
        historic_source_id="aeat-dr-128-2015-2019",
        current_source_id="aeat-dr-128-2020",
        body_extent=400,
        body_field_count=24,
        complementaria_offset=262,
    ),
)


def _modelo_and_catalogue(case: _HistoricalLayoutCase):  # type: ignore[no-untyped-def]  # reason: this small direct-loader proof keeps its concrete schema types local instead of re-exporting them from test support
    """Load only the two authorities this historical-layout proof needs.

    This intentionally avoids the whole-tree validated authority: a failure in
    an unrelated modelo must not make the source/geometry fact for 126 or 128
    untestable.
    """
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", case.modelo_id))
    catalogue = load_catalogue_file(bundled_path("registry", "aeat", "legal", "enrolled-forms-sources-b.toml"))
    return modelo, catalogue


def _source_design(catalogue, source_id: str):  # type: ignore[no-untyped-def]  # reason: private helper retains concrete catalogue/parser types inside this focused module
    source = catalogue.sources[source_id]
    path = bundled_path() / source.corpus_path
    return source, path, extract_record_design(path)


def _body_sheet(design, extent: int):  # type: ignore[no-untyped-def]  # reason: test-only projection of the parser's concrete design type
    return next(sheet for sheet in design.require_complete() if sheet.total_positions == extent)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: f"modelo-{case.modelo_id}")
def test_historical_parent_layout_sources_are_hash_pinned_and_selection_starts_in_2019(
    case: _HistoricalLayoutCase,
) -> None:
    """Join exactly the proven 2019 boundary, without inventing pre-2019 selection."""
    modelo, catalogue = _modelo_and_catalogue(case)
    revision = modelo.revisions["2019-y-siguientes"]
    historic, historic_path, _historic_design = _source_design(catalogue, case.historic_source_id)
    current, current_path, _current_design = _source_design(catalogue, case.current_source_id)

    assert revision.valid_from == date(2019, 1, 1)
    assert revision.period_selector.year_from == 2019
    assert revision.authority_grade.value == "calculation"
    assert [(layout.id, layout.source_refs) for layout in revision.export_layouts] == [
        (f"modelo-{case.modelo_id}-fichero-boe", (case.historic_source_id, case.current_source_id)),
    ]
    assert (historic.kind, historic.evidence_tier, historic.authority) == (
        "record_design",
        "layout_authority",
        "aeat",
    )
    assert (historic.record_design_epoch, historic.applies_from, historic.applies_to) == (
        "2015",
        date(2015, 1, 1),
        date(2019, 12, 31),
    )
    assert (current.record_design_epoch, current.applies_from, current.applies_to) == (
        "2020",
        date(2020, 1, 1),
        None,
    )
    assert (historic_path.stat().st_size, sha256(historic_path.read_bytes()).hexdigest()) == (
        historic.bytes,
        historic.sha256,
    )
    assert (current_path.stat().st_size, sha256(current_path.read_bytes()).hexdigest()) == (
        current.bytes,
        current.sha256,
    )

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2018, period="1T")
    assert select_revision(modelo, filing_year=2019, period="1T") is revision
    assert select_revision(modelo, filing_year=2020, period="1T") is revision


@pytest.mark.parametrize("case", _CASES, ids=lambda case: f"modelo-{case.modelo_id}")
def test_historical_and_current_record_bodies_have_identical_geometry(case: _HistoricalLayoutCase) -> None:
    """The parent layout cites two editions only because the exact body spans agree."""
    _modelo, catalogue = _modelo_and_catalogue(case)
    _historic, _historic_path, historic_design = _source_design(catalogue, case.historic_source_id)
    _current, _current_path, current_design = _source_design(catalogue, case.current_source_id)
    historic_body = _body_sheet(historic_design, case.body_extent)
    current_body = _body_sheet(current_design, case.body_extent)

    assert len(historic_body.fields) == len(current_body.fields) == case.body_field_count
    assert [(field.offset, field.length) for field in historic_body.fields] == [
        (field.offset, field.length) for field in current_body.fields
    ]
    assert historic_body.fields[-1].offset + historic_body.fields[-1].length - 1 == case.body_extent


@pytest.mark.parametrize("case", _CASES, ids=lambda case: f"modelo-{case.modelo_id}")
def test_historical_blank_label_is_a_required_filler_and_layout_coverage_refuses_its_removal(
    case: _HistoricalLayoutCase,
) -> None:
    """Keep the combined historical ``En blanco`` label narrow and write-bound."""
    modelo, catalogue = _modelo_and_catalogue(case)
    revision = modelo.revisions["2019-y-siguientes"]
    _historic, _historic_path, historic_design = _source_design(catalogue, case.historic_source_id)
    historic_body = _body_sheet(historic_design, case.body_extent)
    blank_indicator = next(field for field in historic_body.fields if (field.offset, field.length) == (12, 1))
    complementaria = next(
        field for field in historic_body.fields if (field.offset, field.length) == (case.complementaria_offset, 1)
    )

    assert blank_indicator.description.endswith("En blanco")
    assert _position(historic_body.name, blank_indicator).declared_blank
    assert 'blanco o "X"' in complementaria.description
    assert not _position(historic_body.name, complementaria).declared_blank
    not_a_blank = blank_indicator.model_copy(
        update={"description": 'Indicador de pagina complementaria blanco o "X"'},
    )
    assert not _position(historic_body.name, not_a_blank).declared_blank
    assert (
        validate_export_layout_record_coverage(
            prefix=f"modelo {case.modelo_id} revision {revision.id}",
            revision=revision,
            source_refs=catalogue.sources,
        )
        == []
    )

    (layout,) = revision.export_layouts
    page_record = next(record for record in layout.records if record.id.endswith("page-01"))
    wounded_record = page_record.model_copy(
        update={
            "fields": tuple(
                field for field in page_record.fields if not field.id.endswith("indicador-pagina-complementaria")
            ),
        },
    )
    wounded_layout = layout.model_copy(
        update={
            "records": tuple(record if record is not page_record else wounded_record for record in layout.records),
        },
    )
    wounded_revision = revision.model_copy(update={"export_layouts": (wounded_layout,)})

    failures = validate_export_layout_record_coverage(
        prefix=f"modelo {case.modelo_id} revision {revision.id}",
        revision=wounded_revision,
        source_refs=catalogue.sources,
    )

    assert len(failures) == 1
    assert "@12+1" in failures[0]

"""Modelo 189's ejercicio 2022 is filed on the design Orden HFP/115/2022 left in force.

Orden HFP/1351/2021 art. sexto set NUMERO DE VALORES at 130-145 and Orden HFP/115/2022
DF primera set NOMINAL UNITARIO DE LOS VALORES at 146-163 and BLANCOS at 164-500.
Ordenes HFP/1180/2023 and HFP/1284/2023 first apply to ejercicio 2023 and move the
pair to 130-146 and 147-164. The 2022 edition is the storage baseline with its own
export layout; 2023 keys only those moves and the 2023 ordenes' citations.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN = "aeat-dr-189-2021-2022"
_NEXT_DESIGN = "aeat-dr-189-2023"
# (casilla id, field id) -> (offset, length) per design, as each design prints it.
_MOVED = {
    _DESIGN: {
        ("numero-valores", "modelo-189-t2-numero-valores"): (130, 16),
        ("nominal-unitario-valores", "modelo-189-t2-nominal-unitario"): (146, 18),
    },
    _NEXT_DESIGN: {
        ("numero-valores", "modelo-189-t2-numero-valores"): (130, 17),
        ("nominal-unitario-valores", "modelo-189-t2-nominal-unitario"): (147, 18),
    },
}
_PRINTED = {
    _DESIGN: (
        "130-145 numerico numero de valores",
        "146-163 numerico nominal unitario",
        "164-500 ------------ blancos",
    ),
    _NEXT_DESIGN: (
        "130-146 numerico numero de valores",
        "147-164 numerico nominal unitario",
        "165-500 ------------ blancos",
    ),
}


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("189")


def _last_design_year() -> int:
    _, catalogues = _modelo()
    applies_to = catalogues.sources[_DESIGN].applies_to
    assert applies_to is not None
    return applies_to.year


def _selected(year: int) -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=catalogues.supported_filing_years)


def _corpus_text(source_id: str) -> str:
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[source_id].corpus_path
    assert corpus_path is not None
    sidecar = bundled_path("manual_corpus_text", *corpus_path.removeprefix("corpus/").split("/"))
    sidecar = sidecar.with_name(sidecar.name + ".corpus_text.json")
    return json.loads(sidecar.read_text(encoding="utf-8"))["normalised_text"]


def _declarado_fields(revision: ModeloRevision) -> dict[str, tuple[int, int, str]]:
    (layout,) = revision.export_layouts
    (record,) = [record for record in layout.records if record.record_type == "declarado"]
    return {field.id: (field.offset, field.length, field.kind) for field in record.fields}


def test_the_last_design_year_is_authored_on_its_own_design_below_the_unreviewed_filing_grade() -> None:
    _, catalogues = _modelo()
    year = _last_design_year()
    assert year in catalogues.supported_filing_years.years
    revision = _selected(year)
    resolution = revision_temporal_resolution(
        revision, filing_year=year, period="0A", support=catalogues.supported_filing_years
    )
    assert revision.id == str(year)
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    # Filing grade needs a reviewed revision; the 2023 edition on the same footing claims it.
    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert _selected(year + 1).effective_authority_grade is RegistryAuthorityGrade.FILING
    assert _DESIGN in revision.source_refs
    assert _NEXT_DESIGN not in revision.source_refs
    assert not any("2023" in ref for ref in revision.legal_refs)
    (window,) = revision.deadline_windows
    assert (window.filing_year, window.opens_on, window.closes_on) == (
        year,
        date(year + 1, 3, 1),
        date(year + 1, 3, 31),
    )


@pytest.mark.parametrize("design", [_DESIGN, _NEXT_DESIGN])
def test_each_edition_writes_the_moved_fields_where_its_design_prints_them(design: str) -> None:
    year = _last_design_year() + (0 if design == _DESIGN else 1)
    revision = _selected(year)
    assert design in revision.source_refs
    fields = _declarado_fields(revision)
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for (casilla_id, field_id), (offset, length) in _MOVED[design].items():
        assert fields[field_id][:2] == (offset, length)
        assert casillas[casilla_id].number == f"tipo2.{offset}-{offset + length - 1}"
    blank_offset = max(offset + length for offset, length in _MOVED[design].values())
    assert fields[f"modelo-189-t2-blancos-{blank_offset}"] == (blank_offset, 501 - blank_offset, "filler")
    assert sum(length for _, length, _ in fields.values()) == 500
    for printed in _PRINTED[design]:
        assert printed in _corpus_text(design)


def test_every_other_casilla_and_field_is_unchanged_across_the_designs() -> None:
    year = _last_design_year()
    older, newer = _selected(year), _selected(year + 1)
    moved = {casilla_id for casilla_id, _ in _MOVED[_DESIGN]}
    assert [c.id for c in older.casillas] == [c.id for c in newer.casillas]
    for left, right in zip(older.casillas, newer.casillas, strict=True):
        if left.id not in moved:
            assert (left.number, left.data_type, left.section) == (right.number, right.data_type, right.section)
    older_fields, newer_fields = _declarado_fields(older), _declarado_fields(newer)
    moved_fields = {field_id for _, field_id in _MOVED[_DESIGN]}
    for field_id, spec in older_fields.items():
        if field_id not in moved_fields and not field_id.startswith("modelo-189-t2-blancos-1"):
            assert newer_fields[field_id] == spec

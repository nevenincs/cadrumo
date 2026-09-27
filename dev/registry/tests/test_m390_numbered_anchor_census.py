"""Exact parser-owned Modelo 390 numbered-page census of the pinned census design."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..analysis.m390_2022_anchor_census import (
    M390_2022_NUMBERED_ANCHOR_COUNT,
    M390_2022_NUMBERED_PAGE_ANCHORS,
    M390_2022_NUMBERED_PAGE_COUNTS,
    M390_2022_SCALAR_CASILLA_BOXES,
    census_m390_2022_numbered_anchors,
)
from ..compiler.loader import load_catalogue_file
from ..pipeline.record_design_intermediate import RecordDesignIntermediate, load_record_design_intermediate
from .authored_edition_support import source_exercise, source_with_sha256

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The official record design whose numbered pages the census covers, found by its
# pinned bytes; its applicability names the exercise.
_CENSUS_DESIGN = source_with_sha256("7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe")
_CENSUS_DESIGN_EXERCISE = source_exercise(_CENSUS_DESIGN)


def _intermediate() -> RecordDesignIntermediate:
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    return load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=_CENSUS_DESIGN.id,
        filing_year=_CENSUS_DESIGN_EXERCISE,
        design_epoch=str(_CENSUS_DESIGN_EXERCISE),
    )


def _replace_first_page(intermediate: RecordDesignIntermediate, fields: tuple[object, ...]) -> RecordDesignIntermediate:
    page = intermediate.sheets[0].model_copy(update={"fields": fields})
    return intermediate.model_copy(update={"sheets": (page, *intermediate.sheets[1:])})


def test_m390_numbered_page_census_retains_the_exact_537_parser_anchor_set() -> None:
    census = census_m390_2022_numbered_anchors(_intermediate())

    assert census.anchor_count == M390_2022_NUMBERED_ANCHOR_COUNT == 537
    assert census.anchors == M390_2022_NUMBERED_PAGE_ANCHORS
    assert {record: len(anchors) for record, anchors in census.anchors_by_record.items()} == dict(
        M390_2022_NUMBERED_PAGE_COUNTS,
    )
    assert set(census.scalar_casilla_anchors) == set(M390_2022_SCALAR_CASILLA_BOXES)
    assert set(census.scalar_casilla_anchors.values()).issubset(census.anchors)


def test_census_refuses_a_missing_source_anchor() -> None:
    intermediate = _intermediate()
    with pytest.raises(ValueError, match="missing"):
        census_m390_2022_numbered_anchors(_replace_first_page(intermediate, intermediate.sheets[0].fields[1:]))


def test_census_refuses_a_duplicate_source_anchor() -> None:
    intermediate = _intermediate()
    fields = intermediate.sheets[0].fields
    with pytest.raises(ValueError, match="repeats numbered-page anchors"):
        census_m390_2022_numbered_anchors(_replace_first_page(intermediate, (*fields, fields[0])))


def test_census_refuses_an_unknown_shifted_anchor() -> None:
    intermediate = _intermediate()
    fields = intermediate.sheets[0].fields
    shifted = fields[0].model_copy(update={"source_row": 999, "source_cell": "A999"})
    with pytest.raises(ValueError, match="unknown"):
        census_m390_2022_numbered_anchors(_replace_first_page(intermediate, (shifted, *fields[1:])))

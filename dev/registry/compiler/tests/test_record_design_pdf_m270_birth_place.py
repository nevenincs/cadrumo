"""The 2023 Modelo 270 PDF's two printed birth-place positions survive extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...maintenance_support import resolve_record_design_binary
from ...pipeline.record_design_intermediate import load_record_design_intermediate
from ...pipeline.render_profile_eligibility import source_m270_birth_place_text_field
from ...tests.authored_edition_support import source_first_exercise, source_reference
from ..loader import load_shared_catalogues
from ..record_design import extract_record_design
from ..record_design_pdf_repairs import separate_m270_birth_country_coordinate
from ..record_design_pdf_rows import unnamed_position_candidate
from ..record_design_pdf_visual import extract_pdf_text_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CURRENT_DESIGN = "aeat-dr-270-2023"
_CURRENT_DESIGN_EXERCISE = source_first_exercise(source_reference(_CURRENT_DESIGN))


def _official_pdf() -> tuple[Path, bytes, tuple[str, ...]]:
    root = bundled_path()
    sources = load_shared_catalogues(root / "registry" / "aeat").sources
    resolved = resolve_record_design_binary(
        root,
        sources,
        source_ref=_CURRENT_DESIGN,
        filing_year=_CURRENT_DESIGN_EXERCISE,
        design_epoch=str(_CURRENT_DESIGN_EXERCISE),
    )
    pdf_bytes = resolved.path.read_bytes()
    return resolved.path, pdf_bytes, extract_pdf_text_lines(pdf_bytes, source_label=str(resolved.path))


def test_birth_place_repair_reads_exact_two_source_children() -> None:
    path, pdf_bytes, lines = _official_pdf()
    repaired = separate_m270_birth_country_coordinate(lines, pdf_bytes)
    assert repaired[604].startswith("496-497 CÓDIGO PAÍS:")
    country = unnamed_position_candidate(repaired[604], 605)
    assert country is not None
    assert (country.offset, country.length, country.description) == (496, 2, "CÓDIGO PAÍS: Campo alfabético de")

    design = extract_record_design(path).require_complete()
    perceptor = next(sheet for sheet in design if sheet.name == "Tipo 2 - Registro De Perceptor")
    parent = next(field for field in perceptor.fields if field.offset == 461)
    assert (parent.row, parent.length) == (588, 37)
    assert [(child.row, child.offset, child.length) for child in parent.components] == [
        (601, 461, 35),
        (605, 496, 2),
    ]


@pytest.mark.parametrize("line_index", [587, 599, 600, 604, 618])
def test_birth_place_repair_refuses_changed_pinned_source_rows(line_index: int) -> None:
    _path, pdf_bytes, lines = _official_pdf()
    altered = list(lines)
    altered[line_index] = "changed printed coordinate"
    with pytest.raises(RegistryValidationError, match="source rows"):
        separate_m270_birth_country_coordinate(tuple(altered), pdf_bytes)
    assert separate_m270_birth_country_coordinate(lines, pdf_bytes + b"changed") == lines


@pytest.mark.parametrize(
    ("source_ref", "rows"),
    [
        ("boe-dr-270-2013-2022", (882, 886)),
        (_CURRENT_DESIGN, (601, 605)),
    ],
)
def test_birth_place_text_classification_is_exactly_source_pinned(
    source_ref: str,
    rows: tuple[int, int],
) -> None:
    exercise = source_first_exercise(source_reference(source_ref))
    root = bundled_path()
    sources = load_shared_catalogues(root / "registry" / "aeat").sources
    design = load_record_design_intermediate(
        root,
        sources,
        source_ref=source_ref,
        filing_year=exercise,
        design_epoch=str(exercise),
    )
    fields = [field for sheet in design.sheets for field in sheet.fields if field.source_row in rows]
    assert [(field.source_row, field.offset, field.length) for field in fields] == [
        (rows[0], 461, 35),
        (rows[1], 496, 2),
    ]
    for field in fields:
        assert source_m270_birth_place_text_field(
            field,
            source_ref=source_ref,
            source_sha256=design.source.source_sha256,
        )
        with pytest.raises(RegistryValidationError, match="text or geometry"):
            source_m270_birth_place_text_field(
                field.model_copy(update={"normalized_description": "changed"}),
                source_ref=source_ref,
                source_sha256=design.source.source_sha256,
            )
        with pytest.raises(RegistryValidationError, match="identity"):
            source_m270_birth_place_text_field(
                field,
                source_ref=source_ref,
                source_sha256="0" * 64,
            )

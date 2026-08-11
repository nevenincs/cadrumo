"""Official-source proof for every nonnumbered DP30302 simplified-regime field."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .....domain.iva import RegimenSimplificadoFilingRows
from .. import (
    RegistryValidationError,
    extract_record_design,
    load_catalogue_file,
    m303_regimen_simplificado_nonnumbered_fields,
    project_m303_regimen_simplificado_rows,
    resolve_record_design_binary,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGNS = (
    ("aeat-dr-303-2023", 2023, "2023", 134, ((6, 77, 13, 900), (90, 151, 1105, 1430))),
    (
        "aeat-dr-303-2024-early",
        2024,
        "2024-early",
        130,
        (
            (6, 77, 13, 900),
            (90, 91, 1105, 1109),
            (93, 93, 1113, 1115),
            (95, 119, 1119, 1235),
            (121, 121, 1239, 1241),
            (123, 151, 1245, 1430),
        ),
    ),
    (
        "aeat-dr-303-2024-late",
        2024,
        "2024-late",
        140,
        (
            (6, 77, 13, 900),
            (90, 91, 1105, 1109),
            (93, 93, 1113, 1115),
            (95, 120, 1118, 1235),
            (122, 122, 1239, 1241),
            (124, 161, 1244, 1534),
        ),
    ),
    (
        "aeat-dr-303-2025",
        2025,
        "2025",
        142,
        (
            (6, 77, 13, 900),
            (90, 91, 1105, 1109),
            (93, 93, 1113, 1115),
            (95, 118, 1120, 1235),
            (120, 120, 1239, 1241),
            (122, 147, 1246, 1424),
            (149, 164, 1535, 1614),
        ),
    ),
    (
        "aeat-dr-303-2026",
        2026,
        "2026",
        142,
        (
            (6, 77, 13, 900),
            (90, 91, 1105, 1109),
            (93, 93, 1113, 1115),
            (95, 118, 1120, 1235),
            (120, 120, 1239, 1241),
            (122, 147, 1246, 1424),
            (149, 164, 1535, 1614),
        ),
    ),
)


def _source_sheet(source_ref: str, filing_year: int, design_epoch: str):
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    return next(sheet for sheet in extract_record_design(resolved.path) if sheet.name == "DP30302")


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch", "count", "expected_runs"), _DESIGNS)
def test_real_dp30302_binary_preserves_every_nonnumbered_rs_anchor(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
    count: int,
    expected_runs: tuple[tuple[int, int, int, int], ...],
) -> None:
    fields = m303_regimen_simplificado_nonnumbered_fields(
        _source_sheet(source_ref, filing_year, design_epoch),
    )

    runs: list[tuple[int, int, int, int]] = []
    start = previous = fields[0]
    for field in fields[1:]:
        if field.ordinal != previous.ordinal + 1:
            runs.append((start.ordinal, previous.ordinal, start.offset, previous.offset + previous.length - 1))
            start = field
        previous = field
    runs.append((start.ordinal, previous.ordinal, start.offset, previous.offset + previous.length - 1))

    assert len(fields) == count
    assert tuple(runs) == expected_runs
    assert all(" - Actividad 1 - " in field.description or " - Actividad 2 - " in field.description for field in fields)


def test_projection_refuses_wrong_source_epoch_before_producing_fields() -> None:
    sheet = _source_sheet("aeat-dr-303-2025", 2025, "2025")

    with pytest.raises(RegistryValidationError, match="wrong or unknown design epoch"):
        project_m303_regimen_simplificado_rows(
            sheet,
            design_epoch="2024-late",
            expected_design_epoch="2025",
            rows=RegimenSimplificadoFilingRows(ejercicio=2025, activities=()),
            orden=(),
            applicable=False,
            censo_iae_epigraphs=frozenset(),
        )

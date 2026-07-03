"""Real-behaviour tests for the modelo capability matrix over the bundled registry."""

from __future__ import annotations

import pytest

from ..manager import ModeloCapabilityRow, build_capability_matrix, render_matrix_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _rows() -> dict[str, ModeloCapabilityRow]:
    return {row.modelo_id: row for row in build_capability_matrix()}


def test_matrix_covers_every_bundled_modelo() -> None:
    """The matrix has one row per registry-loadable modelo, sorted by id."""
    rows = build_capability_matrix()

    assert rows, "expected at least one modelo row from the bundled registry"
    assert [row.modelo_id for row in rows] == sorted(row.modelo_id for row in rows)
    assert len({row.modelo_id for row in rows}) == len(rows), "duplicate modelo rows"


def test_modelo_130_303_390_have_fichero_boe_export() -> None:
    """Ground truth: 130 / 303 / 390 are the periodic-return modelos with a fixed-width export layout."""
    rows = _rows()

    for modelo_id in ("130", "303", "390"):
        row = rows[modelo_id]
        assert row.calc_grade, f"modelo {modelo_id} should be calc-grade"
        assert row.has_completeness_manifest, f"modelo {modelo_id} should declare a completeness manifest"
        assert row.has_fixed_width_export, f"modelo {modelo_id} should register a fixed_width export layout"


def test_modelo_100_uses_xml_dictionary_export_not_fixed_width() -> None:
    """Ground truth: Modelo 100 (Renta) exports via xml_dictionary, not fichero-BOE fixed-width."""
    row = _rows()["100"]

    assert row.calc_grade
    assert row.has_xml_dictionary_export
    assert not row.has_fixed_width_export


def test_modelo_182_has_no_export_and_no_extractor() -> None:
    """Ground truth: Modelo 182 (donativos) is calc-grade but ships no export layout or extractor."""
    row = _rows()["182"]

    assert row.calc_grade
    assert not row.has_fixed_width_export
    assert not row.has_xml_dictionary_export
    assert not row.has_extractor
    assert row.extraction_profile_count == 0


def test_dormant_modelos_are_not_calc_grade() -> None:
    """Ground truth: informative/no-calculation modelos report calc_grade False, never a fabricated positive.

    Mirrors the dormant enumeration in
    ``domain/calculations/registry/tests/test_record_design_completeness.py``
    (modelos with an empty calculation closure and therefore no manifest).
    """
    rows = _rows()

    for modelo_id in ("189", "231", "280", "289", "308", "345", "360", "361", "379", "721"):
        row = rows[modelo_id]
        assert not row.calc_grade, f"modelo {modelo_id} should not be calc-grade"
        assert not row.has_completeness_manifest, f"dormant modelo {modelo_id} should carry no completeness manifest"


def test_row_reports_latest_revision_by_valid_from() -> None:
    """A multi-revision modelo's row is probed against its most recent revision."""
    row = _rows()["100"]

    assert row.revision_count >= 6
    assert row.latest_revision_id == "2025"


def test_render_matrix_table_includes_every_modelo_and_a_summary() -> None:
    """The rendered table lists every modelo id and a trailing summary line."""
    rows = build_capability_matrix()

    table = render_matrix_table(rows)

    for row in rows:
        assert row.modelo_id in table
    assert "modelos:" in table
    assert "calc-grade=" in table


def test_build_capability_matrix_is_never_a_fabricated_positive() -> None:
    """Anti-tautology proof: a modelo's declared negatives must be real absences on disk.

    Re-derives has_fixed_width_export directly from the loaded revision's
    export_layouts rather than trusting the row, proving the row is not
    hand-computed independently of the registry data it claims to summarise.
    """
    from aeat.domain.calculations.registry import bundled_authority

    authority = bundled_authority()
    rows = _rows()

    for modelo in authority.modelos:
        revision = max(modelo.revisions.values(), key=lambda r: r.valid_from)
        expected_formats = {layout.format for layout in revision.export_layouts}
        row = rows[modelo.id]
        assert row.has_fixed_width_export == ("fixed_width" in expected_formats)
        assert row.has_xml_dictionary_export == ("xml_dictionary" in expected_formats)
        assert row.has_extractor == bool(revision.extraction_profiles)
        assert row.has_completeness_manifest == (revision.completeness_manifest is not None)
